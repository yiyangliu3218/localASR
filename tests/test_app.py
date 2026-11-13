# -*- coding: utf-8 -*-
import threading
import time
from unittest import mock

import numpy as np
import pytest

import app as app_mod


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setattr(app_mod, "Transcriber", mock.Mock())
    monkeypatch.setattr(app_mod, "make_vad_factory", lambda: None)
    monkeypatch.setattr(app_mod, "AudioRecorder", mock.Mock())
    monkeypatch.setattr(app_mod, "FnHotkeyListener", mock.Mock())
    a = app_mod.DictationApp()
    deadline = time.time() + 5
    while a.transcriber is None and time.time() < deadline:
        time.sleep(0.01)
    a.outputs = []
    monkeypatch.setattr(app_mod, "output_text",
                        lambda text, **k: a.outputs.append(text) or "typed")
    return a


def wait_until(cond, timeout=5):
    deadline = time.time() + timeout
    while not cond() and time.time() < deadline:
        time.sleep(0.01)
    return cond()


def dictate(app, chunks, valid=True):
    app.on_fn_press()
    on_chunk = app.recorder.start.call_args.kwargs["on_chunk"]
    for c in chunks:
        on_chunk(c)
    app.on_fn_release(valid)


def test_happy_path_types_text_and_restores_icon(app):
    app.transcriber.transcribe.return_value = "你好 world"
    dictate(app, [np.ones(1600, np.float32)])
    assert wait_until(lambda: app.outputs == ["你好 world"])
    assert wait_until(lambda: app.title == app_mod.ICON_READY)


def test_transcription_error_does_not_leave_icon_stuck(app):
    app.transcriber.transcribe.side_effect = RuntimeError("Metal OOM")
    dictate(app, [np.ones(1600, np.float32)])
    assert wait_until(lambda: app.title == app_mod.ICON_READY)
    assert app.outputs == []


def test_short_tap_is_discarded(app):
    app.transcriber.transcribe.return_value = "x"
    dictate(app, [np.ones(1600, np.float32)], valid=False)
    time.sleep(0.2)
    assert app.outputs == []


def test_timer_and_real_release_race_outputs_once(app):
    app.transcriber.transcribe.return_value = "once"
    app.on_fn_press()
    app.recorder.start.call_args.kwargs["on_chunk"](np.ones(1600, np.float32))
    t = [threading.Thread(target=app.on_fn_release, args=(True,)) for _ in range(2)]
    for x in t:
        x.start()
    for x in t:
        x.join()
    assert wait_until(lambda: app.outputs == ["once"])
    time.sleep(0.2)
    assert app.outputs == ["once"]
    assert app.recorder.stop.call_count == 1


def test_inference_is_serialized_across_overlapping_dictations(app):
    active, peak = [0], [0]

    def slow(audio):
        active[0] += 1
        peak[0] = max(peak[0], active[0])
        time.sleep(0.15)
        active[0] -= 1
        return "t"

    app.transcriber.transcribe.side_effect = slow
    dictate(app, [np.ones(1600, np.float32)])
    dictate(app, [np.ones(1600, np.float32)])  # pressed again while #1 still decoding
    assert wait_until(lambda: len(app.outputs) == 2)
    assert peak[0] == 1


def test_press_ignored_while_model_loading(app):
    app.transcriber = None
    app.recorder.start.reset_mock()
    app.on_fn_press()
    app.recorder.start.assert_not_called()


def test_mic_failure_notifies_and_stays_ready(app):
    app.recorder.start.side_effect = OSError("device busy")
    with mock.patch.object(app_mod.rumps, "notification") as n:
        app.on_fn_press()
    n.assert_called_once()
    assert app._session is None


def test_model_load_failure_shows_error(monkeypatch):
    monkeypatch.setattr(app_mod, "Transcriber", mock.Mock(side_effect=OSError("disk full")))
    monkeypatch.setattr(app_mod, "AudioRecorder", mock.Mock())
    monkeypatch.setattr(app_mod, "FnHotkeyListener", mock.Mock())
    deferred = []  # like the real main queue: blocks run *after* the caller returns
    monkeypatch.setattr(app_mod, "run_on_main", deferred.append)
    a = app_mod.DictationApp()
    assert wait_until(lambda: deferred)
    time.sleep(0.05)
    for fn in deferred:
        fn()  # original code raised NameError here (exc unbound after except)
    assert a.title == app_mod.ICON_ERROR
    assert "disk full" in a._model_error
