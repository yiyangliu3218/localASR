# -*- coding: utf-8 -*-
import os
import threading
import time

import numpy as np
import pytest

import segmenter as sg
from conftest import MODELS_ROOT


class ListVad:
    """Deterministic fake VAD: every `seg_len` samples form one phrase."""

    window_size = 100

    def __init__(self, seg_len=1000):
        self.seg_len = seg_len
        self.buf = np.zeros(0, dtype=np.float32)
        self.done = []

    def accept_waveform(self, x):
        self.buf = np.concatenate([self.buf, x])
        while len(self.buf) >= self.seg_len:
            self.done.append(self.buf[: self.seg_len])
            self.buf = self.buf[self.seg_len:]

    def flush(self):
        if len(self.buf):
            self.done.append(self.buf)
            self.buf = np.zeros(0, dtype=np.float32)

    def empty(self):
        return not self.done

    def pop_segment(self):
        return self.done.pop(0)


def test_phrases_are_transcribed_while_still_recording():
    started = threading.Event()

    def transcribe(seg):
        started.set()
        return f"p{len(seg)}"

    s = sg.DictationSession(transcribe, vad=ListVad(1000))
    for _ in range(12):
        s.feed(np.ones(100, dtype=np.float32))
    assert started.wait(2), "first phrase should be decoded before release"
    for _ in range(5):
        s.feed(np.ones(100, dtype=np.float32))
    assert s.finish(5) == "p1000 p700"  # Latin neighbours get a space


def test_no_vad_fallback_is_one_batch():
    seen = []
    s = sg.DictationSession(lambda a: seen.append(len(a)) or "x", vad=None)
    for _ in range(7):
        s.feed(np.ones(333, dtype=np.float32))
    assert s.finish(5) == "x"
    assert seen == [7 * 333]


def test_on_phrase_called_in_order():
    got = []
    s = sg.DictationSession(lambda a: str(len(a)), vad=ListVad(200), on_phrase=got.append)
    s.feed(np.ones(500, dtype=np.float32))
    s.finish(5)
    assert got == ["200", "200", "100"]


def test_errors_surface_from_finish_not_swallowed():
    def boom(_):
        raise RuntimeError("model crashed")

    s = sg.DictationSession(boom, vad=ListVad(100))
    s.feed(np.ones(300, dtype=np.float32))
    with pytest.raises(RuntimeError, match="model crashed"):
        s.finish(5)


def test_feed_never_blocks_on_slow_model():
    s = sg.DictationSession(lambda a: time.sleep(0.2) or "x", vad=ListVad(100))
    t0 = time.perf_counter()
    for _ in range(50):
        s.feed(np.ones(100, dtype=np.float32))
    assert time.perf_counter() - t0 < 0.05  # audio thread must stay real-time
    s.finish(30)


VAD_PATH = os.path.join(MODELS_ROOT, "silero_vad.onnx")


@pytest.mark.skipif(not os.path.exists(VAD_PATH), reason="silero_vad.onnx not downloaded")
def test_real_vad_splits_at_pauses():
    sr = 16000
    tone = (0.3 * np.sin(2 * np.pi * 220 * np.arange(sr) / sr)).astype(np.float32)
    noise = np.random.default_rng(0).normal(0, 0.1, sr).astype(np.float32)
    speechlike = tone * (1 + noise)
    vad = sg._SileroVad(VAD_PATH, sr)
    segs = []
    s = sg.DictationSession(lambda a: segs.append(len(a)) or "x", vad=vad)
    audio = np.concatenate([speechlike, np.zeros(sr, np.float32), speechlike])
    for i in range(0, len(audio), 800):
        s.feed(audio[i:i + 800])
    s.finish(10)
    # Silero may or may not consider a synthetic tone speech; the invariant we
    # rely on is: never more phrases than bursts, never audio from the silence.
    assert len(segs) <= 2
    assert sum(segs) <= 2.5 * sr
