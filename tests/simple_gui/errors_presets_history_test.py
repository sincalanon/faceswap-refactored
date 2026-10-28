#!/usr/bin/env python3
""" Pytest unit tests for :mod:`simple_gui.errors`, :mod:`simple_gui.presets` and
:mod:`simple_gui.history` """
import json
import os

import pytest

from simple_gui import errors, presets
from simple_gui.history import FILENAME, RecentPaths
from simple_gui.paths import CONFIG_ENV, user_config_dir


# Error mapping
@pytest.mark.parametrize("log,expected", [
    ("RuntimeError: CUDA out of memory. Tried to allocate 2.00 GiB", "内存或显存不足"),
    ("RuntimeError: DefaultCPUAllocator: can't allocate memory", "内存或显存不足"),
    ("AssertionError: Torch not compiled with CUDA enabled", "GPU/CUDA 不可用"),
    ("FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'", "找不到 ffmpeg"),
    ("UserWarning: ffmpeg binaries not found. Please call ffmpeg.init()", "找不到 ffmpeg"),
    ("ERROR    Failed to download model. Exiting. (Error: 'x', URL: y)", "下载模型文件失败"),
    ("ERROR    Side A contains fewer than 25 images.", "人脸太少"),
    ("ERROR    Error: '/x' contains no images", "没有图片"),
    ("ERROR    Model could not be found in folder '/m'. Exiting", "找不到训练好的模型"),
    ("ERROR    No alignments file found. Please provide", "找不到对齐文件"),
    ("FaceswapError: /m does not exist.", "找不到指定的文件"),
    ("PermissionError: [Errno 13] Permission denied: '/root/x'", "没有权限"),
    ("faceswap.py: error: argument -t: invalid choice: 'foo'", "参数无效"),
    ("ModuleNotFoundError: No module named 'keras'", "缺少 Python 依赖"),
])
def test_explain_failure_patterns(log, expected):
    """ Common failures map to friendly messages """
    assert expected in errors.explain_failure(f"some output\n{log}\nmore", 1)


def test_explain_failure_priority():
    """ A specific cause beats the import-time ffmpeg warning """
    log = "UserWarning: ffmpeg binaries not found\nCUDA out of memory"
    assert "内存或显存不足" in errors.explain_failure(log, 1)


@pytest.mark.parametrize("code,expected", [
    (1, "退出码 1"), (-9, "强制结束"), (137, "强制结束"), (3, "退出码 3"), (None, "异常结束")])
def test_explain_failure_exit_codes(code, expected):
    """ Unknown output falls back to the exit code """
    assert expected in errors.explain_failure("nothing useful", code)


def test_explain_failure_crash_report():
    """ The crash report path is surfaced """
    log = "CRITICAL An unexpected crash has occurred. Crash report written to '/x/crash.log'. "
    assert "/x/crash.log" in errors.explain_failure(log, 1)


def test_extraction_warning():
    """ Extraction that found no faces gets a warning; normal output does not """
    assert errors.extraction_warning("Images found:        5\nFaces detected:      12") == ""
    assert "没有检测到任何人脸" in errors.extraction_warning(
        "Images found:        5\nFaces detected:      0")
    assert "没有找到可处理的图片" in errors.extraction_warning(
        "Images found:        0\nFaces detected:      0")


# Presets
def test_presets_cover_all_sections():
    """ Each preset defines every section, with identical keys """
    sections = ("extract", "train", "convert")
    for section in sections:
        keys = {name: set(preset[section]) for name, preset in presets.PRESETS.items()}
        assert len(set(map(frozenset, keys.values()))) == 1, section


def test_beginner_is_lighter_than_standard():
    """ 新手模式 uses a lighter model and smaller batches """
    beginner = presets.get_preset(presets.PRESET_BEGINNER, "train")
    standard = presets.get_preset(presets.PRESET_STANDARD, "train")
    assert beginner["trainer"] == "lightweight"
    assert beginner["batch_size"] < standard["batch_size"]


def test_get_preset_fallback_and_copy():
    """ Unknown names fall back to the default; returned dicts are copies """
    vals = presets.get_preset("unknown", "train")
    assert vals == presets.PRESETS[presets.DEFAULT_PRESET]["train"]
    vals["batch_size"] = -1
    assert presets.PRESETS[presets.DEFAULT_PRESET]["train"]["batch_size"] != -1


