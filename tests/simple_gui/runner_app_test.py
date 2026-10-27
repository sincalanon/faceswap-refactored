#!/usr/bin/env python3
""" Pytest unit tests for :mod:`simple_gui.runner`, the ``app.py`` launcher and (when Gradio is
installed) building :mod:`simple_gui.ui` """
import os
import sys
import time

import pytest

from simple_gui import runner


@pytest.mark.parametrize("line,fraction,text", [
    ("Extracting faces:  45%|████▌     | 9/20 [00:01<00:02,  4.10it/s]", 0.45,
     "Extracting faces 9/20，剩余约 00:02"),
    ("Converting: 100%|██████████| 91/91 [00:10<00:00,  8.41it/s]", 1.0, "Converting 91/91"),
])
def test_parse_tqdm(line, fraction, text):
    """ tqdm bars are parsed into a fraction and a short text """
    progress = runner.parse_progress(line)
    assert progress is not None
    assert progress.fraction == pytest.approx(fraction)
    assert progress.text.startswith(text)


def test_parse_loss():
    """ Trainer loss lines give iteration progress when the total is known """
    line = "[09:17:08] [#00050] Loss A: 0.40662, Loss B: 0.40141"
    progress = runner.parse_progress(line, iterations=200)
    assert progress is not None and progress.fraction == pytest.approx(0.25)
    assert "迭代 50/200" in progress.text and "Loss A: 0.40662" in progress.text
    assert runner.parse_progress(line).fraction is None


def test_parse_other_lines():
    """ Ordinary log lines carry no progress """
    assert runner.parse_progress("10/27/2026 09:16:35 INFO     Images found:        4") is None
    assert runner.progress_key("plain line") is None
    key = runner.progress_key("Extracting faces:  1%|  | 1/91 [00:00<00:10, 9it/s]")
    assert key == "Extracting faces"


def _python(code):
    return [sys.executable, "-c", code]


def test_runner_success_collapses_progress():
    """ A finished job reports DONE, keeps its log and collapses tqdm redraws """
    code = ("import sys\n"
            "print('hello')\n"
            "for i in range(1, 4):\n"
            "    sys.stdout.write(f'\\rWork: {i*33}%|###| {i}/3 [00:01<00:0{3-i}, 1it/s]')\n"
            "sys.stdout.write('\\n')\n"
            "print('Images found:        3')\n"
            "print('Faces detected:      0')\n")
    job = runner.JobRunner()
    assert job.start(_python(code), "extract")
    snap = job.wait(30)
    assert snap.status == runner.DONE and snap.return_code == 0
    assert snap.log.count("Work:") == 1 and "3/3" in snap.log
    assert snap.progress.fraction == 1.0
    assert "没有检测到任何人脸" in snap.message  # extraction warning surfaced


def test_runner_failure_message():
    """ A failing job is mapped to a friendly message """
    code = "import sys; print('ERROR    Side A contains fewer than 25 images.'); sys.exit(1)"
    job = runner.JobRunner()
    job.start(_python(code), "train", iterations=10)
    snap = job.wait(30)
    assert snap.status == runner.FAILED and snap.return_code == 1
    assert "人脸太少" in snap.message


def test_runner_single_job_and_stop():
    """ Only one job runs at a time and stop terminates it """
    job = runner.JobRunner()
    assert job.start(_python("import time; print('started', flush=True); time.sleep(60)"),
                     "extract")
    assert not job.start(_python("print(1)"), "extract")
    deadline = time.time() + 20
    while "started" not in job.snapshot().log and time.time() < deadline:
        time.sleep(0.1)
    assert job.stop()
    snap = job.wait(30)
    assert snap.status == runner.STOPPED and not snap.running
    assert not job.stop()


@pytest.mark.skipif(os.name == "nt", reason="SIGINT based graceful stop is POSIX only")
def test_runner_train_stop_sends_sigint():
    """ Training gets SIGINT first so it can save before exiting """
    code = ("import time\n"
            "print('ready', flush=True)\n"
            "try:\n"
            "    time.sleep(60)\n"
            "except KeyboardInterrupt:\n"
            "    print('saved on interrupt', flush=True)\n")
    job = runner.JobRunner()
    job.start(_python(code), "train")
    deadline = time.time() + 20
    while "ready" not in job.snapshot().log and time.time() < deadline:
        time.sleep(0.1)
    job.stop(timeout=20)
    snap = job.wait(30)
    assert "saved on interrupt" in snap.log
    assert snap.status == runner.STOPPED


def test_app_parse_args():
    """ Launcher flags """
    app = pytest.importorskip("app")
    args = app.parse_args(["--host", "0.0.0.0", "--port", "8000", "--share"])
    assert (args.host, args.port, args.share) == ("0.0.0.0", 8000, True)
    defaults = app.parse_args([])
    assert (defaults.host, defaults.port, defaults.share) == ("127.0.0.1", 7860, False)


def test_build_ui(monkeypatch, tmp_path):
    """ The Gradio app builds (skipped when Gradio is not installed) """
    pytest.importorskip("gradio")
    monkeypatch.setenv("FACESWAP_SIMPLE_GUI_CONFIG_DIR", str(tmp_path))
    from simple_gui import ui  # pylint:disable=import-outside-toplevel
    app = ui.build_app()
    assert app is not None
    status, _, _ = next(ui.run_extract(False, "/x", "/y", "auto", "auto", "none", 512, 1, 0,
                                       False, False))
    assert "无法开始" in status


def test_runner_shutdown():
    """ shutdown() stops a running job (used when app.py exits) and is a no-op otherwise """
    job = runner.JobRunner()
    job.shutdown()
    job.start(_python("import time; time.sleep(60)"), "convert")
    job.shutdown(timeout=5)
    assert not job.running
