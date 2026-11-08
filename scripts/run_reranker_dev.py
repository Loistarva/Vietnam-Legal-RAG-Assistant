import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

QUERIES_DEV_PATH = ROOT_DIR / "data" / "benchmark" / "queries_dev.json"
GROUND_TRUTH_PATH = ROOT_DIR / "data" / "benchmark" / "ground_truth.json"
CHUNKS_PATH = ROOT_DIR / "data" / "chunking_output" / "chunks.jsonl"
RESULTS_DIR = ROOT_DIR / "retrieval" / "results"
METRICS_DIR = ROOT_DIR / "evaluation" / "results"
RESULTS_NAME = "dev_hybrid_reranker.json"


def require_dev_queries(path: Path) -> None:
    try:
        queries: Any = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Không đọc được file câu hỏi Dev {path}: {exc}") from exc
    if not isinstance(queries, list) or not queries:
        raise ValueError("File câu hỏi Dev phải là JSON array không rỗng.")
    for position, query in enumerate(queries, start=1):
        if not isinstance(query, dict) or query.get("split") != "dev":
            raise ValueError(
                f"Câu hỏi thứ {position} không thuộc split Dev; "
                "script này chỉ chạy reranker trên Dev."
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Chạy Hybrid + Cross-Encoder Reranker và chấm riêng trên Dev."
    )
    parser.add_argument("--queries", type=Path, default=QUERIES_DEV_PATH)
    parser.add_argument("--ground-truth", type=Path, default=GROUND_TRUTH_PATH)
    parser.add_argument("--chunks", type=Path, default=CHUNKS_PATH)
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    parser.add_argument("--metrics-dir", type=Path, default=METRICS_DIR)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument(
        "--elasticsearch-url",
        default=os.getenv("ELASTICSEARCH_URL", "http://localhost:9200"),
    )
    parser.add_argument(
        "--retrieval-config",
        type=Path,
        default=ROOT_DIR / "retrieval" / "config.yaml",
    )
    parser.add_argument(
        "--reranking-config",
        type=Path,
        default=ROOT_DIR / "reranking" / "config.yaml",
    )
    args = parser.parse_args()

    try:
        require_dev_queries(args.queries)
    except ValueError as exc:
        parser.error(str(exc))

    retrieval_command = [
        sys.executable,
        str(ROOT_DIR / "scripts" / "run_retrieval.py"),
        "--queries",
        str(args.queries),
        "--chunks",
        str(args.chunks),
        "--output",
        str(args.results_dir / RESULTS_NAME),
        "--retriever",
        "hybrid",
        "--reranker",
        "cross_encoder",
        "--top-k",
        str(args.top_k),
        "--elasticsearch-url",
        args.elasticsearch_url,
        "--retrieval-config",
        str(args.retrieval_config),
        "--config",
        str(args.reranking_config),
    ]
    subprocess.run(retrieval_command, cwd=ROOT_DIR, check=True)

    metrics_command = [
        sys.executable,
        str(ROOT_DIR / "scripts" / "run_baselines_metrics.py"),
        "--queries",
        str(args.queries),
        "--ground-truth",
        str(args.ground_truth),
        "--chunks",
        str(args.chunks),
        "--results-dir",
        str(args.results_dir),
        "--metrics-dir",
        str(args.metrics_dir),
        "--top-k",
        str(args.top_k),
        "--methods",
        "hybrid_reranker",
    ]
    subprocess.run(metrics_command, cwd=ROOT_DIR, check=True)


if __name__ == "__main__":
    main()
