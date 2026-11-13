# -*- coding: utf-8 -*-
"""Microphone recorder that opens the input stream on demand.

The mic stream is only opened while actually recording, so macOS's orange
menu bar recording indicator lights up only while the hotkey is held down
and turns off on release, instead of the mic staying open the whole time.
"""
import threading

import numpy as np
import sounddevice as sd

from config import CHANNELS, MAX_RECORD_SECONDS, SAMPLE_RATE


class AudioRecorder:
    def __init__(self):
        self._frames = []
        self._num_frames = 0
        self._lock = threading.Lock()
        self._recording = False
        self._stream = None
        self._on_chunk = None
        self._max_frames = SAMPLE_RATE * MAX_RECORD_SECONDS

    def _callback(self, indata, frames, time_info, status):
        # Runs on PortAudio's real-time thread: keep it cheap, never block.
        with self._lock:
            if not self._recording:
                return
            room = self._max_frames - self._num_frames
            chunk = indata[:room, 0].copy()  # mono float32, capped at the max length
            self._frames.append(chunk)
            self._num_frames += len(chunk)
            if self._num_frames >= self._max_frames:
                self._recording = False
            on_chunk = self._on_chunk
        if on_chunk is not None and len(chunk):
            on_chunk(chunk)

    def start(self, on_chunk=None):
        """on_chunk(np.ndarray) is called from the audio thread for every block."""
        with self._lock:
            if self._recording:
                return
            self._frames = []
            self._num_frames = 0
            self._on_chunk = on_chunk
            self._recording = True
        try:
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="float32",
                blocksize=int(SAMPLE_RATE * 0.05),  # 50 ms blocks -> low segmentation lag
                callback=self._callback,
            )
            self._stream.start()
        except Exception:
            with self._lock:
                self._recording = False
            self._stream = None
            raise

    def stop(self) -> np.ndarray:
        with self._lock:
            self._recording = False
            frames = self._frames
            self._frames = []
            self._on_chunk = None
        stream, self._stream = self._stream, None
        if stream is not None:
            stream.stop()
            stream.close()
        if not frames:
            return np.zeros((0,), dtype=np.float32)
        return np.concatenate(frames)
