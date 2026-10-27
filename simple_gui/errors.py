#!/usr/bin/env python3
""" Turn Faceswap's console output and exit codes into friendly Chinese messages. """
from __future__ import annotations

import re
import typing as T

_FFMPEG_MSG = ("找不到 ffmpeg。处理视频需要 ffmpeg：请执行 `pip install ffmpeg-binaries`，"
               "或安装系统 ffmpeg（Linux: `sudo apt install ffmpeg`；"
               "macOS: `brew install ffmpeg`）。")

# (pattern, message). Checked in order against the job's log; the first match wins, so the most
# specific patterns come first. Patterns are matched case-insensitively.
_RULES: list[tuple[str, str]] = [
    (r"out of memory|OutOfMemoryError|CUDNN_STATUS_ALLOC_FAILED|Unable to allocate|"
     r"\bMemoryError\b|DefaultCPUAllocator: can't allocate",
     "内存或显存不足（Out of memory）。请在「高级设置」中减小批大小（Batch Size），"
     "换用更轻量的模型（如 lightweight），或关闭其他占用显卡/内存的程序后重试。"),
    (r"CUDA (driver|error|is not available)|no CUDA-capable device|"
     r"Torch not compiled with CUDA|Found no NVIDIA driver|nvml.*(error|not found)|"
     r"No GPU detected|ROCm.*not (found|available)",
     "无法使用显卡（GPU/CUDA 不可用）。请确认已安装与显卡匹配的驱动和对应版本的 Faceswap"
     "（运行 setup.py 选择 nvidia/rocm），或用 CPU 版本运行（会慢很多）。"),
    (r"No such file or directory: '?[^']*ffmpeg|FileNotFoundError.*ffmpeg|"
     r"NoneType.*ffmpeg|ffmpeg (executable )?not found",
     _FFMPEG_MSG),
    (r"Failed to download model|URLError|ConnectionError|Max retries exceeded|"
     r"Temporary failure in name resolution",
     "下载模型文件失败。首次运行提取/转换时需要联网下载插件模型，请检查网络或代理后重试。"),
    (r"contains fewer than 25 images",
     "训练用的人脸太少：每一边至少需要 25 张，建议 500 - 5000 张。"
     "请先用「提取」从更多照片或视频中提取人脸。"),
    (r"contains images that are not extracted faces",
     "训练文件夹里有不是由 Faceswap「提取」生成的图片。请只使用提取步骤输出的人脸文件夹。"),
    (r"contains no images",
     "选择的文件夹里没有图片。请检查路径是否正确。"),
    (r"Model could not be found in folder|There should be 1 state file|"
     r"Trainer name could not be read",
     "在模型文件夹中找不到训练好的模型。请先完成「训练」，或选择训练时使用的模型文件夹。"),
    (r"No alignments file found|alignments file.*(not found|does not exist)",
     "找不到对齐文件（alignments）。转换前需要先对同一份原始素材运行「提取」，"
     "或在「高级设置」中指定对齐文件路径。"),
    (r"Aligned directory is empty|no faces will be converted",
     "没有可转换的人脸：对齐文件夹为空。"),
    (r"does not exist|No such file or directory|FileNotFoundError",
     "找不到指定的文件或文件夹，请检查路径是否填写正确。"),
    (r"Permission denied|PermissionError",
     "没有权限读写该路径。请换一个有写入权限的输出文件夹。"),
    (r"No space left on device",
     "磁盘空间不足，请清理磁盘或换一个输出位置。"),
    (r"invalid choice|unrecognized arguments|the following arguments are required",
     "参数无效。请检查填写的参数，或恢复为预设的默认值。"),
    # Only a warning at import time, so it is checked after everything more specific
    (r"ffmpeg binaries not found", _FFMPEG_MSG),
    (r"ModuleNotFoundError|No module named",
     "缺少 Python 依赖。请按 INSTALL.md 安装 Faceswap 依赖后重试"
     "（例如 `pip install -r requirements/requirements_cpu.txt`）。"),
]
_COMPILED = [(re.compile(pattern, re.IGNORECASE), msg) for pattern, msg in _RULES]

_CRASH = re.compile(r"Crash report written to '([^']+)'")
_NO_FACES = re.compile(r"Faces detected:\s+0\b")
_IMAGES_FOUND = re.compile(r"Images found:\s+(\d+)")

EXIT_CODE_MESSAGES: dict[int, str] = {
    1: "任务失败（退出码 1）。请查看下方日志中的 ERROR 行了解原因。",
    -9: "任务被系统强制结束（可能是内存不足）。请减小批大小或关闭其他程序后重试。",
    137: "任务被系统强制结束（可能是内存不足）。请减小批大小或关闭其他程序后重试。",
    -11: "程序崩溃（段错误）。请检查依赖安装是否完整，必要时重新安装。",
}


def explain_failure(log_text: str, return_code: int | None) -> str:
    """ Return a friendly Chinese explanation for a failed job.

    Parameters
    ----------
    log_text
        The job's combined stdout/stderr
    return_code
        The process exit code (``None`` if unknown)
    """
    message = _match_rules(log_text, return_code)
    crash = _CRASH.search(log_text)
    if crash:
        message += (f"\n\n程序意外崩溃，崩溃报告已保存到：`{crash.group(1)}`"
                    "（求助时请附上该文件）。")
    return message


def _match_rules(log_text: str, return_code: int | None) -> str:
    """ The message of the first matching rule, else one based on the exit code """
    for regex, message in _COMPILED:
        if regex.search(log_text):
            return message
    if return_code in EXIT_CODE_MESSAGES:
        return EXIT_CODE_MESSAGES[T.cast(int, return_code)]
    if return_code is None:
        return "任务异常结束，请查看下方日志。"
    return f"任务失败（退出码 {return_code}）。请查看下方日志了解原因。"


def extraction_warning(log_text: str) -> str:
    """ Return a Chinese warning when a finished extraction found no faces, else ``""`` """
    if not _NO_FACES.search(log_text):
        return ""
    found = _IMAGES_FOUND.search(log_text)
    if found and found.group(1) == "0":
        return "没有找到可处理的图片或视频帧。请确认输入路径里有 jpg/png 图片或视频文件。"
    return ("提取完成，但没有检测到任何人脸。请换用正脸清晰、光线充足的素材，"
            "或在「高级设置」中更换检测器（如 s3fd）后重试。")
