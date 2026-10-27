#!/usr/bin/env python3
""" Run one Faceswap job at a time as a subprocess, collect its log and parse its progress.

Nothing here depends on Gradio, so the UI only polls :meth:`JobRunner.snapshot`.
"""
from __future__ import annotations

import collections
import os
import re
import signal
import subprocess
import threading
import time
import typing as T
from dataclasses import dataclass, field

import psutil

from .errors import explain_failure, extraction_warning
from .paths import REPO_ROOT

IDLE, RUNNING, STOPPING, DONE, FAILED, STOPPED = ("idle", "running", "stopping", "done",
                                                  "failed", "stopped")

STATUS_TEXT = {IDLE: "空闲", RUNNING: "运行中", STOPPING: "正在停止…", DONE: "已完成",
               FAILED: "失败", STOPPED: "已停止"}

_TQDM = re.compile(r"(?P<desc>[^\r\n|]*?):?\s*(?P<pct>\d{1,3})%\|.*?\|\s*"
                   r"(?P<done>\d+)/(?P<total>\d+)\s*\[(?P<elapsed>[^<\]]*)<?(?P<remain>[^,\]]*)")
_LOSS = re.compile(r"\[#(?P<iteration>\d+)\]\s*(?P<loss>Loss.*)$")
_PREVIEW = re.compile(r"\[Preview Updated\]")
_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

TRAIN_STOP_TIMEOUT = 120.0
""" float : Seconds to let the trainer save and exit after a stop request before killing it """


@dataclass
class Progress:
    """ The latest progress parsed from a job's output """
    fraction: float | None = None
    text: str = ""


@dataclass
class Snapshot:
    """ A consistent view of the job for the UI """
    status: str
    log: str
    progress: Progress
    message: str
    command: list[str] = field(default_factory=list)
    return_code: int | None = None
    preview_updated: float = 0.0

    @property
    def running(self) -> bool:
        """ bool : ``True`` while the process is alive """
        return self.status in (RUNNING, STOPPING)


def parse_progress(line: str, iterations: int | None = None) -> Progress | None:
    """ Parse one console line into progress, or ``None`` if it carries none.

    Understands tqdm bars (extract, convert) and the trainer's ``[#00012] Loss A: ...`` lines
    (fraction from the requested iteration count when known).
    """
    match = _TQDM.search(line)
    if match:
        done, total = int(match["done"]), int(match["total"])
        fraction = done / total if total else None
        desc = match["desc"].strip()
        remain = match["remain"].strip()
        text = f"{desc} {done}/{total}" + (f"，剩余约 {remain}" if remain else "")
        return Progress(fraction, text.strip())
    match = _LOSS.search(line)
    if match:
        iteration = int(match["iteration"])
        fraction = min(iteration / iterations, 1.0) if iterations else None
        out_of = f"/{iterations}" if iterations else ""
        return Progress(fraction, f"迭代 {iteration}{out_of}  {match['loss'].strip()}")
    return None


def progress_key(line: str) -> str | None:
    """ The description of a tqdm bar line (``None`` if it is not one). Consecutive redraws of
    the same bar are collapsed into a single log line. """
    match = _TQDM.search(line)
    return None if match is None else match["desc"].strip()


def _default_sigint() -> None:
    """ Runs in the child before exec. A child inherits an ignored SIGINT from its parent, and
    Python then never raises KeyboardInterrupt, so the trainer could not save on stop. """
    signal.signal(signal.SIGINT, signal.SIG_DFL)


