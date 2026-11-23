"""Create an immutable Dev4 handoff JSONL with deterministic Router decisions."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.router.rule_router import CLASSIFIER_VERSION, RuleRouter
from schemas.models import RAGOutputRecord


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def enrich_results(source_path: Path, output_path: Path, *, router: RuleRouter | None = None) -> dict[str, Any]:
    """Add canonical route to a separate results file; never overwrite the source."""
    source_path = source_path.resolve()
    output_path = output_path.resolve()
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    if source_path == output_path:
        raise ValueError("Không được ghi đè JSONL kết quả gốc")
    if output_path.exists():
        raise FileExistsError(f"Từ chối ghi đè artifact bàn giao: {output_path}")

    raw_lines = source_path.read_text(encoding="utf-8-sig").splitlines()
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    route_counts: Counter[str] = Counter()
    active_router = router or RuleRouter()
    for line_number, raw in enumerate(raw_lines, 1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSONL sai định dạng ở dòng {line_number}: {exc}") from exc
        if not isinstance(row, dict) or not isinstance(row.get("result"), dict):
            raise ValueError(f"Dòng {line_number} phải có object result")
        result = dict(row["result"])
        query_id = row.get("query_id") or result.get("query_id")
        query = result.get("query")
        as_of_date = row.get("as_of_date") or result.get("as_of_date")
        if not isinstance(query_id, str) or not query_id.strip():
            raise ValueError(f"Dòng {line_number} thiếu query_id")
        if query_id in seen:
            raise ValueError(f"query_id trùng trong source JSONL: {query_id}")
        if result.get("query_id") != query_id:
            raise ValueError(f"query_id ở wrapper và result không khớp: {query_id}")
        if not isinstance(query, str) or not query.strip():
            raise ValueError(f"{query_id}: thiếu query để định tuyến")
        if not isinstance(as_of_date, str) or result.get("as_of_date") != as_of_date:
            raise ValueError(f"{query_id}: thiếu hoặc lệch as_of_date")

        decision = active_router.route(query, query_id=query_id, as_of_date=as_of_date)
        canonical = decision.to_canonical()
        if result.get("route") is not None and result["route"] != canonical.route:
            raise ValueError(f"{query_id}: route đã có không khớp Router hiện tại")
        result["route"] = canonical.route
        RAGOutputRecord.model_validate(result)
        row["result"] = result
        rows.append(row)
        seen.add(query_id)
        route_counts[canonical.route] += 1

    if not rows:
        raise ValueError("Source JSONL không có bản ghi kết quả")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation makes an existing handoff immutable by default.
    with output_path.open("x", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    return {
        "record_count": len(rows),
        "unique_query_id_count": len(seen),
        "route_counts": dict(sorted(route_counts.items())),
        "output_sha256": sha256_file(output_path),
        "router_version": CLASSIFIER_VERSION,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-results", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    source_results = args.source_results if args.source_results.is_absolute() else ROOT / args.source_results
    source_manifest = args.source_manifest if args.source_manifest.is_absolute() else ROOT / args.source_manifest
    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    output_results = output_dir / "results.jsonl"
    output_manifest = output_dir / "run_manifest.json"
    if output_manifest.exists() or output_dir.exists():
        raise FileExistsError(f"Từ chối ghi đè thư mục handoff: {output_dir}")
    manifest_source = json.loads(source_manifest.read_text(encoding="utf-8-sig"))
    summary = enrich_results(source_results, output_results)
    manifest = {
        "manifest_version": "d4.4.route_enriched_handoff.v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "derivation": "deterministic_route_enrichment_no_llm_or_retrieval",
        "source_run_manifest": source_manifest.relative_to(ROOT).as_posix(),
        "source_run_manifest_sha256": sha256_file(source_manifest),
        "source_results": source_results.relative_to(ROOT).as_posix(),
        "source_results_sha256": sha256_file(source_results),
        "source_run_git_sha": manifest_source.get("git_sha"),
        "source_run_signature_sha256": manifest_source.get("run_signature_sha256"),
        "source_precomputed_artifact": manifest_source.get("precomputed_artifact"),
        "schema_version": "week10_v1.1",
        "route_field": "result.route (canonical RouteType)",
        "router_version": CLASSIFIER_VERSION,
        "router_source_sha256": sha256_file(ROOT / "agent/router/rule_router.py"),
        "enrichment_script_sha256": sha256_file(Path(__file__).resolve()),
        "output_results": output_results.relative_to(ROOT).as_posix(),
        **summary,
        "ollama_called": False,
        "retrieval_rerun": False,
        "source_output_overwritten": False,
    }
    with output_manifest.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
