import sqlite3

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .config import db_path, index_path, model_dir
from .search import search
from .store import connect, corpus, document, init
from .translate import ProviderError, translate


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    category: str | None = Field(default=None, pattern="^(sutta|vinaya|abhidhamma)$")
    method: str = Field(default="hybrid", pattern="^(hybrid|vector|lexical)$")


class TranslateRequest(BaseModel):
    text_id: str = Field(min_length=1, max_length=100)
    segment_ids: list[str] = Field(min_length=1, max_length=100)
    provider: str = Field(default="ollama", pattern="^(ollama|gemini|azure)$")


def create_app():
    app = FastAPI(title="Sutta local API", version="0.1.0")

    def require_corpus():
        if not db_path().exists():
            raise HTTPException(503, "Corpus is not imported; run sutta ingest")

    @app.get("/health")
    def health():
        database = "missing"
        revision = None
        if db_path().exists():
            try:
                with connect() as conn:
                    database = "ready" if conn.execute("SELECT count(*) FROM documents").fetchone()[0] else "empty"
                    revision_row = conn.execute("SELECT value FROM metadata WHERE key='revision'").fetchone()
                    revision = revision_row[0] if revision_row else None
            except sqlite3.Error:
                database = "error"
        index = "missing"
        index_scope = None
        if index_path().exists():
            from .index import vec_connect
            try:
                conn = vec_connect(index_path())
                try:
                    meta = dict(conn.execute("SELECT key,value FROM metadata"))
                    chunks = conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
                    vectors = conn.execute("SELECT count(*) FROM vectors").fetchone()[0]
                    index = "ready_experimental" if chunks == vectors and meta.get("source_revision") == revision else "inconsistent"
                    index_scope = meta.get("scope")
                finally:
                    conn.close()
            except sqlite3.Error:
                index = "error"
        translation = "unavailable"
        try:
            r = httpx.get("http://127.0.0.1:11434/api/tags", timeout=2, trust_env=False)
            if r.is_success:
                translation = "experimental_local_available"
        except httpx.HTTPError:
            pass
        return {"database": database, "index": index, "index_scope": index_scope,
                "embedding": "installed" if (model_dir()/"onnx/model.onnx").exists() else "missing",
                "translation": translation, "human_review": "pending", "bind": "127.0.0.1"}

    @app.get("/v1/corpus")
    def corpus_info():
        require_corpus()
        with connect() as conn:
            init(conn)
            return corpus(conn)

    @app.get("/v1/texts/{text_id}")
    def text(text_id: str, companion: bool = False):
        require_corpus()
        try:
            with connect() as conn:
                doc = document(conn, text_id)
        except KeyError:
            raise HTTPException(404, "Unknown document") from None
        from .search import result
        response = result(doc, list(doc["pali"]), "identifier", context=0)
        if companion:
            response["human_english"] = doc["english"]
        return response

    @app.post("/v1/search")
    def find(request: SearchRequest):
        require_corpus()
        try:
            return search(request.query, request.top_k, request.category, request.method)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        except (RuntimeError, sqlite3.Error, FileNotFoundError) as exc:
            raise HTTPException(503, str(exc)) from None

    @app.post("/v1/translate")
    def thai(request: TranslateRequest):
        require_corpus()
        try:
            return translate(request.text_id, request.segment_ids, request.provider)
        except KeyError:
            raise HTTPException(404, "Unknown document") from None
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        except (httpx.HTTPError, ProviderError):
            # Do not expose upstream URLs, query parameters, keys or provider response bodies.
            raise HTTPException(503, "Translation provider unavailable; search and reading remain available") from None
    return app


app = create_app()