class JobRunner:  # pylint:disable=too-many-instance-attributes
    """ Launch a command, stream its merged stdout/stderr and allow it to be stopped.

    Parameters
    ----------
    max_lines
        How many log lines to keep in memory
    """
    def __init__(self, max_lines: int = 3000) -> None:
        self._lock = threading.Lock()
        self._lines: collections.deque[str] = collections.deque(maxlen=max_lines)
        self._full_tail: collections.deque[str] = collections.deque(maxlen=max_lines)
        self._process: subprocess.Popen | None = None
        self._reader: threading.Thread | None = None
        self._status = IDLE
        self._progress = Progress()
        self._message = ""
        self._command: list[str] = []
        self._job = ""
        self._iterations: int | None = None
        self._stop_requested = False
        self._preview_updated = 0.0

    @property
    def running(self) -> bool:
        """ bool : ``True`` while a job process is alive """
        return self._process is not None and self._process.poll() is None

    def start(self, command: list[str], job: str, iterations: int | None = None,
              env: dict[str, str] | None = None) -> bool:
        """ Start a job. Returns ``False`` (and does nothing) if one is already running. """
        with self._lock:
            if self.running:
                return False
            self._lines.clear()
            self._full_tail.clear()
            self._status, self._progress, self._message = RUNNING, Progress(0.0, "启动中…"), ""
            self._command, self._job, self._iterations = list(command), job, iterations
            self._stop_requested = False
            self._preview_updated = 0.0
        self._process = subprocess.Popen(  # pylint:disable=consider-using-with
            command, cwd=REPO_ROOT, env=self._environment(env), stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
            errors="replace", bufsize=1, **self._popen_platform_kwargs())
        self._reader = threading.Thread(target=self._read_output, daemon=True)
        self._reader.start()
        return True

    @staticmethod
    def _environment(extra: dict[str, str] | None) -> dict[str, str]:
        """ Copy of the current environment with unbuffered UTF-8 output """
        env = dict(os.environ)
        env.update({"PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"})
        env.update(extra or {})
        return env

    @staticmethod
    def _popen_platform_kwargs() -> dict[str, T.Any]:
        """ Own process group so the job (and its workers) can be stopped as a unit """
        if os.name == "nt":
            return {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)}
        return {"start_new_session": True, "preexec_fn": _default_sigint}

    def _read_output(self) -> None:
        """ Reader thread: collect lines until the process ends, then finalise """
        process = self._process
        assert process is not None and process.stdout is not None
        for raw in process.stdout:
            self._add_line(raw.rstrip("\n"))
        return_code = process.wait()
        self._finish(return_code)

    def _add_line(self, line: str) -> None:
        """ Store a line, collapsing tqdm redraws, and update progress """
        line = _ANSI.sub("", line)
        if not line.strip():
            return
        progress = parse_progress(line, self._iterations)
        key = progress_key(line)
        with self._lock:
            self._full_tail.append(line)
            if key is not None and self._lines and progress_key(self._lines[-1]) == key:
                self._lines[-1] = line
            else:
                self._lines.append(line)
            if progress is not None:
                self._progress = progress
            if _PREVIEW.search(line) or "Saved model" in line:
                self._preview_updated = time.time()

    def _finish(self, return_code: int) -> None:
        """ Set the final status and message once the process has exited """
        log = "\n".join(self._full_tail)
        with self._lock:
            if self._stop_requested:
                self._status = STOPPED
                self._message = ("已停止。训练已在退出前保存模型。" if self._job == "train"
                                 else "任务已被手动停止。")
            elif return_code == 0:
                self._status = DONE
                self._message = (extraction_warning(log) if self._job == "extract" else "")
                self._progress = Progress(1.0, self._progress.text or "完成")
            else:
                self._status = FAILED
                self._message = explain_failure(log, return_code)

    def stop(self, timeout: float = TRAIN_STOP_TIMEOUT) -> bool:
        """ Ask the running job to stop. Returns ``False`` if nothing is running.

        Training receives SIGINT (like Ctrl+C) so that it saves the model before exiting; it is
        killed if it has not exited after ``timeout`` seconds. Other jobs are terminated.
        """
        process = self._process
        if process is None or process.poll() is not None:
            return False
        with self._lock:
            self._stop_requested = True
            self._status = STOPPING
        if self._job == "train" and os.name != "nt":
            process.send_signal(signal.SIGINT)
            threading.Thread(target=self._kill_after, args=(process, timeout),
                             daemon=True).start()
        else:
            self._kill_tree(process)
        return True

    def _kill_after(self, process: subprocess.Popen, timeout: float) -> None:
        """ Kill the process tree if it is still alive after the timeout """
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self._kill_tree(process)

    @staticmethod
    def _kill_tree(process: subprocess.Popen) -> None:
        """ Terminate a process and all of its children, killing any that linger """
        try:
            parent = psutil.Process(process.pid)
            procs = parent.children(recursive=True) + [parent]
        except psutil.NoSuchProcess:
            return
        for proc in procs:
            try:
                proc.terminate()
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs(procs, timeout=10)
        for proc in alive:
            try:
                proc.kill()
            except psutil.NoSuchProcess:
                pass

    def shutdown(self, timeout: float = 30.0) -> None:
        """ Stop a running job when the UI itself exits. The job runs in its own process group,
        so it would otherwise outlive ``app.py``. Training gets ``timeout`` seconds to save. """
        if self.stop(timeout=timeout):
            self.wait(timeout + 15)

    def wait(self, timeout: float | None = None) -> Snapshot:
        """ Block until the job (and its reader) has finished, then return the snapshot """
        if self._reader is not None:
            self._reader.join(timeout)
        return self.snapshot()

    def snapshot(self) -> Snapshot:
        """ The current state of the job """
        with self._lock:
            return Snapshot(status=self._status,
                            log="\n".join(self._lines),
                            progress=Progress(self._progress.fraction, self._progress.text),
                            message=self._message,
                            command=list(self._command),
                            return_code=None if self._process is None else self._process.poll(),
                            preview_updated=self._preview_updated)
