# -*- coding: utf-8 -*-
"""Accuracy + latency benchmark for local zh/en ASR engines.

Usage:
    python bench/run_bench.py --models-root ~/asr-models [--engines sensevoice,whisper-turbo] [--mlx]

Download models (free, no account) with bench/download_models.sh.
"""
import argparse
import json
import os
import statistics
import sys
import time

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engines  # noqa: E402
from metrics import mer  # noqa: E402
from testset import TESTSET  # noqa: E402

SR = 16000


def load_wav(path):
    a, sr = sf.read(path, dtype="float32")
    assert sr == SR, path
    return a


def timeit(fn, repeat):
    ts, out = [], None
    for _ in range(repeat):
        t0 = time.perf_counter()
        out = fn()
        ts.append(time.perf_counter() - t0)
    return out, statistics.median(ts)


def bench_engine(name, eng, root, repeat):
    eng.transcribe(np.zeros(SR, dtype=np.float32))  # warm-up
    rows, errs, toks = [], {}, {}
    total_audio = total_compute = 0.0
    for cat, rel, ref in TESTSET:
        audio = load_wav(os.path.join(root, rel))
        hyp, t = timeit(lambda: eng.transcribe(audio), repeat)
        e, n = mer(ref, hyp)
        errs[cat] = errs.get(cat, 0) + e
        toks[cat] = toks.get(cat, 0) + n
        dur = len(audio) / SR
        total_audio += dur
        total_compute += t
        rows.append(dict(cat=cat, file=os.path.basename(rel), dur=round(dur, 2),
                         latency=round(t, 3), mer=round(e / n, 3), hyp=hyp))
    summary = {c: round(errs[c] / toks[c], 4) for c in errs}
    summary["all"] = round(sum(errs.values()) / sum(toks.values()), 4)
    return dict(engine=name, rows=rows, mer=summary,
                rtf=round(total_compute / total_audio, 4))


def bench_length_scaling(eng, root, repeat):
    """Latency vs utterance length (what the user waits for after releasing Fn)."""
    base = np.concatenate([load_wav(os.path.join(root, rel)) for _, rel, _ in TESTSET])
    out = {}
    for sec in (2, 5, 10, 20, 30):
        clip = base[: sec * SR]
        _, t = timeit(lambda: eng.transcribe(clip), repeat)
        out[sec] = round(t, 3)
    return out


def bench_streaming(eng, root):
    """For true streaming engines: compute remaining after the key is released."""
    tails = []
    for _, rel, _ in TESTSET:
        _, tail, updates = eng.stream_feed(load_wav(os.path.join(root, rel)), chunk_ms=100)
        tails.append(tail)
    return dict(release_to_text_median_s=round(statistics.median(tails), 3),
                release_to_text_max_s=round(max(tails), 3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models-root", required=True)
    ap.add_argument("--engines", default=",".join(engines.REGISTRY))
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--mlx", action="store_true", help="also bench the app's mlx-whisper config")
    ap.add_argument("--out", default="bench_results.json")
    args = ap.parse_args()

    results = []
    todo = [(k, None) for k in args.engines.split(",") if k]
    if args.mlx:
        todo.append(("mlx-whisper", "mlx"))
    for key, kind in todo:
        t0 = time.perf_counter()
        eng = engines.load_mlx() if kind == "mlx" else engines.load(key, args.models_root, args.threads)
        load_s = time.perf_counter() - t0
        print(f"== {key}: loaded in {load_s:.1f}s", flush=True)
        r = bench_engine(key, eng, args.models_root, args.repeat)
        r["load_s"] = round(load_s, 2)
        r["latency_vs_length_s"] = bench_length_scaling(eng, args.models_root, args.repeat)
        if hasattr(eng, "stream_feed"):
            r["streaming"] = bench_streaming(eng, args.models_root)
        print(json.dumps({k: v for k, v in r.items() if k != "rows"}, ensure_ascii=False), flush=True)
        for row in r["rows"]:
            print(f"   [{row['cat']}] {row['file']:<12} {row['latency']:>6}s mer={row['mer']:<5} {row['hyp']}")
        results.append(r)
    with open(args.out, "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
