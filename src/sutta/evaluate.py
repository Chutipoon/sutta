import json
from collections import defaultdict
from pathlib import Path

from .search import search


def evaluate(file, indexes):
    cases = json.loads(Path(file).read_text(encoding="utf-8"))
    rows = []
    groups = defaultdict(list)
    for name, path, method in indexes:
        for case in cases:
            response = search(case["query"], 10, case.get("category"), method, Path(path))
            # Segment-level relevance: a document-only match is insufficient.
            found = {(r["text_id"], s) for r in response["results"] for s in r["segment_ids"]}
            expected = {(case["text_id"], s) for s in case["relevant_segments"]}
            recall = len(found & expected)/len(expected)
            row = {"method": name, "query": case["query"], "recall_at_10": recall,
                   "coverage_group": case["coverage_group"], "human_verified": case["human_verified"]}
            rows.append(row)
            groups[(name, case["coverage_group"])].append(recall)
    metrics = [{"method": k[0], "coverage_group": k[1], "recall_at_10": sum(v)/len(v), "cases": len(v)}
               for k, v in groups.items()]
    verified = all(c["human_verified"] for c in cases) and len(cases) >= 30
    return {"status": "validated" if verified and all(m["recall_at_10"] >= .85 for m in metrics) else "experimental",
            "gold_set_human_verified": verified, "metrics": metrics, "rows": rows}


def collect_translations(file, output, provider="ollama"):
    import httpx

    from .translate import ProviderError, translate
    cases = json.loads(Path(file).read_text(encoding="utf-8"))
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for index, case in enumerate(cases, 1):
        try:
            response = translate(case["text_id"], case["segment_ids"], provider)
            rows.append({"text_id": case["text_id"], "segment_ids": case["segment_ids"],
                         "response": response, "human_review": "pending"})
        except (ValueError, httpx.HTTPError, ProviderError) as exc:
            rows.append({"text_id": case["text_id"], "segment_ids": case["segment_ids"],
                         "error_type": type(exc).__name__, "human_review": "pending"})
        report = {"status": "experimental", "semantic_review": "pending", "provider": provider,
                  "attempted": len(rows), "total_cases": len(cases), "rows": rows}
        Path(output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Translation cases {index}/{len(cases)}", flush=True)
    return {"status": "experimental", "attempted": len(rows),
            "responses": sum("response" in row for row in rows), "semantic_review": "pending"}
