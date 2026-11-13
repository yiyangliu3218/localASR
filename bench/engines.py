# -*- coding: utf-8 -*-
"""ASR engine adapters used by the benchmark (sherpa-onnx, CPU, cross-platform).

Every engine exposes:  transcribe(samples: float32 np.ndarray @16 kHz) -> str
Streaming engines additionally expose: stream_feed(samples, chunk_ms) -> (text, first_partial_s)
"""
import os
import time

import numpy as np
import sherpa_onnx

SR = 16000


def _p(model_dir, name):
    return os.path.join(model_dir, name)


class SenseVoice:
    name = "sensevoice-small-int8"

    def __init__(self, model_dir, threads=4):
        self.rec = sherpa_onnx.OfflineRecognizer.from_sense_voice(
            model=_p(model_dir, "model.int8.onnx"),
            tokens=_p(model_dir, "tokens.txt"),
            num_threads=threads,
            use_itn=True,  # inverse text normalization: punctuation + digits
            language="auto",
        )

    def transcribe(self, samples):
        s = self.rec.create_stream()
        s.accept_waveform(SR, samples)
        self.rec.decode_stream(s)
        return s.result.text


class WhisperTurbo:
    """Same weights as mlx-community/whisper-large-v3-turbo, int8 ONNX on CPU."""

    name = "whisper-large-v3-turbo-int8"

    def __init__(self, model_dir, threads=4, language=""):
        self.rec = sherpa_onnx.OfflineRecognizer.from_whisper(
            encoder=_p(model_dir, "turbo-encoder.int8.onnx"),
            decoder=_p(model_dir, "turbo-decoder.int8.onnx"),
            tokens=_p(model_dir, "turbo-tokens.txt"),
            num_threads=threads,
            language=language,
            task="transcribe",
        )

    def transcribe(self, samples):
        s = self.rec.create_stream()
        s.accept_waveform(SR, samples)
        self.rec.decode_stream(s)
        return s.result.text


class Paraformer:
    name = "paraformer-zh-int8"

    def __init__(self, model_dir, threads=4):
        self.rec = sherpa_onnx.OfflineRecognizer.from_paraformer(
            paraformer=_p(model_dir, "model.int8.onnx"),
            tokens=_p(model_dir, "tokens.txt"),
            num_threads=threads,
        )

    def transcribe(self, samples):
        s = self.rec.create_stream()
        s.accept_waveform(SR, samples)
        self.rec.decode_stream(s)
        return s.result.text


class _Streaming:
    def transcribe(self, samples):
        return self.stream_feed(samples, chunk_ms=100)[0]

    def stream_feed(self, samples, chunk_ms=100):
        """Feed audio chunk by chunk as a microphone would. Returns
        (final_text, compute_time_after_last_chunk_s, partial_updates)."""
        s = self.rec.create_stream()
        step = int(SR * chunk_ms / 1000)
        updates = 0
        last = ""
        for i in range(0, len(samples), step):
            s.accept_waveform(SR, samples[i : i + step])
            while self.rec.is_ready(s):
                self.rec.decode_stream(s)
            t = self.rec.get_result(s)
            if t != last:
                updates += 1
                last = t
        # user releases the key: flush
        t0 = time.perf_counter()
        s.accept_waveform(SR, np.zeros(int(0.66 * SR), dtype=np.float32))
        s.input_finished()
        while self.rec.is_ready(s):
            self.rec.decode_stream(s)
        tail = time.perf_counter() - t0
        return self.rec.get_result(s), tail, updates


class StreamingZipformer(_Streaming):
    name = "streaming-zipformer-zh-en-int8"

    def __init__(self, model_dir, threads=4):
        self.rec = sherpa_onnx.OnlineRecognizer.from_transducer(
            tokens=_p(model_dir, "tokens.txt"),
            encoder=_p(model_dir, "encoder-epoch-99-avg-1.int8.onnx"),
            decoder=_p(model_dir, "decoder-epoch-99-avg-1.onnx"),
            joiner=_p(model_dir, "joiner-epoch-99-avg-1.int8.onnx"),
            num_threads=threads,
            decoding_method="greedy_search",
        )


class StreamingParaformer(_Streaming):
    name = "streaming-paraformer-zh-en-int8"

    def __init__(self, model_dir, threads=4):
        self.rec = sherpa_onnx.OnlineRecognizer.from_paraformer(
            tokens=_p(model_dir, "tokens.txt"),
            encoder=_p(model_dir, "encoder.int8.onnx"),
            decoder=_p(model_dir, "decoder.int8.onnx"),
            num_threads=threads,
        )


REGISTRY = {
    "sensevoice": (SenseVoice, "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17"),
    "whisper-turbo": (WhisperTurbo, "sherpa-onnx-whisper-turbo"),
    "paraformer": (Paraformer, "sherpa-onnx-paraformer-zh-2024-03-09"),
    "stream-zipformer": (StreamingZipformer, "sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20"),
    "stream-paraformer": (StreamingParaformer, "sherpa-onnx-streaming-paraformer-bilingual-zh-en"),
}


def load(key, models_root, threads=4):
    cls, sub = REGISTRY[key]
    return cls(os.path.join(models_root, sub), threads=threads)


class MLXWhisper:
    """The app's current engine, with the exact settings from config.py.
    Only available on Apple Silicon (pip install mlx-whisper)."""

    name = "mlx-whisper (app config)"

    def __init__(self, model_dir=None, threads=None, **overrides):
        import mlx_whisper  # noqa: F401  (raises ImportError off-Mac)
        import sys

        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        import config

        self._mlx = mlx_whisper
        self.kwargs = dict(
            path_or_hf_repo=config.MODEL_REPO,
            language=config.LANGUAGE,
            initial_prompt=config.INITIAL_PROMPT,
        )
        self.kwargs.update(overrides)

    def transcribe(self, samples):
        return self._mlx.transcribe(samples, **self.kwargs)["text"].strip()


def load_mlx(**overrides):
    return MLXWhisper(**overrides)
