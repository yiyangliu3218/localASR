# -*- coding: utf-8 -*-
"""Downloads sherpa-onnx models from GitHub releases on first use (free, no account).

If GitHub is slow or blocked on your network, either
  * set LOCALASR_DOWNLOAD_BASE to a mirror of the release URL, or
  * download the files in a browser and put them in MODELS_DIR (see README).
"""
import os
import socket
import ssl
import sys
import tarfile
import tempfile
import time
import urllib.request

_BASE = os.environ.get(
    "LOCALASR_DOWNLOAD_BASE",
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/",
)
SENSEVOICE = "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17"
SILERO_VAD = "silero_vad.onnx"
_TIMEOUT_S = 30  # no bytes for this long -> fail with an error instead of hanging forever


def _ssl_context():
    """python.org builds of Python on macOS ship without system root certificates
    (CERTIFICATE_VERIFY_FAILED); use certifi's CA bundle when it is installed.
    An explicit SSL_CERT_FILE (e.g. a corporate proxy's CA) always wins."""
    if os.environ.get("SSL_CERT_FILE"):
        return ssl.create_default_context(cafile=os.environ["SSL_CERT_FILE"])
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _log(msg):
    print(f"[model] {msg}", file=sys.stderr, flush=True)


def _download(url: str, dest: str):
    _log(f"downloading {url}")
    t0 = last = time.time()
    with urllib.request.urlopen(url, timeout=_TIMEOUT_S, context=_ssl_context()) as resp, open(dest, "wb") as f:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while True:
            try:
                chunk = resp.read(1 << 20)
            except socket.timeout as exc:
                raise TimeoutError(
                    f"下载超时（{_TIMEOUT_S}s 没有收到数据）: {url}\n"
                    "GitHub 在你的网络上可能被限速/屏蔽。可以设置 LOCALASR_DOWNLOAD_BASE 换镜像，"
                    "或用浏览器手动下载后放进模型目录（见 README）。"
                ) from exc
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if time.time() - last > 1:
                last = time.time()
                pct = f"{done * 100 / total:5.1f}%" if total else ""
                speed = done / 1e6 / (last - t0)
                _log(f"  {pct} {done / 1e6:7.1f} MB  {speed:.1f} MB/s")
    _log(f"  done: {done / 1e6:.1f} MB in {time.time() - t0:.0f}s")


def ensure_model_dir(models_dir: str, name: str) -> str:
    """Returns <models_dir>/<name>, downloading and extracting the tarball if needed."""
    target = os.path.join(models_dir, name)
    if os.path.isdir(target):
        return target
    os.makedirs(models_dir, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=models_dir) as tmp:
        archive = os.path.join(tmp, name + ".tar.bz2")
        # A manually downloaded archive dropped into MODELS_DIR is used as-is
        manual = os.path.join(models_dir, name + ".tar.bz2")
        if os.path.isfile(manual):
            archive = manual
        else:
            _download(_BASE + name + ".tar.bz2", archive)
        _log(f"extracting {os.path.basename(archive)}")
        with tarfile.open(archive) as tar:
            tar.extractall(tmp, filter="data")
        os.replace(os.path.join(tmp, name), target)  # atomic: no half-extracted model dirs
    _log(f"ready: {target}")
    return target


def ensure_file(models_dir: str, name: str) -> str:
    target = os.path.join(models_dir, name)
    if os.path.isfile(target):
        return target
    os.makedirs(models_dir, exist_ok=True)
    tmp = target + ".part"
    _download(_BASE + name, tmp)
    os.replace(tmp, target)
    return target
