import hashlib
import json
import sqlite3
import zlib
from contextlib import contextmanager

from .config import db_path


def pack(value):
    return zlib.compress(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode(), 9)


def unpack(value):
    return json.loads(zlib.decompress(value))


def digest(value):
    return hashlib.sha256(value).hexdigest()


@contextmanager
def connect(path=None):
    path = path or db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=60)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def init(conn):
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS documents(
      text_id TEXT PRIMARY KEY, category TEXT NOT NULL, source_path TEXT NOT NULL,
      revision TEXT NOT NULL, raw BLOB NOT NULL, sha256 TEXT NOT NULL, translator TEXT, translation_path TEXT, translation_raw BLOB,
      translation_sha256 TEXT, segment_count INTEGER NOT NULL, aligned_count INTEGER NOT NULL,
      coverage TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS aliases(alias TEXT PRIMARY KEY,text_id TEXT NOT NULL) WITHOUT ROWID;
    CREATE INDEX IF NOT EXISTS alias_document ON aliases(text_id);
    CREATE TABLE IF NOT EXISTS manifest(
      path TEXT PRIMARY KEY, status TEXT NOT NULL, sha256 TEXT, error TEXT);
    CREATE TABLE IF NOT EXISTS translations(
      cache_key TEXT PRIMARY KEY, response TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS spending(
      id TEXT PRIMARY KEY, reserved REAL NOT NULL, actual REAL, status TEXT NOT NULL);
    ''')


def document(conn, text_id):
    row = conn.execute("SELECT * FROM documents WHERE text_id=?", (text_id,)).fetchone()
    if row is None:
        raise KeyError(text_id)
    result = dict(row)
    edition = conn.execute("SELECT value FROM metadata WHERE key='edition'").fetchone()
    result["edition"] = edition[0] if edition else "unverified"
    result["pali"] = json.loads(zlib.decompress(result["raw"]))
    original_translation = json.loads(zlib.decompress(result["translation_raw"])) if result["translation_raw"] else {}
    result["english"] = {k: v for k, v in original_translation.items() if k in result["pali"] and v.strip()}
    return result


def corpus(conn):
    total = conn.execute("SELECT count(*),coalesce(sum(segment_count),0),coalesce(sum(aligned_count),0) FROM documents").fetchone()
    metadata = dict(conn.execute("SELECT key,value FROM metadata").fetchall())
    return {
        "documents": total[0], "segments": total[1], "aligned_segments": total[2],
        "coverage": dict(conn.execute("SELECT coverage,count(*) FROM documents GROUP BY coverage").fetchall()),
        "categories": dict(conn.execute("SELECT category,count(*) FROM documents GROUP BY category").fetchall()),
        "manifest": dict(conn.execute("SELECT status,count(*) FROM manifest GROUP BY status").fetchall()),
        "metadata": metadata,
        "source_status": "validated" if metadata.get("verified_documents") == str(total[0]) else "imported_unverified" if total[0] else "empty",
        "search_status": "experimental", "translation_status": "experimental",
    }
