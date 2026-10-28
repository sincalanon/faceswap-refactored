#!/usr/bin/env python3
""" Pytest unit tests for :mod:`simple_gui.commands` (argument building and validation) """
import os
import sys

import pytest

from simple_gui import commands
from simple_gui.paths import FACESWAP_SCRIPT, TOOLS_SCRIPT, clean_path, is_video
from simple_gui.presets import AUTO


def _touch_images(folder, count, ext=".png"):
    os.makedirs(folder, exist_ok=True)
    for idx in range(count):
        with open(os.path.join(folder, f"face_{idx:04d}{ext}"), "wb") as handle:
            handle.write(b"x")
    return str(folder)


def _make_model(folder):
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "original_state.json"), "w", encoding="utf-8") as handle:
        handle.write("{}")
    return str(folder)


# Argument building
def test_extract_defaults_only_pass_required():
    """ Defaults are left to Faceswap: only input/output are passed """
    args = commands.build_extract(commands.ExtractOptions("/in", "/out"))
    assert args == [sys.executable, "-u", FACESWAP_SCRIPT, "extract", "-i", "/in", "-o", "/out"]


def test_extract_custom_options():
    """ Non default values become flags """
    opts = commands.ExtractOptions(' "/in dir" ', "/out", detector="s3fd", aligner="fan",
                                   masker="bisenet-fp", size=256, extract_every_n=5,
                                   min_size=40, skip_existing=True, batch_mode=True)
    args = commands.build_extract(opts)[4:]
    assert args == ["-i", "/in dir", "-o", "/out", "-D", "s3fd", "-A", "fan",
                    "-M", "bisenet-fp", "-z", "256", "-N", "5", "-m", "40", "-s", "-b"]


def test_train_args():
    """ Train always passes batch size and iterations, plus the preview flag """
    opts = commands.TrainOptions("/a", "/b", "/model", trainer="lightweight", batch_size=8,
                                 iterations=20000, save_interval=100, write_preview=True,
                                 no_flip=True)
    args = commands.build_train(opts)
    assert args[:4] == [sys.executable, "-u", FACESWAP_SCRIPT, "train"]
    assert args[4:] == ["-A", "/a", "-B", "/b", "-m", "/model", "-t", "lightweight",
                        "-b", "8", "-i", "20000", "-s", "100", "-w", "-P"]


def test_train_without_preview():
    """ No -w when the preview is switched off """
    opts = commands.TrainOptions("/a", "/b", "/m", write_preview=False)
    assert "-w" not in commands.build_train(opts)


@pytest.mark.parametrize("writer,input_path,expected", [
    (AUTO, "/x/clip.MP4", "ffmpeg"),
    (AUTO, "/x/frames", "opencv"),
    ("gif", "/x/clip.mp4", "gif"),
    ("", "/x/frames", "opencv")])
def test_resolve_writer(writer, input_path, expected):
    """ auto picks a video writer for video input and an image writer otherwise """
    assert commands.resolve_writer(writer, input_path) == expected


def test_convert_args():
    """ Convert passes writer always and other options only when changed """
    opts = commands.ConvertOptions("/v.mp4", "/out", "/model", alignments="/v_alignments.fsa",
                                   color_adjustment="match-hist", mask_type="components",
                                   output_scale=50, swap_model=True)
    args = commands.build_convert(opts)[4:]
    assert args == ["-i", "/v.mp4", "-o", "/out", "-m", "/model", "-p", "/v_alignments.fsa",
                    "-w", "ffmpeg", "-c", "match-hist", "-M", "components", "-O", "50", "-s"]


def test_convert_defaults():
    """ Default convert has no optional flags """
    args = commands.build_convert(commands.ConvertOptions("/imgs", "/out", "/model"))[4:]
    assert args == ["-i", "/imgs", "-o", "/out", "-m", "/model", "-w", "opencv"]


def test_video_args():
    """ effmpeg shortcuts """
    extract = commands.build_video(commands.VideoOptions("extract", "/v.mp4", "/frames"))
    assert extract == [sys.executable, "-u", TOOLS_SCRIPT, "effmpeg", "-a", "extract",
                       "-i", "/v.mp4", "-o", "/frames"]
    gen = commands.build_video(commands.VideoOptions("gen-vid", "/frames", "/o.mp4", fps=30))
    assert gen[-2:] == ["-R", "30"]
    ref = commands.build_video(commands.VideoOptions("gen-vid", "/frames", "/o.mp4",
                                                     reference_video="/v.mp4", mux_audio=True))
    assert ref[-3:] == ["-r", "/v.mp4", "-m"]


