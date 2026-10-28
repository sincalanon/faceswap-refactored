#!/usr/bin/env python3
""" Path helpers for the simple GUI: repository locations, media detection and the per-user
configuration folder. """
from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
"""str : The root folder of the Faceswap repository (where ``faceswap.py`` lives) """

FACESWAP_SCRIPT = os.path.join(REPO_ROOT, "faceswap.py")
TOOLS_SCRIPT = os.path.join(REPO_ROOT, "tools.py")

TRAINING_PREVIEW = os.path.join(REPO_ROOT, "training_preview.png")
""" str : Where ``faceswap.py train --write-image`` saves its preview. The trainer writes it to
the folder that contains the launched script, which is always :attr:`REPO_ROOT` here. """

# Mirrors lib.utils.IMAGE_EXTENSIONS and lib.video.VIDEO_EXTENSIONS. Copied rather than imported
# so that this module stays importable without the heavy Faceswap dependencies.
IMAGE_EXTENSIONS = (".bmp", ".exr", ".jpeg", ".jpg", ".png", ".tif", ".tiff")
VIDEO_EXTENSIONS = (".avi", ".flv", ".mkv", ".mov", ".mp4", ".mpeg", ".mpg", ".webm", ".wmv",
                    ".ts", ".vob")

APP_DIR_NAME = "faceswap-simple-gui"
CONFIG_ENV = "FACESWAP_SIMPLE_GUI_CONFIG_DIR"


def user_config_dir() -> str:
    """ Return the per-user configuration folder for the simple GUI (not created here).

    The environment variable ``FACESWAP_SIMPLE_GUI_CONFIG_DIR`` overrides the platform default.
    """
    override = os.environ.get(CONFIG_ENV)
    if override:
        return override
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, APP_DIR_NAME)


def clean_path(path: str | None) -> str:
    """ Normalise a path typed or pasted by a user: strip whitespace and surrounding quotes
    (Windows "Copy as path" adds them) and expand ``~``. Returns an empty string for nothing. """
    if not path:
        return ""
    path = str(path).strip().strip('"').strip("'").strip()
    return os.path.expanduser(path) if path else ""


def is_video(path: str) -> bool:
    """ ``True`` if the given path has a video file extension """
    return os.path.splitext(path)[-1].lower() in VIDEO_EXTENSIONS


def media_path(path: str | None) -> str:
    """ Clean a media input path. A folder that holds no images but exactly one video is taken
    to mean that video, so users can simply point at e.g. ``D:\\fs\\A`` with ``A.mp4`` inside. """
    path = clean_path(path)
    if not path or not os.path.isdir(path) or count_images(path) > 0:
        return path
    videos = sorted(name for name in os.listdir(path)
                    if is_video(name) and os.path.isfile(os.path.join(path, name)))
    return os.path.join(path, videos[0]) if len(videos) == 1 else path


def count_images(folder: str) -> int:
    """ Count the images directly inside a folder. Returns 0 if it is not a folder. """
    if not os.path.isdir(folder):
        return 0
    return sum(1 for fname in os.listdir(folder)
               if os.path.splitext(fname)[-1].lower() in IMAGE_EXTENSIONS)


def has_model(folder: str) -> bool:
    """ ``True`` if the folder holds exactly one Faceswap model (one ``*_state.json`` file),
    which is what ``faceswap.py convert`` requires. """
    if not os.path.isdir(folder):
        return False
    states = [fname for fname in os.listdir(folder) if fname.endswith("_state.json")]
    return len(states) == 1
