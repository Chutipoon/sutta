import json
import re
import sqlite3
import subprocess
import zlib
from pathlib import Path

from .config import PRIORITY, REVISION, SOURCE
from .store import connect, corpus, digest, init


def read_json(raw):
    # Dict insertion order is the source order, never lexicographic segment order.
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError(f"Duplicate JSON key: {key}")
            out[key] = value
        return out
    value = json.loads(raw, object_pairs_hook=unique)
    if not isinstance(value, dict) or not value or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in value.items()
    ):
        raise ValueError("Expected a nonempty segment-to-string object")
    return value


def belongs(container, segment_document):
    if container == segment_document:
        return True
    match = re.fullmatch(r"(.*?)(\d+)-(\d+)", container)
    if not match:
        return False
    prefix, low, high = match.groups()
    suffix = segment_document.removeprefix(prefix)
    if not segment_document.startswith(prefix):
        return False
    parts = suffix.split("-")
    return len(parts) <= 2 and all(x.isdigit() for x in parts) and int(low) <= int(parts[0]) <= int(parts[-1]) <= int(high)


def ingest(upstream, path=None, require_revision=True):
    upstream = Path(upstream).resolve()
    if require_revision:
        head = subprocess.check_output(["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True).strip()
        if head != REVISION:
            raise ValueError(f"Source revision mismatch: {head}")
        changed = subprocess.check_output(["git", "-C", str(upstream), "status", "--porcelain"], text=True)
        if changed.strip():
            raise ValueError("Upstream has local changes; restore them before importing")
    files = sorted((upstream / "root/pli/ms").rglob("*.json"))
    if not files:
        raise ValueError("No Pali root files found")
    if require_revision:
        tracked = subprocess.check_output(
            ["git", "-C", str(upstream), "ls-tree", "-r", "--name-only", REVISION, "root/pli/ms"],
            text=True,
        ).splitlines()
        if {f.relative_to(upstream).as_posix() for f in files} != {f for f in tracked if f.endswith(".json")}:
            raise ValueError("Source checkout is incomplete relative to the pinned Git manifest")
        authors = json.loads((upstream / "_author.json").read_bytes())
        if authors.get("ms", {}).get("name") != "Mahāsaṅgīti Tipiṭaka Buddhavasse 2500":
            raise ValueError("Unexpected Pali edition metadata")
        if any(authors.get(a, {}).get("type") != "translator" for a in PRIORITY):
            raise ValueError("Translation author metadata missing or inconsistent")
        if "CC0" not in (upstream / "LICENSE.md").read_text(encoding="utf-8"):
            raise ValueError("Bilara translation licensing changed; review before importing")
    translations = {}
    for author in PRIORITY:
        for file in sorted((upstream / "translation/en" / author).rglob("*.json")):
            text_id = file.name.split("_translation-")[0]
            translations.setdefault(text_id, (author, file))
    with connect(path) as conn:
        init(conn)
        conn.execute("INSERT OR REPLACE INTO metadata VALUES('revision',?)", (REVISION,))
        conn.execute("INSERT OR REPLACE INTO metadata VALUES('source',?)", (SOURCE,))
        conn.execute("INSERT OR REPLACE INTO metadata VALUES('edition',?)",
                     (authors["ms"]["name"] if require_revision else "test-fixture",))
        if require_revision:
            conn.execute("INSERT OR REPLACE INTO metadata VALUES('translation_license_sha256',?)",
                         (digest((upstream / "LICENSE.md").read_bytes()),))
            conn.execute("INSERT OR REPLACE INTO metadata VALUES('author_metadata_sha256',?)",
                         (digest((upstream / "_author.json").read_bytes()),))
        conn.execute("INSERT OR REPLACE INTO metadata VALUES('expected_documents',?)", (str(len(files)),))
        conn.execute("DELETE FROM metadata WHERE key='verified_documents'")
        for file in files:
            relative = file.relative_to(upstream).as_posix()
            raw = file.read_bytes()
            sha = digest(raw)
            text_id = file.name.split("_root-")[0]
            existing = conn.execute("SELECT sha256 FROM documents WHERE text_id=?", (text_id,)).fetchone()
            if existing and existing[0] == sha:
                continue
            conn.execute("SAVEPOINT import_file")
            try:
                pali = read_json(raw)
                if any(not belongs(text_id, k.split(":")[0]) for k in pali):
                    raise ValueError(f"Segment belongs to another document: {text_id}")
                author, transfile = translations.get(text_id, (None, None))
                transraw = transfile.read_bytes() if transfile else None
                english = read_json(transraw) if transraw else {}
                aligned = {k: v for k, v in english.items() if k in pali and v.strip()}
                count = len(aligned)
                coverage = "complete" if count == len(pali) else "partial" if count else "none"
                values = (text_id, relative.split("/")[3], relative, REVISION,
                          zlib.compress(raw, 9), sha,
                          author, transfile.relative_to(upstream).as_posix() if transfile else None,
                          zlib.compress(transraw, 9) if transraw else None,
                          digest(transraw) if transraw else None, len(pali), count, coverage)
                # Keep exact raw source bytes for provenance and verification. API preserves all string values.
                conn.execute("INSERT OR REPLACE INTO documents VALUES(" + ",".join("?" * 13) + ")", values)
                conn.execute("DELETE FROM aliases WHERE text_id=?", (text_id,))
                conn.executemany("INSERT INTO aliases VALUES(?,?)",
                                 ((alias, text_id) for alias in {sid.split(":")[0] for sid in pali}))
                conn.execute("INSERT OR REPLACE INTO manifest VALUES(?,?,?,NULL)", (relative, "imported", sha))
                conn.execute("RELEASE import_file")
            except (ValueError, UnicodeError, sqlite3.IntegrityError) as exc:
                conn.execute("ROLLBACK TO import_file")
                conn.execute("RELEASE import_file")
                conn.execute("INSERT OR REPLACE INTO manifest VALUES(?,?,?,?)", (relative, "failed", sha, str(exc)))
            conn.commit()  # Each file is atomic; interruption can resume without duplicate IDs.
        result = corpus(conn)
        if result["manifest"].get("failed"):
            raise ValueError(f"Import has failed files: {result['manifest']}")
        return result


def verify_source(path=None):
    with connect(path) as conn:
        init(conn)
        checked = 0
        for row in conn.execute("SELECT * FROM documents"):
            raw = zlib.decompress(row["raw"])
            if digest(raw) != row["sha256"]:
                raise ValueError(f"Source mismatch: {row['text_id']}")
            pali = read_json(raw)
            english = {}
            if row["translation_raw"]:
                traw = zlib.decompress(row["translation_raw"])
                if digest(traw) != row["translation_sha256"]:
                    raise ValueError("Translation checksum mismatch")
                source = read_json(traw)
                english = {k: v for k, v in source.items() if k in pali and v.strip()}
            stored_aliases = {r[0] for r in conn.execute("SELECT alias FROM aliases WHERE text_id=?", (row["text_id"],))}
            if stored_aliases != {sid.split(":")[0] for sid in pali}:
                raise ValueError("Document alias lookup mismatch")
            if len(english) != row["aligned_count"]:
                raise ValueError("Alignment count mismatch")
            if not set(english).issubset(pali):
                raise ValueError("Invalid segment alignment")
            checked += 1
        expected = conn.execute("SELECT value FROM metadata WHERE key='expected_documents'").fetchone()
        failures = conn.execute("SELECT count(*) FROM manifest WHERE status='failed'").fetchone()[0]
        if not checked or (expected and checked != int(expected[0])) or failures:
            raise ValueError("Corpus does not cover its manifest")
        conn.execute("INSERT OR REPLACE INTO metadata VALUES('verified_documents',?)", (str(checked),))
        return {"checked_documents": checked, "lossless": True}
