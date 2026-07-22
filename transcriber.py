# -*- coding: utf-8 -*-
"""mlx-whisper 模型封装(Apple Silicon GPU 加速),负责把录到的音频转成文字。"""
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
        # mlx-whisper 没有常驻模型对象,首次调用 transcribe 时才会加载/下载模型；
        # 这里提前跑一次空音频，把模型加载和下载放在启动阶段完成。
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
