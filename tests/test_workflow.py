
import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from sutta.api import create_app
from sutta.index import chunk_document, vec_connect
from sutta.ingest import ingest, read_json, verify_source
from sutta.search import search
from sutta.store import connect, corpus, document
from sutta.translate import reserve, translate


def test_lossless_order_and_resume(dataset):
    upstream, pali = dataset
    assert verify_source() == {"checked_documents": 1, "lossless": True}
    ingest(upstream, require_revision=False)
    with connect() as conn:
        doc = document(conn, "mn1")
        assert doc["pali"] == pali
        assert list(doc["pali"]) == ["mn1:1.1", "mn1:1.2", "mn1:1.10"]
        assert corpus(conn)["documents"] == 1
        assert doc["coverage"] == "complete"


def test_duplicate_keys_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        read_json(b'{"mn1:1":"a","mn1:1":"b"}')


def test_wrong_document_failed(dataset):
    upstream, _ = dataset
    file = upstream / "root/pli/ms/sutta/mn/mn2_root-pli-ms.json"
    file.write_text('{"mn1:1.1":"wrong"}', encoding="utf-8")
    with pytest.raises(ValueError, match="failed"):
        ingest(upstream, require_revision=False)
    with connect() as conn:
        assert corpus(conn)["manifest"] == {"imported": 1, "failed": 1}


def test_partial_coverage(dataset):
    upstream, _ = dataset
    (upstream / "root/pli/ms/sutta/mn/mn2_root-pli-ms.json").write_text(
        '{"mn2:1":"a", "mn2:2":"b"}', encoding="utf-8")
    (upstream / "translation/en/sujato/sutta/mn/mn2_translation-en-sujato.json").write_text(
        '{"mn2:1":"a", "mn999:1":"not aligned"}', encoding="utf-8")
    ingest(upstream, require_revision=False)
    with connect() as conn:
        doc = document(conn, "mn2")
        assert doc["coverage"] == "partial"
        assert list(doc["english"]) == ["mn2:1"]


def test_exact_search_without_model(dataset):
    r = search("mn1:1.10")
    assert r["results"][0]["original_pali"] == {"mn1:1.10": "last "}
    assert search("mn1:9.9")["results"] == []
    assert len(search("mn1")["results"][0]["segment_ids"]) == 3
    assert search("mn999:1.1")["results"] == []


def test_range_container_alias(dataset):
    upstream, _ = dataset
    (upstream / "root/pli/ms/sutta/mn/mn2-10_root-pli-ms.json").write_text(
        '{"mn2:1.1":"a", "mn3-10:1.1":"b"}', encoding="utf-8")
    ingest(upstream, require_revision=False)
    assert search("mn3-10:1.1")["results"][0]["text_id"] == "mn2-10"
    assert search("mn2")["results"][0]["original_pali"] == {"mn2:1.1": "a"}


def test_long_segments_have_offsets_and_no_loss():
    doc = {"pali": {"a:1": "abcdefghij", "a:2": "x"}, "english": {}}
    chunks = list(chunk_document(doc, len, max_tokens=3))
    assert "".join(x[2] for x in chunks) == "abcdefghijx"
    assert all(len(x[2]) <= 3 for x in chunks)
    assert chunks[0][3] == [0, 3]


def test_language_boundaries():
    doc = {"pali": {"a:1": "p1", "a:2": "p2", "a:3": "p3"}, "english": {"a:2": "e2"}}
    chunks = list(chunk_document(doc, len))
    assert [x[0] for x in chunks] == ["pli", "en", "pli"]


def test_sqlite_vec_filter():
    conn = vec_connect(":memory:")
    conn.execute("CREATE VIRTUAL TABLE vectors USING vec0(embedding float[384])")
    for i in range(1, 4):
        v = np.zeros(384, dtype=np.float32)
        v[i] = 1
        conn.execute("INSERT INTO vectors(rowid,embedding) VALUES(?,?)", (i, v.tobytes()))
    v = np.zeros(384, dtype=np.float32)
    result = conn.execute("SELECT rowid FROM vectors WHERE embedding MATCH ? AND k=2 AND rowid IN (2,3)",
                          (v.tobytes(),)).fetchall()
    assert {r[0] for r in result} == {2, 3}
    conn.close()


def test_translation_failure_does_not_break_reading(dataset, monkeypatch):
    def fail(*args, **kwargs):
        raise httpx.ConnectError("offline")
    monkeypatch.setattr(httpx.Client, "post", fail)
    client = TestClient(create_app())
    assert client.post("/v1/translate", json={"text_id": "mn1", "segment_ids": ["mn1:1.1"]}).status_code == 503
    assert client.get("/v1/texts/mn1").status_code == 200
    assert client.post("/v1/search", json={"query": "mn1"}).status_code == 200


def test_malformed_provider_is_unavailable(dataset, monkeypatch):
    def malformed(*args, **kwargs):
        return httpx.Response(200, json={}, request=httpx.Request("POST", "http://localhost"))
    monkeypatch.setattr(httpx.Client, "post", malformed)
    client = TestClient(create_app())
    assert client.post("/v1/translate", json={"text_id": "mn1", "segment_ids": ["mn1:1.1"]}).status_code == 503
    assert client.get("/v1/texts/mn1").status_code == 200


def test_translation_cache_and_provenance(dataset, monkeypatch):
    calls = []
    def answer(*args, **kwargs):
        calls.append(kwargs["json"])
        return httpx.Response(200, json={"response": "คำแปลทดลอง", "done_reason": "stop"},
                              request=httpx.Request("POST", "http://localhost"))
    monkeypatch.setattr(httpx.Client, "post", answer)
    first = translate("mn1", ["mn1:1.1"])
    second = translate("mn1", ["mn1:1.1"])
    assert len(calls) == 1 and second["cached"]
    assert first["via_language"] == "en" and first["human_review"] == "pending"
    assert first["original_pali"]["mn1:1.1"].startswith("ไทย")


