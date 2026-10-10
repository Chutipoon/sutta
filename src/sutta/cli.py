import argparse
import json
import subprocess
import sys
from pathlib import Path

from .config import REVISION, SOURCE, data_dir, model_dir
from .store import connect, corpus, init


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def fetch():
    upstream = data_dir()/"upstream"
    if upstream.exists():
        head = subprocess.check_output(["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True).strip()
        if head != REVISION:
            raise ValueError("Existing upstream revision mismatch; choose another SUTTA_DATA directory")
        return {"directory": str(upstream), "revision": head}
    upstream.mkdir(parents=True)
    for args in (["init"], ["remote", "add", "origin", SOURCE+".git"],
                 ["sparse-checkout", "init", "--cone"],
                 ["sparse-checkout", "set", "root/pli/ms", "translation/en"],
                 ["fetch", "--depth", "1", "origin", REVISION], ["checkout", "--detach", "FETCH_HEAD"]):
        subprocess.run(["git", "-C", str(upstream), *args], check=True)
    return {"directory": str(upstream), "revision": REVISION}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Local Pali corpus workflow")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("doctor", "fetch", "verify", "storage-report", "corpus"):
        commands.add_parser(name)
    p = commands.add_parser("download-model")
    p.add_argument("--embedding", choices=["e5", "bge"], default="e5")
    p = commands.add_parser("ingest")
    p.add_argument("--source", type=Path, default=data_dir()/"upstream")
    p = commands.add_parser("index")
    p.add_argument("--limit", type=int)
    p.add_argument("--mode", choices=["pali", "companion"], default="companion")
    p.add_argument("--output", type=Path)
    p.add_argument("--category", action="append")
    p.add_argument("--texts-file", type=Path)
    p.add_argument("--embedding", choices=["e5", "bge"], default="e5")
    p = commands.add_parser("search")
    p.add_argument("query")
    p.add_argument("--method", choices=["hybrid", "vector", "lexical"], default="hybrid")
    p = commands.add_parser("evaluate")
    p.add_argument("--cases", default="evaluation/search-cases.json")
    p.add_argument("--pali", default="data/pali-pilot.sqlite")
    p.add_argument("--companion", default="data/index.sqlite")
    p.add_argument("--output", default="docs/search-results.json")
    p.add_argument("--bge")
    p = commands.add_parser("evaluate-translation")
    p.add_argument("--cases", default="evaluation/translation-cases.json")
    p.add_argument("--output", default="docs/translation-results.json")
    p.add_argument("--provider", choices=["ollama", "gemini", "azure"], default="ollama")
    p = commands.add_parser("serve")
    p.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    try:
        match args.command:
            case "fetch":
                emit(fetch())
            case "download-model":
                from .embedding import download
                emit(download(args.embedding))
            case "ingest":
                from .ingest import ingest
                emit(ingest(args.source))
            case "index":
                from .index import build
                emit(build(args.limit, args.mode, args.output, args.category,
                           json.loads(args.texts_file.read_text(encoding="utf-8")) if args.texts_file else None,
                           args.embedding))
            case "search":
                from .search import search
                emit(search(args.query, method=args.method))
            case "corpus":
                with connect() as conn:
                    init(conn)
                    emit(corpus(conn))
            case "verify":
                subprocess.run([sys.executable, "-m", "ruff", "check", "src", "tests"], check=True)
                subprocess.run([sys.executable, "-m", "pytest", "-q"], check=True)
                if (data_dir()/"corpus.sqlite").exists():
                    from .ingest import verify_source
                    emit(verify_source())
            case "storage-report":
                import os

                from .embedding import directory_for
                def size(path):
                    total = 0
                    if path.exists():
                        for file in path.rglob("*"):
                            try:
                                if file.is_file():
                                    total += file.stat().st_size
                            except FileNotFoundError:
                                pass
                    return total
                uv_cache = Path(subprocess.check_output(["uv", "cache", "dir"], text=True).strip())
                hf_cache = Path(os.environ.get("HF_HOME", str(Path.home()/".cache/huggingface")))
                emit({"database_bytes": sum(p.stat().st_size for p in data_dir().glob("*.sqlite")),
                      "database_breakdown": {p.name: p.stat().st_size for p in data_dir().glob("*.sqlite")},
                      "models_bytes": size(model_dir()) + size(directory_for("bge")),
                      "model_breakdown": {"e5": size(model_dir()), "bge": size(directory_for("bge"))},
                      "dependencies_bytes": size(Path(".venv")),
                      "upstream_checkout_bytes": size(data_dir()/"upstream"),
                      "temporary_validation_bytes": size(data_dir()/"fresh-install"),
                      "shared_cache_bytes": {"uv": size(uv_cache), "huggingface": size(hf_cache)},
                      "shared_cache_note": "Shared with other projects; these totals cannot be attributed exclusively to sutta",
                      "measurement": "Logical file bytes. Hardlinks may share physical storage; do not add shared-cache totals as new project disk usage."})
            case "doctor":
                import sqlite3

                from .index import vec_connect
                conn = vec_connect(":memory:")
                emit({"python": sys.version, "sqlite": sqlite3.sqlite_version,
                      "sqlite_vec": conn.execute("SELECT vec_version()").fetchone()[0],
                      "fts5": bool(conn.execute("SELECT sqlite_compileoption_used('ENABLE_FTS5')").fetchone()[0]),
                      "model_installed": (model_dir()/"onnx/model.onnx").exists()})
                conn.close()
            case "evaluate":
                from .evaluate import evaluate
                indexes = [("pali", args.pali, "vector"), ("companion", args.companion, "vector"),
                           ("hybrid", args.companion, "hybrid")]
                if args.bge:
                    indexes += [("bge_companion", args.bge, "vector"), ("bge_hybrid", args.bge, "hybrid")]
                report = evaluate(args.cases, indexes)
                Path(args.output).parent.mkdir(parents=True, exist_ok=True)
                Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
                emit({k: v for k, v in report.items() if k != "rows"})
            case "evaluate-translation":
                from .evaluate import collect_translations
                emit(collect_translations(args.cases, args.output, args.provider))
            case "serve":
                import uvicorn
                uvicorn.run("sutta.api:app", host="127.0.0.1", port=args.port)
    except (ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from None
