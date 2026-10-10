import hashlib

import httpx
import pytest

from sutta.model_download import ranged_download


def test_ranged_download_checks_digest_before_activation(tmp_path, monkeypatch):
    body = b"model bytes"
    def handler(request):
        return httpx.Response(206, content=body, headers={"content-range": f"bytes 0-{len(body)-1}/{len(body)}"})
    real_client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: real_client(transport=httpx.MockTransport(handler)))
    destination = tmp_path/"model.onnx_data"
    ranged_download("https://example.invalid/model", destination, len(body), hashlib.sha256(body).hexdigest())
    assert destination.read_bytes() == body
    assert not destination.with_suffix(".onnx_data.range.partial").exists()


def test_wrong_range_not_activated(tmp_path, monkeypatch):
    def handler(request):
        return httpx.Response(200, content=b"wrong")
    real_client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: real_client(transport=httpx.MockTransport(handler)))
    destination = tmp_path/"model.onnx_data"
    with pytest.raises(ValueError, match="range"):
        ranged_download("https://example.invalid/model", destination, 5, "bad")
    assert not destination.exists()


def test_existing_corrupt_model_not_overwritten(tmp_path):
    destination = tmp_path/"model.onnx_data"
    destination.write_bytes(b"custom")
    with pytest.raises(ValueError, match="Existing"):
        ranged_download("https://example.invalid/model", destination, 5, "bad")
    assert destination.read_bytes() == b"custom"


def test_multiple_ranges_written_at_correct_offsets(tmp_path, monkeypatch):
    body = b"0123456789abcdef"
    seen = []
    def handler(request):
        start, end = map(int, request.headers["Range"].removeprefix("bytes=").split("-"))
        seen.append((start, end))
        return httpx.Response(206, content=body[start:end+1],
                              headers={"content-range": f"bytes {start}-{end}/{len(body)}"})
    real_client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: real_client(transport=httpx.MockTransport(handler)))
    destination = tmp_path/"model.onnx_data"
    ranged_download("https://example.invalid/model", destination, len(body),
                    hashlib.sha256(body).hexdigest(), step=5)
    assert destination.read_bytes() == body
    assert sorted(seen) == [(0, 4), (5, 9), (10, 14), (15, 15)]
