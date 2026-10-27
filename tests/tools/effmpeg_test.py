#!/usr/bin/env python3
""" Pytest unit tests for :mod:`tools.effmpeg.effmpeg` helpers """
import pytest

from tools.effmpeg.effmpeg import Effmpeg


@pytest.mark.parametrize("filename,expected", [
    ("test.mp4_00001", 5), ("frame12", 2), ("nodigits", 0), ("00042", 5)])
def test_get_zero_pad(filename, expected):
    """ The zero padding length is the count of trailing digits (used by gen-vid to build the
    ffmpeg input pattern, e.g. ``test.mp4_%5d.png``) """
    assert Effmpeg._Effmpeg__get_zero_pad(filename) == expected  # pylint:disable=protected-access
