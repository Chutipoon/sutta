import json
import os
import sqlite3
import time
import unicodedata
from contextlib import contextmanager

import sqlite_vec

from .config import db_path, index_path
from .embedding import encoder
from .store import connect, document


def vec_connect(path):
    conn = sqlite3.connect(path, timeout=60)
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    return conn


def chunk_document(doc, count, max_tokens=384):
    # No overlap; splitting a long segment uses explicit character offsets in the chosen language.
    group = []
    language = None
    for sid, pali in doc["pali"].items():
        lang = "en" if sid in doc["english"] else "pli"
        text = doc["english"].get(sid, pali)
        if group and (lang != language or count("".join(x[1] for x in group) + text) > max_tokens):
            yield language, [x[0] for x in group], "".join(x[1] for x in group), None
            group = []
        language = lang
        if count(text) > max_tokens:
            if group:
                yield language, [x[0] for x in group], "".join(x[1] for x in group), None
                group = []
            start = 0
            while start < len(text):
                low, high = start + 1, len(text)
                while low < high:
                    mid = (low + high + 1) // 2
                    if count(text[start:mid]) <= max_tokens:
                        low = mid
                    else:
                        high = mid - 1
                yield lang, [sid], text[start:low], [start, low]
                start = low
        else:
            group.append((sid, text))
    if group:
        yield language, [x[0] for x in group], "".join(x[1] for x in group), None


@contextmanager
def index_lock(output):
    output.parent.mkdir(parents=True, exist_ok=True)
    lock = output.with_suffix(".lock")
    try:
        with lock.open("x", encoding="utf-8") as file:
            file.write(str(os.getpid()))
    except FileExistsError:
        raise RuntimeError(f"Index build locked: {lock}. Check its process before removing a stale lock.") from None
    try:
        yield
    finally:
        lock.unlink(missing_ok=True)


def build(limit=None, mode="companion", output=None, categories=None, text_ids=None, profile="e5"):
    output = output or index_path()
    with index_lock(output):
        return _build(limit, mode, output, categories, text_ids, profile)


def _build(limit=None, mode="companion", output=None, categories=None, text_ids=None, profile="e5"):
    model = encoder(profile)
    output = output or index_path()
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix(".building.sqlite")
    if temp.exists():
        temp.unlink()
    conn = vec_connect(temp)
    conn.executescript('''
    CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    CREATE TABLE chunks(id INTEGER PRIMARY KEY,text_id TEXT NOT NULL,segment_ids TEXT NOT NULL,
      language TEXT NOT NULL,offsets TEXT,category TEXT NOT NULL);
    CREATE VIRTUAL TABLE lexical USING fts5(text,content='',tokenize='unicode61 remove_diacritics 0');
    ''')
    conn.execute(f"CREATE VIRTUAL TABLE vectors USING vec0(embedding float[{model.dimension}])")
    started = time.perf_counter()
    batch = []
    count_docs = 0
    chunk_id = 0

    def flush():
        if not batch:
            return
        vectors = model.encode([x[1] for x in batch])
        for (cid, _), vector in zip(batch, vectors, strict=True):
            conn.execute("INSERT INTO vectors(rowid,embedding) VALUES(?,?)", (cid, vector.tobytes()))
        conn.commit()
        batch.clear()

    try:
        with connect(db_path()) as corpus:
            source_revision = corpus.execute("SELECT value FROM metadata WHERE key='revision'").fetchone()[0]
            ids = corpus.execute("SELECT text_id,category FROM documents ORDER BY category,text_id").fetchall()
            if categories:
                ids = [r for r in ids if r["category"] in categories]
            if text_ids:
                ids = [r for r in ids if r["text_id"] in text_ids]
            # Round-robin categories provides a pilot covering all three baskets.
            if limit:
                buckets = {}
                for r in ids:
                    buckets.setdefault(r["category"], []).append(r)
                ids = [bucket[i] for i in range(max(map(len, buckets.values())))
                       for bucket in buckets.values() if i < len(bucket)][:limit]
            for row in ids:
                doc = document(corpus, row["text_id"])
                if mode == "pali":
                    doc["english"] = {}
                for lang, sids, text, offsets in chunk_document(doc, model.count):
                    chunk_id += 1
                    conn.execute("INSERT INTO chunks VALUES(?,?,?,?,?,?)",
                                 (chunk_id, doc["text_id"], json.dumps(sids), lang,
                                  json.dumps(offsets) if offsets else None, doc["category"]))
                    conn.execute("INSERT INTO lexical(rowid,text) VALUES(?,?)",
                                 (chunk_id, unicodedata.normalize("NFC", text)))
                    batch.append((chunk_id, text))
                    if len(batch) >= 16:
                        flush()
                    if chunk_id % 256 == 0:
                        print(f"Indexed {chunk_id} chunks ({count_docs}/{len(ids)} documents)", flush=True)
                count_docs += 1
                if count_docs % 100 == 0:
                    print(f"Indexed {count_docs}/{len(ids)} documents, {chunk_id} chunks", flush=True)
        flush()
        meta = {"source_revision": source_revision, "model": model.fingerprint,
                "mode": mode, "documents": str(count_docs), "chunks": str(chunk_id),
                "scope": "pilot" if limit or categories or text_ids else "full", "quality": "experimental"}
        conn.executemany("INSERT INTO metadata VALUES(?,?)", meta.items())
        conn.execute("INSERT INTO lexical(lexical) VALUES('optimize')")
        conn.commit()
        conn.close()
        os.replace(temp, output)
    except BaseException:
        conn.close()
        raise
    return {**meta, "seconds": round(time.perf_counter() - started, 2), "bytes": output.stat().st_size}
