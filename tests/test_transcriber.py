# -*- coding: utf-8 -*-
from unittest import mock

import numpy as np
import pytest

import config
import transcriber as tr


@pytest.mark.parametrize("parts,expected", [
    (["你好。", "世界。"], "你好。世界。"),
    (["The boy.", "And the gold."], "The boy. And the gold."),
    (["昨天是 Monday.", "Today is 星期二。"], "昨天是 Monday. Today is 星期二。"),
    (["今天", "review 一下"], "今天review 一下"),
    (["", "  ", "ok"], "ok"),
])
def test_join_segments(parts, expected):
    assert tr.join_segments(parts) == expected


@pytest.mark.parametrize("text", ["谢谢观看", "谢谢大家。", "字幕by索兰娅", "Thank you.", "you"])
def test_whisper_silence_hallucinations_are_dropped(text):
    assert tr.postprocess(text) == ""


def test_real_sentences_mentioning_thanks_survive():
    assert tr.postprocess("谢谢你帮我 review 代码") == "谢谢你帮我 review 代码"


def test_traditional_is_converted_to_simplified():
    with mock.patch.object(config, "OUTPUT_CHINESE", "simplified"):
        assert tr.postprocess("今天是禮拜二") == "今天是礼拜二"


def test_custom_vocabulary_fixes_casing_only_on_word_boundaries():
    vocab = ["Kubernetes", "PR"]
    assert tr.apply_vocabulary("部署到 kubernetes 上, 提个 pr", vocab) == "部署到 Kubernetes 上, 提个 PR"
    assert tr.apply_vocabulary("april", vocab) == "april"


def test_silence_gate():
    assert tr.is_silent(np.zeros(16000, dtype=np.float32))
    assert tr.is_silent(np.zeros(0, dtype=np.float32))
    assert not tr.is_silent((0.1 * np.sin(np.arange(16000) / 5)).astype(np.float32))


def test_transcriber_skips_model_on_silence():
    backend = mock.Mock()
    backend.transcribe.return_value = "x"
    with mock.patch.dict(tr._BACKENDS, {"fake": lambda: backend}):
        t = tr.Transcriber("fake")
        backend.transcribe.reset_mock()
        assert t.transcribe(np.zeros(16000, dtype=np.float32)) == ""
    backend.transcribe.assert_not_called()


def test_unknown_engine_is_a_clear_error():
    with pytest.raises(ValueError, match="Unknown ENGINE"):
        tr.Transcriber("nope")


def test_mlx_backend_disables_temperature_fallback():
    fake = mock.MagicMock()
    fake.transcribe.return_value = {"text": " hi "}
    with mock.patch.dict("sys.modules", {"mlx_whisper": fake}):
        b = tr.MLXWhisperBackend()
        b.transcribe(np.zeros(10, dtype=np.float32))
    kwargs = fake.transcribe.call_args.kwargs
    assert kwargs["temperature"] == 0.0
    assert kwargs["condition_on_previous_text"] is False
