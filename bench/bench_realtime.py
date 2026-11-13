# -*- coding: utf-8 -*-
"""Simulates a long dictation (all test clips joined with 0.6 s pauses, ~85 s)
fed in real time, 100 ms at a time, and measures what the user waits for after
releasing the key under three pipelines:

  batch     : current app design - record everything, transcribe on release
  vad+asr   : silero VAD cuts at pauses; each finished segment is transcribed
              in the background while the user is still talking
  streaming : true streaming transducer, text updates every chunk
"""
import argparse
import os
import sys
import time

import numpy as np
import sherpa_onnx
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engines  # noqa: E402
from testset import TESTSET  # noqa: E402

SR = 16000


def build_long(root):
    """Returns (audio, release_points). Release points are mid-sentence (70 % into
    a clip) - the worst case, where the user lets go while still talking."""
    gap = np.zeros(int(0.6 * SR), dtype=np.float32)
    parts, releases, pos = [], [], 0
    for _, rel, _ in TESTSET:
        a, _ = sf.read(os.path.join(root, rel), dtype="float32")
        releases.append(pos + int(0.7 * len(a)))
        parts += [a, gap]
        pos += len(a) + len(gap)
    return np.concatenate(parts), releases


def vad_pipeline(asr, vad_model, audio, chunk_ms=100):
    cfg = sherpa_onnx.VadModelConfig()
    cfg.silero_vad.model = vad_model
    cfg.silero_vad.min_silence_duration = 0.3
    cfg.silero_vad.min_speech_duration = 0.2
    cfg.silero_vad.max_speech_duration = 20
    cfg.sample_rate = SR
    vad = sherpa_onnx.VoiceActivityDetector(cfg, buffer_size_in_seconds=120)
    step = int(SR * chunk_ms / 1000)
    win = cfg.silero_vad.window_size
    pending = np.zeros(0, dtype=np.float32)
    texts, busy_during = [], 0.0
    for i in range(0, len(audio), step):
        pending = np.concatenate([pending, audio[i:i + step]])
        while len(pending) >= win:
            vad.accept_waveform(pending[:win])
            pending = pending[win:]
        while not vad.empty():  # a segment finished while still recording
            t0 = time.perf_counter()
            texts.append(asr.transcribe(np.array(vad.front.samples, dtype=np.float32)))
            busy_during += time.perf_counter() - t0
            vad.pop()
    # key released
    t0 = time.perf_counter()
    vad.flush()
    while not vad.empty():
        texts.append(asr.transcribe(np.array(vad.front.samples, dtype=np.float32)))
        vad.pop()
    tail = time.perf_counter() - t0
    return "".join(texts), tail, busy_during


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models-root", required=True)
    ap.add_argument("--threads", type=int, default=4)
    a = ap.parse_args()
    audio, releases = build_long(a.models_root)
    print(f"long dictation: {len(audio) / SR:.1f}s of audio; releasing mid-sentence at "
          f"{len(releases[3:])} points between {releases[3] / SR:.0f}s and {releases[-1] / SR:.0f}s")
    vad = os.path.join(a.models_root, "silero_vad.onnx")
    for key in ("sensevoice", "whisper-turbo"):
        asr = engines.load(key, a.models_root, a.threads)
        asr.transcribe(np.zeros(SR, dtype=np.float32))
        if key == "sensevoice":
            bt = []
            for r in (releases[3], releases[6], releases[-1]):
                t0 = time.perf_counter()
                asr.transcribe(audio[:r])
                bt.append(f"{r / SR:.0f}s audio -> {time.perf_counter() - t0:.2f}s")
            print(f"[batch    ] {key:14} release->text: " + ", ".join(bt))
        else:
            print(f"[batch    ] {key:14} release->text: see run_bench latency_vs_length "
                  "(>30 s needs several sequential 30 s windows)")
        tails, busy = [], 0.0
        for r in releases[3:]:
            _, tail, b = vad_pipeline(asr, vad, audio[:r])
            tails.append(tail)
            busy = max(busy, b)
        print(f"[vad+asr  ] {key:14} release->text median {np.median(tails):.2f}s max {max(tails):.2f}s "
              f"(max background work while talking: {busy:.1f}s)")
    z = engines.load("stream-zipformer", a.models_root, a.threads)
    tails = [z.stream_feed(audio[:r])[1] for r in releases[3:]]
    print(f"[streaming] stream-zipformer release->text median {np.median(tails):.2f}s max {max(tails):.2f}s")


if __name__ == "__main__":
    main()
