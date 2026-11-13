# -*- coding: utf-8 -*-
import io
import os
import socket
import tarfile
from unittest import mock

import pytest

import model_download as md

NAME = "fake-model"


def make_archive(path):
    with tarfile.open(path, "w:bz2") as tar:
        data = b"weights"
        info = tarfile.TarInfo(f"{NAME}/model.onnx")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))


def test_downloads_and_extracts(tmp_path, monkeypatch):
    src = tmp_path / "src"
    src.mkdir()
    make_archive(src / f"{NAME}.tar.bz2")
    monkeypatch.setattr(md, "_BASE", src.as_uri() + "/")
    out = md.ensure_model_dir(str(tmp_path / "models"), NAME)
    assert open(os.path.join(out, "model.onnx"), "rb").read() == b"weights"
    # second call is a no-op (no network)
    monkeypatch.setattr(md, "_download", mock.Mock(side_effect=AssertionError))
    assert md.ensure_model_dir(str(tmp_path / "models"), NAME) == out


def test_manually_downloaded_archive_is_used_without_network(tmp_path, monkeypatch):
    models = tmp_path / "models"
    models.mkdir()
    make_archive(models / f"{NAME}.tar.bz2")
    monkeypatch.setattr(md, "_download", mock.Mock(side_effect=AssertionError("no network")))
    out = md.ensure_model_dir(str(models), NAME)
    assert os.path.isfile(os.path.join(out, "model.onnx"))


def test_stalled_download_fails_with_clear_error_and_leaves_no_partial_model(tmp_path, monkeypatch):
    resp = mock.MagicMock()
    resp.__enter__.return_value = resp
    resp.headers = {"Content-Length": "100"}
    resp.read.side_effect = socket.timeout()
    monkeypatch.setattr(md.urllib.request, "urlopen", lambda *a, **k: resp)
    with pytest.raises(TimeoutError, match="LOCALASR_DOWNLOAD_BASE"):
        md.ensure_model_dir(str(tmp_path), NAME)
    assert os.listdir(tmp_path) == []