def test_preset_values_are_valid_choices():
    """ Preset values must be selectable in the UI """
    choices = {"detector": presets.DETECTORS, "aligner": presets.ALIGNERS,
               "masker": presets.MASKERS, "trainer": presets.TRAINERS,
               "writer": presets.WRITERS, "color_adjustment": presets.COLOR_ADJUSTMENTS,
               "mask_type": presets.MASK_TYPES}
    for preset in presets.PRESETS.values():
        for section in preset.values():
            for key, valid in choices.items():
                if key in section:
                    assert section[key] in valid, key


def test_choices_match_plugins():
    """ The hard coded choice lists only contain plugins that exist """
    loader = pytest.importorskip("plugins.plugin_loader").PluginLoader
    real = presets.AUTO
    assert set(presets.DETECTORS) - {real} <= set(loader.get_available_extractors("detect"))
    assert set(presets.ALIGNERS) - {real} <= set(loader.get_available_extractors("align"))
    assert set(presets.MASKERS) - {"none"} <= set(loader.get_available_extractors("mask"))
    assert set(presets.TRAINERS) == set(loader.get_available_models())
    assert set(presets.COLOR_ADJUSTMENTS) <= set(
        loader.get_available_convert_plugins("color", True))
    assert set(presets.WRITERS) - {real} <= set(
        loader.get_available_convert_plugins("writer", False))


# Recent paths
def test_recent_paths_roundtrip(tmp_path):
    """ Values are de-duplicated, most recent first, capped and persisted """
    store = RecentPaths(str(tmp_path), max_items=3)
    for value in ("/a", "/b", "/a", "/c", "/d", "  ", None):
        store.add("faces", value)
    assert store.get("faces") == ["/d", "/c", "/a"]
    assert store.last("faces") == "/d"
    assert store.last("other") == ""
    store.preset = presets.PRESET_STANDARD
    reloaded = RecentPaths(str(tmp_path))
    assert reloaded.get("faces") == ["/d", "/c", "/a"]
    assert reloaded.preset == presets.PRESET_STANDARD


def test_recent_paths_add_many_and_unicode(tmp_path):
    """ add_many saves once and keeps non-ASCII paths readable """
    store = RecentPaths(str(tmp_path))
    store.add_many({"model": "/模型/甲", "faces": '"/素材 A"'})
    with open(os.path.join(str(tmp_path), FILENAME), encoding="utf-8") as handle:
        raw = handle.read()
    assert "/模型/甲" in raw
    assert json.loads(raw)["paths"]["faces"] == ["/素材 A"]


def test_recent_paths_corrupt_file(tmp_path):
    """ A corrupt file is ignored rather than crashing the UI """
    with open(os.path.join(str(tmp_path), FILENAME), "w", encoding="utf-8") as handle:
        handle.write("{not json")
    store = RecentPaths(str(tmp_path))
    assert store.get("faces") == []
    store.add("faces", "/x")
    assert RecentPaths(str(tmp_path)).get("faces") == ["/x"]


def test_user_config_dir_override(monkeypatch, tmp_path):
    """ The environment variable overrides the platform folder """
    monkeypatch.setenv(CONFIG_ENV, str(tmp_path))
    assert user_config_dir() == str(tmp_path)
    monkeypatch.delenv(CONFIG_ENV)
    assert user_config_dir().endswith("faceswap-simple-gui")


def test_workspace_layout_and_create(tmp_path):
    """ The work folder layout is created and remembered """
    from simple_gui import history, workspace
    assert workspace.layout("") == {} and workspace.create("")
    work = tmp_path / "fs"
    assert not workspace.create(f' "{work}" ')
    paths = workspace.layout(str(work))
    assert paths["faces_b"] == str(work / "facesB") and paths["result"].endswith("result.mp4")
    assert (work / "A").is_dir() and (work / "model").is_dir()
    store = history.RecentPaths(str(tmp_path / "cfg"))
    store.workdir = f'"{work}"'
    assert history.RecentPaths(str(tmp_path / "cfg")).workdir == str(work)
