# -*- coding: utf-8 -*-
"""Real-time phrase segmentation.

While Fn is held, microphone chunks are pushed into a ``DictationSession``. A
Silero VAD (via sherpa-onnx) cuts the stream at natural pauses; each finished
phrase is transcribed immediately on the session's worker thread, overlapping
with the user still speaking. On release only the trailing phrase is left, so
release-to-text latency no longer grows with how long you talked.
"""
import queue
import threading

import numpy as np

import config
from transcriber import join_segments

_STOP = object()


class _NoVad:
    """Fallback when VAD is unavailable: buffer everything, one segment at the end."""

    window_size = 512

    def __init__(self):
        self._buf = []
        self._done = []

    def accept_waveform(self, x):
        self._buf.append(np.asarray(x, dtype=np.float32))

    def flush(self):
        if self._buf:
            self._done.append(np.concatenate(self._buf))
            self._buf = []

    def empty(self):
        return not self._done

    def pop_segment(self):
        return self._done.pop(0)


class _SileroVad:
    def __init__(self, model_path, sample_rate):
        import sherpa_onnx

        cfg = sherpa_onnx.VadModelConfig()
        cfg.silero_vad.model = model_path
        cfg.silero_vad.threshold = 0.5
        cfg.silero_vad.min_silence_duration = 0.35  # pause length that ends a phrase
        cfg.silero_vad.min_speech_duration = 0.2
        cfg.silero_vad.max_speech_duration = 15  # force a cut in very long run-on speech
        cfg.sample_rate = sample_rate
        cfg.num_threads = 1
        self.window_size = cfg.silero_vad.window_size
        self._vad = sherpa_onnx.VoiceActivityDetector(cfg, buffer_size_in_seconds=60)

    def accept_waveform(self, x):
        self._vad.accept_waveform(x)

    def flush(self):
        self._vad.flush()

    def empty(self):
        return self._vad.empty()

    def pop_segment(self):
        seg = np.array(self._vad.front.samples, dtype=np.float32)
        self._vad.pop()
        return seg


def make_vad_factory():
    """Returns a zero-arg callable creating a fresh VAD per dictation, or None."""
    try:
        from model_download import SILERO_VAD, ensure_file

        path = ensure_file(config.MODELS_DIR, SILERO_VAD)
        _SileroVad(path, config.SAMPLE_RATE)  # validate once
        return lambda: _SileroVad(path, config.SAMPLE_RATE)
    except Exception as exc:  # sherpa-onnx missing, offline on first run, ...
        print(f"[segmenter] VAD unavailable, falling back to batch mode: {exc}", flush=True)
        return None


class DictationSession:
    """One press-to-release dictation.

    feed() is called from the audio thread and never blocks on the model.
    finish() blocks until all speech has been transcribed and returns the text.
    on_phrase(text) (optional) is called on the worker thread for each phrase.
    """

    def __init__(self, transcribe, vad=None, on_phrase=None):
        self._transcribe = transcribe
        self._vad = vad if vad is not None else _NoVad()
        self._on_phrase = on_phrase
        self._q = queue.Queue()
        self._parts = []
        self._error = None
        self._pending = np.zeros(0, dtype=np.float32)
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def feed(self, chunk: np.ndarray):
        self._q.put(np.asarray(chunk, dtype=np.float32).reshape(-1))

    def finish(self, timeout: float = None) -> str:
        self._q.put(_STOP)
        self._worker.join(timeout)
        if self._error is not None:
            raise self._error
        return join_segments(self._parts)

    def _drain_segments(self):
        while not self._vad.empty():
            text = self._transcribe(self._vad.pop_segment())
            if text:
                self._parts.append(text)
                if self._on_phrase is not None:
                    self._on_phrase(text)

    def _run(self):
        win = self._vad.window_size
        try:
            while True:
                item = self._q.get()
                if item is _STOP:
                    break
                self._pending = np.concatenate([self._pending, item])
                n = (len(self._pending) // win) * win
                for i in range(0, n, win):
                    self._vad.accept_waveform(self._pending[i:i + win])
                self._pending = self._pending[n:]
                self._drain_segments()
            if len(self._pending):
                self._vad.accept_waveform(self._pending)
            self._vad.flush()
            self._drain_segments()
        except Exception as exc:  # surfaced to the caller of finish()
            self._error = exc
