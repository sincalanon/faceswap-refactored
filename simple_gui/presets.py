#!/usr/bin/env python3
""" Presets (新手模式 / 标准模式) and the choice lists shown in the simple GUI.

A preset is only a set of default values for the visible and advanced fields. Anything the
preset does not mention keeps Faceswap's own default because the argument is simply not passed.
"""
from __future__ import annotations

import typing as T

AUTO = "auto"
""" Sentinel meaning "don't pass this option, let Faceswap decide" """

# Choice lists. Kept in sync with plugins.plugin_loader by tests/simple_gui/presets_test.py
DETECTORS = [AUTO, "s3fd", "retinaface", "mtcnn", "cv2-dnn"]
ALIGNERS = [AUTO, "fan", "hrnet", "cv2-dnn"]
MASKERS = ["none", "bisenet-fp", "vgg-clear", "vgg-obstructed", "unet-dfl"]
TRAINERS = ["lightweight", "original", "dfaker", "dfl-h128", "dfl-sae", "dlight", "iae",
            "phaze-a", "realface", "unbalanced", "villain"]
COLOR_ADJUSTMENTS = ["avg-color", "color-transfer", "match-hist", "manual-balance",
                     "seamless-clone", "none"]
MASK_TYPES = ["extended", "components", "none", "predicted"]
WRITERS = [AUTO, "opencv", "ffmpeg", "pillow", "gif"]

PRESET_BEGINNER = "新手模式"
PRESET_STANDARD = "标准模式"

PRESETS: dict[str, dict[str, dict[str, T.Any]]] = {
    PRESET_BEGINNER: {
        # Fewer frames from a video, a light model, small batches and frequent saves: quick
        # results that run on modest hardware.
        "extract": {"detector": AUTO, "aligner": AUTO, "masker": "none", "size": 512,
                    "extract_every_n": 5, "min_size": 0, "skip_existing": False},
        "train": {"trainer": "lightweight", "batch_size": 8, "iterations": 20000,
                  "save_interval": 250, "write_preview": True, "warp_to_landmarks": False,
                  "no_flip": False, "no_augment_color": False},
        "convert": {"writer": AUTO, "color_adjustment": "avg-color", "mask_type": "extended",
                    "output_scale": 100, "swap_model": False},
    },
    PRESET_STANDARD: {
        # Faceswap's own defaults: every frame, the Original model and the default batch size.
        "extract": {"detector": AUTO, "aligner": AUTO, "masker": "none", "size": 512,
                    "extract_every_n": 1, "min_size": 0, "skip_existing": False},
        "train": {"trainer": "original", "batch_size": 16, "iterations": 100000,
                  "save_interval": 250, "write_preview": True, "warp_to_landmarks": False,
                  "no_flip": False, "no_augment_color": False},
        "convert": {"writer": AUTO, "color_adjustment": "avg-color", "mask_type": "extended",
                    "output_scale": 100, "swap_model": False},
    },
}

DEFAULT_PRESET = PRESET_BEGINNER


def get_preset(name: str | None, section: str) -> dict[str, T.Any]:
    """ Return a copy of a preset's defaults for one section (extract, train or convert).

    Unknown preset names fall back to :data:`DEFAULT_PRESET`. Unknown sections raise
    ``KeyError`` because that is a programming error.
    """
    preset = PRESETS.get(name or "", PRESETS[DEFAULT_PRESET])
    return dict(preset[section])
