#!/usr/bin/env python3
""" Pytest unit tests for :mod:`lib.serializer` """
import os

import numpy as np
import pytest

from lib import serializer as serializer_mod
from lib.serializer import get_serializer, get_serializer_from_filename, Serializer
from lib.utils import FaceswapError

_DATA = {"a": [1, 2, 3], "b": "text", "c": {"nested": 1.5}}


@pytest.mark.parametrize("name, ext", [("json", "json"),
                                       ("pickle", "pickle"),
                                       ("npy", "npy"),
                                       ("compressed", "fsa")])
def test_get_serializer(name: str, ext: str) -> None:
    """ Each named serializer is returned as an instance with the correct extension """
    serializer = get_serializer(name)  # type:ignore[arg-type]
    assert isinstance(serializer, Serializer)
    assert serializer.file_extension == ext


def test_get_serializer_case_insensitive() -> None:
    """ Serializer names are case insensitive """
    assert get_serializer("JSON").file_extension == "json"  # type:ignore[arg-type]


def test_get_serializer_unknown_returns_json() -> None:
    """ An unknown serializer name returns a JSON serializer instance (not ``None``) """
    serializer = get_serializer("not-a-format")  # type:ignore[arg-type]
    assert isinstance(serializer, Serializer)
    assert serializer.file_extension == "json"


def test_get_serializer_yaml_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """ YAML without PyYAML installed falls back to a JSON serializer *instance* """
    monkeypatch.setattr(serializer_mod, "_HAS_YAML", False)
    for serializer in (get_serializer("yaml"), get_serializer_from_filename("file.yml")):
        assert isinstance(serializer, Serializer)
        assert serializer.file_extension == "json"


@pytest.mark.parametrize("filename, ext", [("x.json", "json"),
                                           ("x.p", "pickle"),
                                           ("x.PICKLE", "pickle"),
                                           ("x.npy", "npy"),
                                           ("x.fsa", "fsa"),
                                           ("x.unknown", "json"),
                                           ("no_extension", "json")])
def test_get_serializer_from_filename(filename: str, ext: str) -> None:
    """ Serializers are selected from the file extension, defaulting to JSON """
    assert get_serializer_from_filename(filename).file_extension == ext


@pytest.mark.parametrize("name", ["json", "pickle", "compressed"])
def test_round_trip(name: str, tmp_path: str) -> None:
    """ Data saved to disk is loaded back unchanged """
    serializer = get_serializer(name)  # type:ignore[arg-type]
    filename = os.path.join(tmp_path, f"data.{serializer.file_extension}")
    serializer.save(filename, _DATA)
    assert serializer.load(filename) == _DATA
    assert serializer.unmarshal(serializer.marshal(_DATA)) == _DATA


def test_npy_round_trip() -> None:
    """ Numpy arrays survive marshalling """
    serializer = get_serializer("npy")
    arr = np.arange(12, dtype="float32").reshape(3, 4)
    np.testing.assert_array_equal(serializer.unmarshal(serializer.marshal(arr)), arr)


def test_save_adds_extension(tmp_path: str) -> None:
    """ Saving to a filename without an extension appends the serializer's extension """
    serializer = get_serializer("json")
    filename = os.path.join(tmp_path, "data")
    serializer.save(filename, _DATA)
    assert os.path.isfile(f"{filename}.json")


def test_errors_are_wrapped(tmp_path: str) -> None:
    """ IO and (un)marshalling errors are raised as :class:`FaceswapError` """
    serializer = get_serializer("json")
    with pytest.raises(FaceswapError):
        serializer.load(os.path.join(tmp_path, "missing.json"))
    with pytest.raises(FaceswapError):
        serializer.marshal({"bad": object()})
    with pytest.raises(FaceswapError):
        serializer.unmarshal(b"{not json")