def test_translation_rejects_noncontiguous_and_unknown(dataset):
    for sids in (["mn1:1.1", "mn1:1.10"], ["mn1:1.2", "mn1:1.1"], ["bad:1"], ["mn1:1.1"]*2):
        with pytest.raises(ValueError):
            translate("mn1", sids)


def test_cloud_requires_explicit_configuration(dataset, monkeypatch):
    monkeypatch.delenv("SUTTA_AZURE_CONFIRMED", raising=False)
    monkeypatch.delenv("SUTTA_GEMINI_FREE_CONFIRMED", raising=False)
    for provider in ("azure", "gemini"):
        with pytest.raises(ValueError):
            translate("mn1", ["mn1:1.1"], provider)


def test_gemini_adapter_with_mocked_response(dataset, monkeypatch):
    monkeypatch.setenv("SUTTA_GEMINI_FREE_CONFIRMED", "1")
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    monkeypatch.setenv("SUTTA_GEMINI_MODEL", "fixture-model")
    def answer(self, url, **kwargs):
        assert kwargs["headers"]["x-goog-api-key"] == "fake"
        return httpx.Response(200, json={"candidates": [{"finishReason": "STOP",
            "content": {"parts": [{"text": "Thai fixture"}]}}]}, request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx.Client, "post", answer)
    response = translate("mn1", ["mn1:1.1"], "gemini")
    assert response["provider"] == "gemini" and response["via_language"] == "en"


def test_budget_persists_failures_and_blocks(dataset):
    with connect() as conn:
        reserve(conn, 34)
    with connect() as conn:
        with pytest.raises(ValueError, match="budget"):
            reserve(conn, 2)
        assert conn.execute("SELECT sum(reserved) FROM spending").fetchone()[0] == 34


def test_azure_failure_retry_reserves_again(dataset, monkeypatch):
    config = {"SUTTA_AZURE_CONFIRMED": "1", "SUTTA_AZURE_ENDPOINT": "https://example.invalid/chat",
              "SUTTA_AZURE_KEY": "fake", "SUTTA_AZURE_MODEL": "fixture",
              "SUTTA_AZURE_INPUT_USD_PER_MILLION": "1", "SUTTA_AZURE_OUTPUT_USD_PER_MILLION": "2"}
    for key, value in config.items():
        monkeypatch.setenv(key, value)
    def failure(*args, **kwargs):
        raise httpx.ReadTimeout("fixture timeout")
    monkeypatch.setattr(httpx.Client, "post", failure)
    for _ in range(2):
        with pytest.raises(httpx.ReadTimeout):
            translate("mn1", ["mn1:1.1"], "azure")
    with connect() as conn:
        rows = conn.execute("SELECT reserved,actual,status FROM spending").fetchall()
        assert len(rows) == 2
        assert all(r[0] > 0 and r[1] is None and r[2] == "reserved" for r in rows)


def test_azure_settles_reported_usage(dataset, monkeypatch):
    for key, value in {"SUTTA_AZURE_CONFIRMED": "1", "SUTTA_AZURE_ENDPOINT": "https://example.invalid/chat",
              "SUTTA_AZURE_KEY": "fake", "SUTTA_AZURE_MODEL": "fixture",
              "SUTTA_AZURE_INPUT_USD_PER_MILLION": "1", "SUTTA_AZURE_OUTPUT_USD_PER_MILLION": "2"}.items():
        monkeypatch.setenv(key, value)
    def answer(*args, **kwargs):
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": "Thai"}}],
                                       "usage": {"prompt_tokens": 100, "completion_tokens": 50}},
                              request=httpx.Request("POST", "https://example.invalid"))
    monkeypatch.setattr(httpx.Client, "post", answer)
    translate("mn1", ["mn1:1.1"], "azure")
    with connect() as conn:
        row = conn.execute("SELECT actual,status FROM spending").fetchone()
        assert row[0] == pytest.approx(.0002) and row[1] == "settled"


def test_budget_concurrent_requests(dataset):
    from concurrent.futures import ThreadPoolExecutor
    def try_reserve(_):
        with connect() as conn:
            try:
                return reserve(conn, 20)
            except ValueError:
                return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(try_reserve, range(2)))
    assert sum(r is not None for r in results) == 1


def test_api_uninitialized(tmp_path, monkeypatch):
    monkeypatch.setenv("SUTTA_DATA", str(tmp_path))
    client = TestClient(create_app())
    assert client.get("/v1/corpus").status_code == 503
    assert client.get("/v1/texts/mn1").status_code == 503


def test_api_validation(dataset):
    client = TestClient(create_app())
    assert client.get("/v1/corpus").json()["documents"] == 1
    assert client.get("/v1/texts/unknown").status_code == 404
    assert client.post("/v1/search", json={"query": "x", "top_k": 0}).status_code == 422
    assert client.post("/v1/search", json={"query": "x", "category": "wrong"}).status_code == 422
    assert client.get("/v1/texts/mn1?companion=true").json()["human_english"]


def test_unavailable_direct_pali(dataset):
    with connect() as conn:
        conn.execute("UPDATE documents SET translation_raw=NULL,aligned_count=0,coverage='none'")
    assert translate("mn1", ["mn1:1.1"])["status"] == "translation_unavailable"


def test_corruption_detected(dataset):
    with connect() as conn:
        conn.execute("UPDATE documents SET sha256='bad'")
    with pytest.raises(ValueError, match="mismatch"):
        verify_source()
