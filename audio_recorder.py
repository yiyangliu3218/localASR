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
        self._max_frames = SAMPLE_RATE * MAX_RECORD_SECONDS

    def _callback(self, indata, frames, time_info, status):
        with self._lock:
            if not self._recording:
                return
            self._frames.append(indata.copy())
            self._num_frames += frames
            if self._num_frames >= self._max_frames:
                self._recording = False

    def start(self):
        with self._lock:
            if self._recording:
                return
            self._frames = []
            self._num_frames = 0
            self._recording = True
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> np.ndarray:
        with self._lock:
            self._recording = False
            frames = self._frames
            self._frames = []
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        if not frames:
            return np.zeros((0,), dtype=np.float32)
        return np.concatenate(frames, axis=0).reshape(-1)
