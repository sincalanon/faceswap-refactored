#!/usr/bin/env python3
""" Build and validate the command lines for the simple GUI.

Each job is described by a small dataclass holding only the options the simple GUI exposes.
:func:`build_command` turns it into the argument list for ``faceswap.py`` (or ``tools.py``),
and :func:`validate` returns friendly Chinese messages for anything that would obviously fail
before a process is launched.
"""
from __future__ import annotations

import os
import sys
import typing as T
from dataclasses import dataclass

from .paths import (FACESWAP_SCRIPT, TOOLS_SCRIPT, clean_path, count_images, has_model,
                    is_video)
from .presets import AUTO

MIN_TRAIN_IMAGES = 25
""" int : ``faceswap.py train`` exits when a side has fewer images than this """


@dataclass
class ExtractOptions:
    """ Options for ``faceswap.py extract`` """
    input_path: str
    output_dir: str
    detector: str = AUTO
    aligner: str = AUTO
    masker: str = "none"
    size: int = 512
    extract_every_n: int = 1
    min_size: int = 0
    skip_existing: bool = False
    batch_mode: bool = False
    command: T.ClassVar[str] = "extract"


@dataclass
class TrainOptions:
    """ Options for ``faceswap.py train`` """
    input_a: str
    input_b: str
    model_dir: str
    trainer: str = "original"
    batch_size: int = 16
    iterations: int = 100000
    save_interval: int = 250
    write_preview: bool = True
    warp_to_landmarks: bool = False
    no_flip: bool = False
    no_augment_color: bool = False
    command: T.ClassVar[str] = "train"


@dataclass
class ConvertOptions:
    """ Options for ``faceswap.py convert`` """
    input_path: str
    output_dir: str
    model_dir: str
    alignments: str = ""
    writer: str = AUTO
    color_adjustment: str = "avg-color"
    mask_type: str = "extended"
    output_scale: int = 100
    swap_model: bool = False
    command: T.ClassVar[str] = "convert"


@dataclass
class VideoOptions:
    """ Options for the ``tools.py effmpeg`` video shortcuts.

    action is ``extract`` (video -> frames) or ``gen-vid`` (frames -> video). For ``gen-vid``
    ``reference_video`` supplies the frame rate (and audio when ``mux_audio`` is set); without
    one, ``fps`` is used.
    """
    action: str
    input_path: str
    output_path: str
    reference_video: str = ""
    mux_audio: bool = False
    fps: float = 25.0
    command: T.ClassVar[str] = "effmpeg"


JobOptions = ExtractOptions | TrainOptions | ConvertOptions | VideoOptions


def _base(script: str, command: str) -> list[str]:
    """ The interpreter, script and sub-command. ``-u`` keeps the output unbuffered so the
    log streams live. """
    return [sys.executable, "-u", script, command]


def _choice(flag: str, value: str, skip: tuple[str, ...] = (AUTO,)) -> list[str]:
    """ Return ``[flag, value]`` unless the value is empty or one of the skip values """
    return [] if not value or value in skip else [flag, value]


def _number(flag: str, value: int | float, default: int | float) -> list[str]:
    """ Return ``[flag, value]`` only when the value differs from Faceswap's default """
    return [] if value is None or int(value) == default else [flag, str(int(value))]


def _flag(flag: str, enabled: bool) -> list[str]:
    """ Return ``[flag]`` when enabled """
    return [flag] if enabled else []


def build_extract(opts: ExtractOptions) -> list[str]:
    """ Build the ``faceswap.py extract`` command line """
    return (_base(FACESWAP_SCRIPT, "extract")
            + ["-i", clean_path(opts.input_path), "-o", clean_path(opts.output_dir)]
            + _choice("-D", opts.detector)
            + _choice("-A", opts.aligner)
            + _choice("-M", opts.masker, skip=(AUTO, "none"))
            + _number("-z", opts.size, 512)
            + _number("-N", opts.extract_every_n, 1)
            + _number("-m", opts.min_size, 0)
            + _flag("-s", opts.skip_existing)
            + _flag("-b", opts.batch_mode))


def build_train(opts: TrainOptions) -> list[str]:
    """ Build the ``faceswap.py train`` command line """
    return (_base(FACESWAP_SCRIPT, "train")
            + ["-A", clean_path(opts.input_a), "-B", clean_path(opts.input_b),
               "-m", clean_path(opts.model_dir)]
            + _choice("-t", opts.trainer)
            + ["-b", str(int(opts.batch_size)), "-i", str(int(opts.iterations))]
            + _number("-s", opts.save_interval, 250)
            + _flag("-w", opts.write_preview)
            + _flag("-M", opts.warp_to_landmarks)
            + _flag("-P", opts.no_flip)
            + _flag("-c", opts.no_augment_color))


def resolve_writer(writer: str, input_path: str) -> str:
    """ Pick the converter writer. ``auto`` writes a video for a video input (ffmpeg) and
    images otherwise (opencv). """
    if writer and writer != AUTO:
        return writer
    return "ffmpeg" if is_video(clean_path(input_path)) else "opencv"


