#!/usr/bin/env python3
""" Pytest unit tests for the stand-alone helpers in :mod:`lib.image` """
import os

import cv2
import numpy as np
import pytest

from lib.image import (batch_convert_color, encode_image, generate_thumbnail, hex_to_rgb,
                       read_image, read_image_batch, read_image_meta, rgb_to_hex)


def _write(path: str, image: np.ndarray) -> str:
    """ Write an image to disk with OpenCV and return the path """
    assert cv2.imwrite(path, image)
    return path


@pytest.fixture(name="bgr_png")
def fixture_bgr_png(tmp_path: str) -> tuple[str, np.ndarray]:
    """ A random 3 channel UINT8 png """
    image = np.random.randint(0, 255, (32, 48, 3), dtype=np.uint8)
    return _write(os.path.join(tmp_path, "img.png"), image), image


def test_read_image_bgr(bgr_png: tuple[str, np.ndarray]) -> None:
    """ A standard BGR image is returned unchanged """
    path, image = bgr_png
    out = read_image(path, raise_error=True)
    assert out.dtype == np.uint8
    np.testing.assert_array_equal(out, image)


def test_read_image_gray_to_bgr(tmp_path: str) -> None:
    """ Grayscale images are expanded to 3 channel BGR """
    image = np.random.randint(0, 255, (16, 16), dtype=np.uint8)
    out = read_image(_write(os.path.join(tmp_path, "g.png"), image), raise_error=True)
    assert out.shape == (16, 16, 3)
    np.testing.assert_array_equal(out[..., 0], image)


def test_read_image_bgra_keeps_alpha(tmp_path: str) -> None:
    """ 4 channel images are currently returned with their alpha channel (existing behaviour) """
    image = np.random.randint(0, 255, (16, 16, 4), dtype=np.uint8)
    out = read_image(_write(os.path.join(tmp_path, "a.png"), image), raise_error=True)
    assert out.shape == (16, 16, 4)


def test_read_image_uint16_scaled(tmp_path: str) -> None:
    """ 16 bit images are scaled down to UINT8 """
    image = np.full((8, 8, 3), 65535, dtype=np.uint16)
    out = read_image(_write(os.path.join(tmp_path, "w.png"), image), raise_error=True)
    assert out.dtype == np.uint8
    assert np.all(out == 255)


def test_read_image_missing(tmp_path: str) -> None:
    """ Missing files return ``None`` or raise, depending on `raise_error` """
    path = os.path.join(tmp_path, "missing.png")
    assert read_image(path, raise_error=False) is None
    with pytest.raises(Exception):
        read_image(path, raise_error=True)


def test_read_image_corrupt(tmp_path: str) -> None:
    """ Undecodable files raise ValueError when `raise_error` is ``True`` """
    path = os.path.join(tmp_path, "bad.png")
    with open(path, "wb") as bad:
        bad.write(b"not an image")
    assert read_image(path) is None
    with pytest.raises(ValueError):
        read_image(path, raise_error=True)


def test_read_image_batch(tmp_path: str) -> None:
    """ Batches are returned in filename order """
    images = [np.full((8, 8, 3), i * 10, dtype=np.uint8) for i in range(5)]
    paths = [_write(os.path.join(tmp_path, f"{i}.png"), img) for i, img in enumerate(images)]
    batch = read_image_batch(paths)
    assert batch.shape == (5, 8, 8, 3)
    for idx, img in enumerate(images):
        np.testing.assert_array_equal(batch[idx], img)


def test_read_image_meta_dimensions(bgr_png: tuple[str, np.ndarray], tmp_path: str) -> None:
    """ Width and height are read for png (header) and non-png (decoded) files """
    path, image = bgr_png
    assert read_image_meta(path) == {"width": image.shape[1], "height": image.shape[0]}
    jpg = _write(os.path.join(tmp_path, "img.jpg"), image)
    assert read_image_meta(jpg) == {"width": image.shape[1], "height": image.shape[0]}


def test_generate_thumbnail() -> None:
    """ Thumbnails are jpg encoded at the requested size """
    image = np.random.randint(0, 255, (128, 128, 3), dtype=np.uint8)
    thumb = generate_thumbnail(image, size=32, quality=50)
    decoded = cv2.imdecode(thumb, cv2.IMREAD_UNCHANGED)
    assert decoded.shape == (32, 32, 3)


def test_batch_convert_color() -> None:
    """ Batch conversion matches per-image conversion """
    batch = np.random.randint(0, 255, (4, 8, 8, 3), dtype=np.uint8)
    out = batch_convert_color(batch, "BGR2RGB")
    np.testing.assert_array_equal(out, batch[..., ::-1])


@pytest.mark.parametrize("hex_code, rgb", [("#000000", (0, 0, 0)),
                                           ("#ff8000", (255, 128, 0)),
                                           ("0d25ac", (13, 37, 172))])
def test_hex_rgb_round_trip(hex_code: str, rgb: tuple[int, int, int]) -> None:
    """ Hex and RGB conversions are inverse operations """
    assert hex_to_rgb(hex_code) == rgb
    assert rgb_to_hex(rgb) == f"#{hex_code.lstrip('#')}"


def test_encode_image_png(bgr_png: tuple[str, np.ndarray]) -> None:
    """ encode_image produces decodable bytes """
    _, image = bgr_png
    encoded = encode_image(image, ".png")
    decoded = cv2.imdecode(np.frombuffer(encoded, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    np.testing.assert_array_equal(decoded, image)
