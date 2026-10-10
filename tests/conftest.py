import json

import pytest

from sutta.ingest import ingest


@pytest.fixture
def dataset(tmp_path, monkeypatch):
    monkeypatch.setenv("SUTTA_DATA", str(tmp_path / "data"))
    root = tmp_path / "upstream/root/pli/ms/sutta/mn"
    trans = tmp_path / "upstream/translation/en/sujato/sutta/mn"
    root.mkdir(parents=True)
    trans.mkdir(parents=True)
    pali = {"mn1:1.1": "ไทย, ā \"x\"\n ", "mn1:1.2": "not ", "mn1:1.10": "last "}
    english = {"mn1:1.1": "first ", "mn1:1.2": "not ", "mn1:1.10": "last "}
    (root / "mn1_root-pli-ms.json").write_text(json.dumps(pali, ensure_ascii=False), encoding="utf-8")
    (trans / "mn1_translation-en-sujato.json").write_text(json.dumps(english), encoding="utf-8")
    ingest(tmp_path / "upstream", require_revision=False)
    return tmp_path / "upstream", pali
