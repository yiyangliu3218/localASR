# -*- coding: utf-8 -*-
"""Wraps mlx-whisper (Apple Silicon GPU accelerated) to turn recorded audio into text."""
import mlx_whisper
import numpy as np
from opencc import OpenCC

from config import CUSTOM_VOCABULARY, INITIAL_PROMPT, LANGUAGE, MODEL_REPO, OUTPUT_CHINESE

_PROMPT = INITIAL_PROMPT
if CUSTOM_VOCABULARY:
    _PROMPT += "常见专业词汇：" + "、".join(CUSTOM_VOCABULARY) + "。"

_CONVERTERS = {"simplified": OpenCC("t2s"), "traditional": OpenCC("s2t")}


def normalize_chinese(text: str, mode: str) -> str:
    converter = _CONVERTERS.get(mode)
    return converter.convert(text) if converter else text


class Transcriber:
    def __init__(self):
        # mlx-whisper has no persistent model object; the model is only loaded/
        # downloaded on the first call to transcribe. Run one dummy pass here so
        # loading/downloading happens during startup instead of on first use.
        self.transcribe(np.zeros(16000, dtype=np.float32))

    def transcribe(self, audio: np.ndarray) -> str:
        if audio.size == 0:
            return ""
        result = mlx_whisper.transcribe(
            audio,
            path_or_hf_repo=MODEL_REPO,
            language=LANGUAGE,
            initial_prompt=_PROMPT,
        )
        return normalize_chinese(result["text"].strip(), OUTPUT_CHINESE)
