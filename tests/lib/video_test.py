#!/usr/bin/env python3
""" Pytest unit tests for :func:`lib.video.count_frames` and its FFmpeg output parsers """
import io
import subprocess
import typing as T

import pytest
import pytest_mock

from lib import video

_FFMPEG_OUTPUT = """ffmpeg version 6.0 Copyright (c) 2000-2023 the FFmpeg developers
Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'test.mp4':
  Duration: 00:01:05.00, start: 0.000000, bitrate: 1205 kb/s
frame=  250 fps=0.0 q=-0.0 size=N/A time=00:00:10.00 bitrate=N/A speed=20x
frame= 1625 fps=0.0 q=-0.0 Lsize=N/A time=00:01:05.00 bitrate=N/A speed=22x
"""


class _FakePopen:
    """ Minimal stand-in for :class:`subprocess.Popen` that replays canned FFmpeg output """
    def __init__(self, cmd: list[str], **kwargs: T.Any) -> None:
        self.cmd = cmd
        self.kwargs = kwargs
        self.stdout = io.StringIO(_FFMPEG_OUTPUT)
        self.returncode: int | None = None

    def poll(self) -> int | None:
        """ Finished once all output has been consumed """
        if self.stdout.tell() == len(_FFMPEG_OUTPUT):
            self.returncode = 0
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:  # pylint:disable=unused-argument
        """ Wait for the process """
        return 0

    def __enter__(self) -> "_FakePopen":
        return self

    def __exit__(self, *args: T.Any) -> None:
        self.stdout.close()


@pytest.mark.parametrize("fast", [True, False])
def test_count_frames(mocker: pytest_mock.MockerFixture, fast: bool) -> None:
    """ count_frames returns the final frame count reported by FFmpeg """
    calls: list[_FakePopen] = []

    def _popen(cmd: list[str], **kwargs: T.Any) -> _FakePopen:
        proc = _FakePopen(cmd, **kwargs)
        calls.append(proc)
        return proc

    mocker.patch.object(subprocess, "Popen", side_effect=_popen)
    mocker.patch.object(video.ffmpeg, "FFMPEG_PATH", "/usr/bin/ffmpeg")
    assert video.count_frames("test.mp4", fast=fast) == 1625
    assert len(calls) == 1
    assert ("-c" in calls[0].cmd) is fast
    assert calls[0].cmd[:3] == ["/usr/bin/ffmpeg", "-i", "test.mp4"]


def test_parse_ffmpeg_duration() -> None:
    """ Duration lines are parsed to whole seconds """
    parse = getattr(video, "_parse_ffmpeg_duration")
    assert parse("Duration: 00:01:05.00, start: 0.000000, bitrate: 1205 kb/s") == 65
    assert parse("Duration: 01:00:00.50, start: 0.0") == 3600


def test_parse_ffmpeg_progress() -> None:
    """ Progress lines are parsed to (frames, seconds) """
    parse = getattr(video, "_parse_ffmpeg_progress")
    assert parse("frame=  250 fps=0.0 q=-0.0 size=N/A time=00:00:10.00 bitrate=N/A") == (250, 10)
    assert parse("frame=1625 fps=0.0 q=-0.0 Lsize=N/A time=00:01:05.00 bitrate=N/A") == (1625, 65)
