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


def test_mic_failure_notifies_and_stays_ready(app, monkeypatch):
    monkeypatch.setattr(app_mod.config, "SHOW_NOTIFICATIONS", True)
    app.recorder.start.side_effect = OSError("device busy")
    with mock.patch.object(app_mod.rumps, "notification") as n:
        app.on_fn_press()
    n.assert_called_once()
    assert app._session is None


def test_notifications_off_only_logs(app, monkeypatch, capsys):
    monkeypatch.setattr(app_mod.config, "SHOW_NOTIFICATIONS", False)
    app.recorder.start.side_effect = OSError("device busy")
    with mock.patch.object(app_mod.rumps, "notification") as n:
        app.on_fn_press()
    n.assert_not_called()
    assert "device busy" in capsys.readouterr().out


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


def test_overlay_follows_record_transcribe_hide(app):
    app.overlay = mock.Mock()
    app.transcriber.transcribe.return_value = "好的"
    dictate(app, [np.ones(1600, np.float32)])
    assert wait_until(lambda: app.outputs == ["好的"])
    assert wait_until(lambda: [c[0] for c in app.overlay.method_calls]
                      == ["show_recording", "show_transcribing", "hide"])


def test_overlay_hides_on_short_tap(app):
    app.overlay = mock.Mock()
    app.transcriber.transcribe.return_value = "x"
    dictate(app, [np.ones(1600, np.float32)], valid=False)
    assert [c[0] for c in app.overlay.method_calls] == ["show_recording", "hide"]


def test_overlay_failure_never_breaks_dictation(app):
    app.overlay = mock.Mock()
    app.overlay.show_recording.side_effect = RuntimeError("AppKit exploded")
    app.transcriber.transcribe.return_value = "照样出字"
    dictate(app, [np.ones(1600, np.float32)])
    assert wait_until(lambda: app.outputs == ["照样出字"])


def test_second_instance_is_refused(tmp_path, monkeypatch):
    import fcntl

    lock = tmp_path / "sub" / "app.lock"
    monkeypatch.setattr(app_mod, "_lock_file", None)
    assert app_mod.acquire_single_instance(str(lock))  # first copy gets it
    held = app_mod._lock_file
    # A second open of the same file (what another process would do) can't lock it
    with open(lock, "w") as other:
        with pytest.raises(OSError):
            fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
    monkeypatch.setattr(app_mod, "_lock_file", None)
    assert not app_mod.acquire_single_instance(str(lock))
    held.close()  # first copy exits -> free again
    assert app_mod.acquire_single_instance(str(lock))
    app_mod._lock_file.close()


def test_second_launch_asks_running_copy_to_show_menu(monkeypatch):
    monkeypatch.setattr(app_mod, "acquire_single_instance", lambda: False)
    center = mock.Mock()
    monkeypatch.setattr(app_mod, "NSDistributedNotificationCenter",
                        mock.Mock(defaultCenter=lambda: center))
    monkeypatch.setattr(app_mod, "DictationApp", mock.Mock(side_effect=AssertionError))
    assert app_mod.main() == 0
    name = center.postNotificationName_object_userInfo_deliverImmediately_.call_args.args[0]
    assert name == app_mod.REOPEN_NOTIFICATION


def test_listener_restarts_once_permission_is_granted(app, monkeypatch):
    app.listener = mock.Mock(active=True, intercepting=False)
    monkeypatch.setattr(app_mod.config, "SUPPRESS_FN_SYSTEM_ACTION", True)
    granted = {"ax": False}
    monkeypatch.setattr(app_mod, "AXIsProcessTrusted", lambda: granted["ax"])
    monkeypatch.setattr(app_mod, "CGPreflightListenEventAccess", lambda: True)
    timer = mock.Mock()

    app._permission_state = None
    app._on_permission_tick(timer)  # still no Accessibility: nothing to do
    app._on_permission_tick(timer)
    app.listener.start.assert_not_called()

    granted["ax"] = True  # user flips the switch
    app.listener.start.side_effect = lambda: setattr(app.listener, "intercepting", True)
    app._on_permission_tick(timer)
    app.listener.start.assert_called_once()
    timer.stop.assert_called_once()