def build_convert(opts: ConvertOptions) -> list[str]:
    """ Build the ``faceswap.py convert`` command line """
    return (_base(FACESWAP_SCRIPT, "convert")
            + ["-i", clean_path(opts.input_path), "-o", clean_path(opts.output_dir),
               "-m", clean_path(opts.model_dir)]
            + _choice("-p", clean_path(opts.alignments))
            + ["-w", resolve_writer(opts.writer, opts.input_path)]
            + _choice("-c", opts.color_adjustment, skip=(AUTO, "avg-color"))
            + _choice("-M", opts.mask_type, skip=(AUTO, "extended"))
            + _number("-O", opts.output_scale, 100)
            + _flag("-s", opts.swap_model))


def build_video(opts: VideoOptions) -> list[str]:
    """ Build the ``tools.py effmpeg`` command line """
    args = (_base(TOOLS_SCRIPT, "effmpeg")
            + ["-a", opts.action, "-i", clean_path(opts.input_path),
               "-o", clean_path(opts.output_path)])
    if opts.action != "gen-vid":
        return args
    reference = clean_path(opts.reference_video)
    if reference:
        return args + ["-r", reference] + _flag("-m", opts.mux_audio)
    return args + ["-R", f"{float(opts.fps or 25.0):g}"]


def build_command(opts: JobOptions) -> list[str]:
    """ Build the full command line for any supported job """
    builders: dict[str, T.Callable[[T.Any], list[str]]] = {
        "extract": build_extract, "train": build_train, "convert": build_convert,
        "effmpeg": build_video}
    return builders[opts.command](opts)


# Validation
def _require(path: str, label: str) -> list[str]:
    """ Error if a required path is empty or does not exist """
    path = clean_path(path)
    if not path:
        return [f"请填写「{label}」。"]
    if not os.path.exists(path):
        return [f"「{label}」不存在：{path}"]
    return []


def _require_value(value: str, label: str) -> list[str]:
    """ Error if a required (output) path is empty """
    return [] if clean_path(value) else [f"请填写「{label}」。"]


def _check_faces_folder(path: str, label: str) -> list[str]:
    """ Errors for a training face folder """
    errors = _require(path, label)
    if errors:
        return errors
    path = clean_path(path)
    if not os.path.isdir(path):
        return [f"「{label}」应该是一个文件夹（提取步骤输出的人脸文件夹）：{path}"]
    num = count_images(path)
    if num < MIN_TRAIN_IMAGES:
        return [f"「{label}」里只有 {num} 张图片，至少需要 {MIN_TRAIN_IMAGES} 张"
                "（建议 500 - 5000 张）。请先用「提取」从更多素材中提取人脸。"]
    return []


def validate_extract(opts: ExtractOptions) -> list[str]:
    """ Pre-flight checks for extraction """
    return (_require(opts.input_path, "输入（图片文件夹或视频）")
            + _require_value(opts.output_dir, "人脸输出文件夹"))


def validate_train(opts: TrainOptions) -> list[str]:
    """ Pre-flight checks for training """
    errors = (_check_faces_folder(opts.input_a, "人脸 A 文件夹")
              + _check_faces_folder(opts.input_b, "人脸 B 文件夹")
              + _require_value(opts.model_dir, "模型文件夹"))
    if not errors and os.path.realpath(clean_path(opts.input_a)) == os.path.realpath(
            clean_path(opts.input_b)):
        errors.append("人脸 A 和人脸 B 是同一个文件夹，请分别选择两个人的人脸文件夹。")
    if int(opts.batch_size) < 1 or int(opts.iterations) < 1:
        errors.append("批大小和迭代次数都必须大于 0。")
    return errors


def validate_convert(opts: ConvertOptions) -> list[str]:
    """ Pre-flight checks for conversion """
    errors = (_require(opts.input_path, "输入（原图文件夹或视频）")
              + _require_value(opts.output_dir, "输出文件夹")
              + _require(opts.model_dir, "模型文件夹"))
    model_dir = clean_path(opts.model_dir)
    if model_dir and os.path.isdir(model_dir) and not has_model(model_dir):
        errors.append(f"「模型文件夹」里没有找到训练好的模型（*_state.json）：{model_dir}。"
                      "请先完成「训练」，或选择训练时使用的模型文件夹。")
    if clean_path(opts.alignments):
        errors += _require(opts.alignments, "对齐文件")
    return errors


def validate_video(opts: VideoOptions) -> list[str]:
    """ Pre-flight checks for the video shortcuts """
    errors = (_require(opts.input_path, "输入")
              + _require_value(opts.output_path, "输出"))
    if opts.action == "extract" and not errors and not is_video(clean_path(opts.input_path)):
        errors.append("「输入」需要是一个视频文件（如 .mp4）。")
    if opts.action == "gen-vid" and clean_path(opts.reference_video):
        errors += _require(opts.reference_video, "参考视频")
    return errors


def validate(opts: JobOptions) -> list[str]:
    """ Run the pre-flight checks for any supported job """
    validators: dict[str, T.Callable[[T.Any], list[str]]] = {
        "extract": validate_extract, "train": validate_train, "convert": validate_convert,
        "effmpeg": validate_video}
    return validators[opts.command](opts)