def test_build_command_dispatch():
    """ build_command routes by job type """
    opts = commands.TrainOptions("/a", "/b", "/m")
    assert commands.build_command(opts) == commands.build_train(opts)


# Validation
def test_validate_extract(tmp_path):
    """ Missing input and empty output are reported in Chinese """
    errors = commands.validate_extract(commands.ExtractOptions(str(tmp_path / "nope"), ""))
    assert len(errors) == 2
    assert "不存在" in errors[0] and "请填写" in errors[1]
    (tmp_path / "a.jpg").write_bytes(b"x")
    ok_opts = commands.ExtractOptions(str(tmp_path), str(tmp_path / "faces"))
    assert not commands.validate_extract(ok_opts)


def test_validate_extract_folder_without_images(tmp_path):
    """ A folder with only a video, only sub folders or unsupported images explains what to do """
    def check(folder):
        return commands.validate_extract(commands.ExtractOptions(str(folder), "/out"))

    empty = tmp_path / "empty"
    empty.mkdir()
    assert "空的" in check(empty)[0]
    vids = tmp_path / "vids"
    vids.mkdir()
    (vids / "clip.MP4").write_bytes(b"x")
    assert "视频文件" in check(vids)[0] and "clip.MP4" in check(vids)[0]
    nested = tmp_path / "nested"
    (nested / "sub").mkdir(parents=True)
    assert "子文件夹" in check(nested)[0]
    webp = tmp_path / "webp"
    webp.mkdir()
    (webp / "a.webp").write_bytes(b"x")
    assert ".webp" in check(webp)[0]
    assert not commands.validate_extract(commands.ExtractOptions(str(nested), "/out",
                                                                 batch_mode=True))


def test_extract_every_n_only_for_video():
    """ -N is dropped for a photo folder but kept for a video or batch mode """
    folder = commands.build_extract(commands.ExtractOptions("/in", "/out", extract_every_n=5))
    assert "-N" not in folder
    video = commands.build_extract(commands.ExtractOptions("/in/a.mp4", "/out", extract_every_n=5))
    assert video[-2:] == ["-N", "5"]


def test_validate_train(tmp_path):
    """ Face folders need enough images, must differ and the model folder is required """
    side_a = _touch_images(tmp_path / "a", 30)
    side_b = _touch_images(tmp_path / "b", 10)
    errors = commands.validate_train(commands.TrainOptions(side_a, side_b, ""))
    assert any("10 张" in err for err in errors)
    assert any("模型文件夹" in err for err in errors)
    same = commands.validate_train(commands.TrainOptions(side_a, side_a, str(tmp_path / "m")))
    assert any("同一个文件夹" in err for err in same)
    side_b = _touch_images(tmp_path / "b", 30)
    assert not commands.validate_train(commands.TrainOptions(side_a, side_b,
                                                             str(tmp_path / "m")))


def test_validate_convert(tmp_path):
    """ The model folder must contain a trained model """
    src = _touch_images(tmp_path / "src", 2, ext=".jpg")
    empty_model = str(tmp_path / "empty")
    os.makedirs(empty_model)
    errors = commands.validate_convert(commands.ConvertOptions(src, str(tmp_path / "o"),
                                                               empty_model))
    assert len(errors) == 1 and "没有找到训练好的模型" in errors[0]
    model = _make_model(tmp_path / "model")
    assert not commands.validate_convert(commands.ConvertOptions(src, str(tmp_path / "o"),
                                                                 model))
    bad_align = commands.ConvertOptions(src, "o", model, alignments=str(tmp_path / "x.fsa"))
    assert any("对齐文件" in err for err in commands.validate_convert(bad_align))


def test_validate_video(tmp_path):
    """ Video -> frames needs a video file """
    folder = _touch_images(tmp_path / "f", 1)
    errors = commands.validate_video(commands.VideoOptions("extract", folder, "out"))
    assert any("视频文件" in err for err in errors)
    assert not commands.validate_video(commands.VideoOptions("gen-vid", folder, "o.mp4"))


# Paths
def test_clean_path():
    """ Quotes, whitespace and ~ are handled """
    assert clean_path('  "C:\\data\\a b"  ') == "C:\\data\\a b"
    assert clean_path(None) == ""
    assert clean_path("~/x") == os.path.expanduser("~/x")


def test_is_video():
    """ Extension check is case insensitive """
    assert is_video("a/b.MKV")
    assert not is_video("a/b.png")
