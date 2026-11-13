# -*- coding: utf-8 -*-
from unittest import mock

import numpy as np
import pytest

import audio_recorder as ar


@pytest.fixture
def rec():
    with mock.patch.object(ar, "sd") as sd:
        r = ar.AudioRecorder()
        r._fake_sd = sd
        yield r


def block(n, value=0.5):
    return np.full((n, 1), value, dtype=np.float32)


def test_records_and_streams_chunks(rec):
    got = []
    rec.start(on_chunk=got.append)
    rec._callback(block(800), 800, None, None)
    rec._callback(block(800), 800, None, None)
    audio = rec.stop()
    assert audio.shape == (1600,)
    assert sum(len(c) for c in got) == 1600
    rec._fake_sd.InputStream.return_value.close.assert_called_once()


def test_caps_at_max_length(rec):
    rec._max_frames = 1000
    rec.start()
    for _ in range(5):
        rec._callback(block(800), 800, None, None)
    assert rec.stop().shape == (1000,)  # exactly the cap, not 1600


def test_callbacks_after_stop_are_ignored(rec):
    got = []
    rec.start(on_chunk=got.append)
    rec.stop()
    rec._callback(block(800), 800, None, None)
    assert got == []


def test_mic_open_failure_leaves_recorder_reusable(rec):
    rec._fake_sd.InputStream.side_effect = RuntimeError("no mic")
    with pytest.raises(RuntimeError):
        rec.start()
    rec._fake_sd.InputStream.side_effect = None
    rec.start()  # must not be stuck in "recording"
    rec._callback(block(10), 10, None, None)
    assert rec.stop().shape == (10,)
