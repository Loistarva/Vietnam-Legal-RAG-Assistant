#!/usr/bin/env python3
"""D5.2: sweep the Confidence Threshold Filter on Dev data only.

Positives are the reviewed (``source_checked``) Dev questions left after removing the
30 official IDs of ``evaluation/manifests/dev_gold_30_manifest.json``; their reranked
Top-5 come from the committed G3 artifact. Negatives are Dev 1's negative set, reranked
with the same Hybrid + Cross-Encoder settings. Test is never read.

For each (min_top1_score, min_evidence_score) the script reports:

* false rejection: answerable questions abstained, split into those with a gold chunk in
  the Top-5 (a real loss) and those without (retrieval already missed);
* false acceptance: negatives that would reach the LLM, per negative label;
* gold dropped: gold chunks inside the Top-5 removed by the evidence floor.

Usage::

    python scripts/calibrate_confidence_threshold.py \
        --negatives-artifact reports/retrieval/confidence_calibration/neg_v2_hybrid_reranker.json \
        --output reports/retrieval/confidence_calibration/sweep.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reranking.confidence import ConfidenceConfig, apply_confidence_threshold  # noqa: E402

TOP1_GRID = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
EVIDENCE_GRID = (0.0, 0.05, 0.1, 0.2, 0.3)
RERANK_TOP_K = 5


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def canonical_sha256(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def repo_path(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def build_cases(args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    official = set(load_json(args.id_manifest)["question_ids"])
    gold = {row["id"]: row for row in load_json(args.ground_truth)}
    dev_ids = {row["id"] for row in load_json(args.benchmark)}
    envelopes = {env["query_id"]: env for env in load_json(args.dev_artifact)}
    remaining = sorted(qid for qid in dev_ids
                       if gold.get(qid, {}).get("review_status") == "source_checked" and qid not in official)
    if not remaining:
        raise SystemExit("Không còn câu Dev nào ngoài 30 ID official")
    missing = [qid for qid in remaining if qid not in envelopes]
    if missing:
        raise SystemExit(f"Artifact Dev thiếu {missing}")
    positives = []
    for qid in remaining:
        top = envelopes[qid]["results"][:RERANK_TOP_K]
        gold_ids = set(gold[qid]["gold_context_ids"])
        positives.append({"id": qid, "rows": top, "gold_ids": gold_ids,
                          "gold_in_top5": any(row["chunk_id"] in gold_ids for row in top)})
    negative_rows = {row["id"]: row for row in load_jsonl(args.negative_set)}
    negative_envelopes = {env["query_id"]: env for env in load_json(args.negatives_artifact)}
    if set(negative_rows) != set(negative_envelopes):
        raise SystemExit("Artifact câu âm không khớp đúng tập câu âm")
    for qid, env in negative_envelopes.items():
        if env.get("query") != negative_rows[qid]["question"]:
            raise SystemExit(f"{qid}: câu hỏi trong artifact khác tập câu âm")
        if (env.get("config") or {}).get("as_of_date") != negative_rows[qid]["as_of_date"]:
            raise SystemExit(f"{qid}: as_of_date trong artifact khác tập câu âm")
    negatives = [{"id": qid, "label": negative_rows[qid]["label"],
                  "rows": negative_envelopes[qid]["results"][:RERANK_TOP_K]} for qid in sorted(negative_rows)]
    inputs = {
        "dev_remaining_ids": remaining,
        "dev_remaining_ids_sha256": canonical_sha256(remaining),
        "official_ids_excluded": len(official),
        "dev_artifact": repo_path(args.dev_artifact),
        "dev_artifact_sha256": file_sha256(args.dev_artifact),
        "negative_set": repo_path(args.negative_set),
        "negative_set_sha256": file_sha256(args.negative_set),
        "negatives_artifact": repo_path(args.negatives_artifact),
        "negatives_artifact_sha256": file_sha256(args.negatives_artifact),
        "corpus_sha256": ((load_json(args.dev_artifact)[0].get("config") or {}).get("retriever") or {})
        .get("corpus_sha256"),
    }
    return positives, negatives, inputs


def evaluate(positives, negatives, top1: float, floor: float) -> dict[str, Any]:
    config = ConfidenceConfig(enabled=True, min_top1_score=top1 if top1 > 0 else None,
                              min_evidence_score=floor if floor > 0 else None,
                              threshold_config_version="sweep") if (top1 or floor) else ConfidenceConfig()
    rejected_hit, rejected_miss, gold_dropped, kept_items = [], [], 0, 0
    for case in positives:
        decision = apply_confidence_threshold(case["rows"], config)
        if decision.status != "ok":
            (rejected_hit if case["gold_in_top5"] else rejected_miss).append(case["id"])
            continue
        kept_items += len(decision.kept)
        gold_dropped += sum(1 for row in decision.dropped if row["chunk_id"] in case["gold_ids"])
    accepted: dict[str, list[str]] = {}
    for case in negatives:
        decision = apply_confidence_threshold(case["rows"], config)
        accepted.setdefault(case["label"], [])
        if decision.status == "ok":
            accepted[case["label"]].append(case["id"])
    return {
        "min_top1_score": top1, "min_evidence_score": floor,
        "false_rejection_gold_in_top5": rejected_hit,
        "rejected_without_gold_in_top5": rejected_miss,
        "gold_chunks_dropped": gold_dropped,
        "mean_evidence_items": round(kept_items / max(1, len(positives) - len(rejected_hit) - len(rejected_miss)), 2),
        "negatives_accepted": accepted,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dev-artifact", type=Path, default=ROOT / "retrieval/results/dev_hybrid_reranker.json")
    parser.add_argument("--negatives-artifact", type=Path, required=True)
    parser.add_argument("--negative-set", type=Path,
                        default=ROOT / "evaluation/negative_set/dev_negative_queries_v2.jsonl")
    parser.add_argument("--id-manifest", type=Path, default=ROOT / "evaluation/manifests/dev_gold_30_manifest.json")
    parser.add_argument("--ground-truth", type=Path, default=ROOT / "data/benchmark/ground_truth.json")
    parser.add_argument("--benchmark", type=Path, default=ROOT / "data/benchmark/queries_dev.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    for name in ("dev_artifact", "negatives_artifact", "negative_set", "id_manifest", "ground_truth", "benchmark"):
        setattr(args, name, getattr(args, name).resolve())

    positives, negatives, inputs = build_cases(args)
    sweep = [evaluate(positives, negatives, top1, floor) for top1 in TOP1_GRID for floor in EVIDENCE_GRID]
    scores = {
        "positives": [{"id": c["id"], "gold_in_top5": c["gold_in_top5"],
                       "top5_scores": [round(r["reranker_score"], 4) for r in c["rows"]],
                       "gold_scores": [round(r["reranker_score"], 4) for r in c["rows"] if r["chunk_id"] in c["gold_ids"]]}
                      for c in positives],
        "negatives": [{"id": c["id"], "label": c["label"],
                       "top5_scores": [round(r["reranker_score"], 4) for r in c["rows"]]} for c in negatives],
    }
    output = {"inputs": inputs, "rerank_top_k": RERANK_TOP_K, "scores": scores, "sweep": sweep}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(positives)} positives, {len(negatives)} negatives -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
