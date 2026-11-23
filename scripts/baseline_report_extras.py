"""Số bổ sung cho docs/baseline_report.md, tính từ file đã lưu (không chạy lại retrieval).

- Temporal Violation Rate của từng file kết quả retrieval: chunk trả về không có hiệu lực tại
  as_of_date của câu hỏi (retrieval.temporal.is_effective_at), trên các câu được chấm.
- So sánh ghép cặp Hybrid + Reranker với Hybrid: bootstrap theo câu trên hiệu số điểm từng câu.
"""
import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any, Sequence

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from evaluation.metrics import BOOTSTRAP_CONFIDENCE_LEVEL, BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED, _percentile
from retrieval.temporal import effective_period, is_effective_at

CHUNKS_PATH = ROOT_DIR / "data" / "chunking_output" / "chunks.jsonl"
RESULTS_DIR = ROOT_DIR / "retrieval" / "results"
METRICS_DIR = ROOT_DIR / "evaluation" / "results"
OUTPUT_PATH = METRICS_DIR / "baseline_report_extras.json"
SPLITS = {
    "dev": {
        "queries": ROOT_DIR / "data" / "benchmark" / "queries_dev.json",
        "results": {
            "bm25": RESULTS_DIR / "dev_bm25.json",
            "dense": RESULTS_DIR / "dev_dense.json",
            "hybrid": RESULTS_DIR / "dev_hybrid.json",
            "hybrid_reranker": RESULTS_DIR / "dev_hybrid_reranker.json",
        },
    },
    "test": {
        "queries": ROOT_DIR / "data" / "benchmark" / "queries_test.json",
        "results": {
            "bm25": RESULTS_DIR / "test" / "test_bm25.json",
            "dense": RESULTS_DIR / "test" / "test_dense.json",
            "hybrid": RESULTS_DIR / "test" / "test_hybrid.json",
            "hybrid_reranker": RESULTS_DIR / "test" / "hybrid_reranker_test.json",
        },
    },
}
PAIRED_METRICS = ("strict_match_recall@10", "mrr@10", "ndcg@10")


def read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_chunks(path: Path) -> dict[str, dict[str, Any]]:
    chunks = {}
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                chunk = json.loads(line)
                chunks[chunk["chunk_id"]] = chunk
    return chunks


def temporal_check(
    results: Sequence[dict[str, Any]],
    as_of_by_query: dict[str, str],
    query_ids: set[str],
    chunks: dict[str, dict[str, Any]],
    top_k: int = 10,
) -> dict[str, Any]:
    checked = violations = missing = 0
    for record in results:
        if record["query_id"] not in query_ids:
            continue
        as_of = as_of_by_query[record["query_id"]]
        for item in record["results"][:top_k]:
            chunk = chunks.get(item["chunk_id"])
            if chunk is None:
                raise ValueError(f"chunk_id không có trong corpus: {item['chunk_id']}")
            if effective_period(chunk) == (None, None):
                missing += 1
                continue
            checked += 1
            violations += not is_effective_at(chunk, as_of)
    return {
        "temporal_violation_rate": violations / checked if checked else None,
        "violations": violations,
        "checked": checked,
        "missing_date_metadata": missing,
    }


def paired_bootstrap(
    per_question_a: Sequence[dict[str, Any]],
    per_question_b: Sequence[dict[str, Any]],
    metric: str,
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """Hiệu trung bình b − a, CI percentile bootstrap theo câu, số câu b hơn / kém a."""
    a = {row["query_id"]: row[metric] for row in per_question_a}
    b = {row["query_id"]: row[metric] for row in per_question_b}
    if a.keys() != b.keys():
        raise ValueError("Hai file metric phải chấm cùng tập câu hỏi.")
    diffs = [b[qid] - a[qid] for qid in sorted(a)]
    rng = random.Random(seed)
    count = len(diffs)
    means = sorted(sum(rng.choices(diffs, k=count)) / count for _ in range(resamples))
    alpha = (1 - BOOTSTRAP_CONFIDENCE_LEVEL) / 2
    return {
        "mean_difference": sum(diffs) / count,
        "lower": _percentile(means, alpha),
        "upper": _percentile(means, 1 - alpha),
        "better": sum(d > 0 for d in diffs),
        "worse": sum(d < 0 for d in diffs),
        "num_questions": count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()

    chunks = load_chunks(CHUNKS_PATH)
    report: dict[str, Any] = {
        "temporal": {},
        "paired_hybrid_reranker_minus_hybrid": {},
        "bootstrap": {
            "confidence_level": BOOTSTRAP_CONFIDENCE_LEVEL,
            "resamples": BOOTSTRAP_RESAMPLES,
            "seed": BOOTSTRAP_SEED,
        },
    }
    for split, spec in SPLITS.items():
        as_of = {row["id"]: row["as_of_date"] for row in read_json(spec["queries"])}
        metrics = {
            method: read_json(METRICS_DIR / f"{method}_{split}_metrics.json")
            for method in spec["results"]
        }
        scored_ids = {row["query_id"] for row in metrics["hybrid"]["per_question"]}
        report["temporal"][split] = {
            method: temporal_check(read_json(path), as_of, scored_ids, chunks)
            for method, path in spec["results"].items()
        }
        report["paired_hybrid_reranker_minus_hybrid"][split] = {
            metric: paired_bootstrap(
                metrics["hybrid"]["per_question"], metrics["hybrid_reranker"]["per_question"], metric
            )
            for metric in PAIRED_METRICS
        }

    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for split in SPLITS:
        for method, row in report["temporal"][split].items():
            print(f"{split} {method}: temporal {row['violations']}/{row['checked']}, thiếu ngày {row['missing_date_metadata']}")
        for metric, row in report["paired_hybrid_reranker_minus_hybrid"][split].items():
            print(f"{split} reranker − hybrid {metric}: {row['mean_difference']:+.4f} "
                  f"[{row['lower']:+.4f}, {row['upper']:+.4f}], {row['better']}/{row['worse']}")
    print(f"Đã ghi {args.output}")


if __name__ == "__main__":
    main()
