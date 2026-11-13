# -*- coding: utf-8 -*-
"""Speech-to-text backends plus shared text post-processing.

Backends expose ``transcribe(audio: float32 ndarray @16 kHz) -> str``. They are NOT
thread-safe; the app funnels every call through a single worker thread.
"""
import re

import numpy as np
from opencc import OpenCC

import config

_CONVERTERS = {"simplified": OpenCC("t2s"), "traditional": OpenCC("s2t")}

# Whisper's well-known hallucinations on silence / noise (subtitle credits etc.)
_HALLUCINATIONS = re.compile(
    r"^(谢谢(大家|观看|收看)?[。！!.]*|请不吝点赞.*|字幕(由|by).*|(明镜|优优)字幕.*|"
    r"thank you( for watching)?[.!]*|thanks for watching[.!]*|you)$",
    re.IGNORECASE,
)
_LATIN_END = re.compile(r"[A-Za-z0-9.,!?;:'\")]$")
_LATIN_START = re.compile(r"^[A-Za-z0-9(\"']")


def normalize_chinese(text: str, mode: str) -> str:
    converter = _CONVERTERS.get(mode)
    return converter.convert(text) if converter else text


def apply_vocabulary(text: str, vocabulary) -> str:
    """Fixes the capitalization/spelling of Latin-script custom terms."""
    for term in vocabulary:
        if re.search(r"[A-Za-z]", term):
            text = re.sub(r"(?<![A-Za-z])" + re.escape(term) + r"(?![A-Za-z])", term, text,
                          flags=re.IGNORECASE)
    return text


def join_segments(parts) -> str:
    """Concatenates phrase-level results, inserting a space only between two
    Latin-script neighbours ("boy." + "And" -> "boy. And"; "你好" + "世界" -> "你好世界")."""
    out = ""
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if out and _LATIN_END.search(out) and _LATIN_START.search(p):
            out += " "
        out += p
    return out


def postprocess(text: str) -> str:
    text = text.strip()
    if _HALLUCINATIONS.match(text):
        return ""
    text = normalize_chinese(text, config.OUTPUT_CHINESE)
    return apply_vocabulary(text, config.CUSTOM_VOCABULARY)


def is_silent(audio: np.ndarray, threshold: float = 0.004) -> bool:
    """RMS gate so we never feed pure silence/noise to the model (that is where
    Whisper invents "谢谢观看" etc.)."""
    return audio.size == 0 or float(np.sqrt(np.mean(np.square(audio)))) < threshold


class SenseVoiceBackend:
    name = "sensevoice"

    def __init__(self):
        import sherpa_onnx

        from model_download import SENSEVOICE, ensure_model_dir

        d = ensure_model_dir(config.MODELS_DIR, SENSEVOICE)
        self._rec = sherpa_onnx.OfflineRecognizer.from_sense_voice(
            model=f"{d}/model.int8.onnx",
            tokens=f"{d}/tokens.txt",
            num_threads=config.NUM_THREADS,
            use_itn=True,  # punctuation + "九点" -> "9点"
            language="auto",
        )

    def transcribe(self, audio: np.ndarray) -> str:
        s = self._rec.create_stream()
        s.accept_waveform(config.SAMPLE_RATE, audio)
        self._rec.decode_stream(s)
        return s.result.text


class MLXWhisperBackend:
    name = "mlx-whisper"

    def __init__(self):
        import mlx_whisper

        self._mlx = mlx_whisper
        prompt = config.INITIAL_PROMPT
        if config.CUSTOM_VOCABULARY:
            prompt += " " + ", ".join(config.CUSTOM_VOCABULARY) + "."
        self._kwargs = dict(
            path_or_hf_repo=config.MODEL_REPO,
            language=config.LANGUAGE,
            initial_prompt=prompt,
            # mlx-whisper defaults to a 6-step temperature fallback (0.0 .. 1.0): when
            # a decode looks "bad" it silently re-decodes up to 5 more times, which is
            # where the occasional multi-second stalls come from. Dictation snippets
            # are short; one greedy pass is enough.
            temperature=0.0,
            condition_on_previous_text=False,  # stops repetition loops on long audio
        )

    def transcribe(self, audio: np.ndarray) -> str:
        return self._mlx.transcribe(audio, **self._kwargs)["text"]


_BACKENDS = {"sensevoice": SenseVoiceBackend, "mlx-whisper": MLXWhisperBackend}


class Transcriber:
    def __init__(self, engine: str = None):
        engine = engine or config.ENGINE
        if engine not in _BACKENDS:
            raise ValueError(f"Unknown ENGINE {engine!r}; choose one of {sorted(_BACKENDS)}")
        self.backend = _BACKENDS[engine]()
        # Warm-up pass: loads/downloads weights and JIT-compiles kernels at startup
        # instead of on the user's first dictation.
        self.backend.transcribe(np.zeros(config.SAMPLE_RATE, dtype=np.float32))

    def transcribe(self, audio: np.ndarray) -> str:
        if is_silent(audio):
            return ""
        return postprocess(self.backend.transcribe(audio))
