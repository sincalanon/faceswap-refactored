#!/usr/bin/env python3
""" A fixed folder layout under one "工作文件夹" so every path box can be filled automatically.

::

    <工作文件夹>\\A\\        A 的素材（放 1 个视频，或若干张照片）
    <工作文件夹>\\B\\        B 的素材
    <工作文件夹>\\facesA\\   提取出的 A 人脸
    <工作文件夹>\\facesB\\   提取出的 B 人脸
    <工作文件夹>\\model\\    训练的模型
    <工作文件夹>\\output\\   转换结果
    <工作文件夹>\\frames\\   视频工具：拆出的图片
    <工作文件夹>\\result.mp4 视频工具：合成的视频
"""
from __future__ import annotations

import logging
import os

from .paths import clean_path

logger = logging.getLogger(__name__)

FOLDERS = {"src_a": "A", "src_b": "B", "faces_a": "facesA", "faces_b": "facesB",
           "model": "model", "output": "output", "frames": "frames"}
RESULT_VIDEO = "result.mp4"


def layout(workdir: str | None) -> dict[str, str]:
    """ Every path of the layout for a work folder, or an empty dict when none is set """
    workdir = clean_path(workdir)
    if not workdir:
        return {}
    paths = {key: os.path.join(workdir, name) for key, name in FOLDERS.items()}
    paths["result"] = os.path.join(workdir, RESULT_VIDEO)
    return paths


def create(workdir: str | None) -> list[str]:
    """ Create the work folder and its sub folders. Returns error messages (Chinese). """
    paths = layout(workdir)
    if not paths:
        return ["请先填写「工作文件夹」，例如 D:\\fs"]
    try:
        for key in FOLDERS:
            os.makedirs(paths[key], exist_ok=True)
    except OSError as err:
        logger.warning("Could not create work folder: %s", err)
        return [f"无法创建文件夹：{err}。请换一个位置（例如 D:\\fs），不要用系统保护的目录。"]
    return []
