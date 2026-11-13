# -*- coding: utf-8 -*-
"""Downloads sherpa-onnx models from GitHub releases on first use (free, no account)."""
import os
import tarfile
import tempfile
import urllib.request

_BASE = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
SENSEVOICE = "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17"
SILERO_VAD = "silero_vad.onnx"


def ensure_model_dir(models_dir: str, name: str) -> str:
    """Returns <models_dir>/<name>, downloading and extracting the tarball if needed."""
    target = os.path.join(models_dir, name)
    if os.path.isdir(target):
        return target
    os.makedirs(models_dir, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=models_dir) as tmp:
        archive = os.path.join(tmp, name + ".tar.bz2")
        urllib.request.urlretrieve(_BASE + name + ".tar.bz2", archive)
        with tarfile.open(archive) as tar:
            tar.extractall(tmp, filter="data")
        os.replace(os.path.join(tmp, name), target)  # atomic: no half-extracted model dirs
    return target


def ensure_file(models_dir: str, name: str) -> str:
    target = os.path.join(models_dir, name)
    if os.path.isfile(target):
        return target
    os.makedirs(models_dir, exist_ok=True)
    tmp = target + ".part"
    urllib.request.urlretrieve(_BASE + name, tmp)
    os.replace(tmp, target)
    return target
