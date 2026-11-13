# -*- coding: utf-8 -*-
"""End-to-end accuracy/latency regression on real audio. Skipped unless models
are downloaded (bench/download_models.sh ~/.cache/localasr/models)."""
import os
import sys
import time
from unittest import mock

import numpy as np
import pytest

from conftest import MODELS_ROOT, ROOT

sys.path.insert(0, os.path.join(ROOT, "bench"))
from metrics import mer  # noqa: E402
from testset import TESTSET  # noqa: E402

import config  # noqa: E402

SV = os.path.join(MODELS_ROOT, "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17")
pytestmark = pytest.mark.skipif(not os.path.isdir(SV), reason="SenseVoice model not downloaded")


@pytest.fixture(scope="module")
def stack():
    sf = pytest.importorskip("soundfile")
    with mock.patch.object(config, "MODELS_DIR", MODELS_ROOT):
        import segmenter
        import transcriber

        t = transcriber.Transcriber("sensevoice")
        vad_factory = segmenter.make_vad_factory()
        yield t, vad_factory, sf, segmenter


def load(sf, rel):
    a, sr = sf.read(os.path.join(MODELS_ROOT, rel), dtype="float32")
    return a


@pytest.mark.parametrize("cat,limit", [("zh", 0.05), ("en", 0.05), ("mix", 0.25)])
def test_accuracy_budget(stack, cat, limit):
    t, _, sf, _ = stack
    e = n = 0
    for c, rel, ref in TESTSET:
        if c == cat:
            de, dn = mer(ref, t.transcribe(load(sf, rel)))
            e, n = e + de, n + dn
    assert e / n <= limit, f"{cat} MER {e / n:.3f} > {limit}"


def test_streaming_session_release_latency(stack):
    t, vad_factory, sf, segmenter = stack
    assert vad_factory is not None
    audio = np.concatenate([load(sf, rel) for _, rel, _ in TESTSET[:6]])
    s = segmenter.DictationSession(t.transcribe, vad=vad_factory())
    step = 800  # 50 ms, like the mic callback
    for i in range(0, len(audio), step):
        s.feed(audio[i:i + step])
        time.sleep(step / 16000 / 8)  # 8x real time keeps the test fast but realistic
    t0 = time.perf_counter()
    text = s.finish(30)
    tail = time.perf_counter() - t0
    assert "全球金融" in text and "chieftain" in text.lower()
    assert tail < 1.0, f"release->text {tail:.2f}s"
