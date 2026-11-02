import argparse
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
QUERIES_TEST_PATH = ROOT_DIR / "data" / "benchmark" / "queries_test.json"
GROUND_TRUTH_PATH = ROOT_DIR / "data" / "benchmark" / "ground_truth.json"
CHUNKS_PATH = ROOT_DIR / "data" / "chunking_output" / "chunks.jsonl"
RESULTS_PATH = ROOT_DIR / "retrieval" / "results" / "test" / "hybrid_test.json"
METRICS_PATH = ROOT_DIR / "evaluation" / "results" / "hybrid_test_metrics.json"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Chạy Hybrid Retrieval trên Test rồi chấm metric."
    )
    parser.add_argument("--queries", type=Path, default=QUERIES_TEST_PATH)
    parser.add_argument("--ground-truth", type=Path, default=GROUND_TRUTH_PATH)
    parser.add_argument("--chunks", type=Path, default=CHUNKS_PATH)
    parser.add_argument("--results", type=Path, default=RESULTS_PATH)
    parser.add_argument("--metrics", type=Path, default=METRICS_PATH)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--elasticsearch-url")
    parser.add_argument("--retrieval-config", type=Path)
    parser.add_argument("--reranking-config", type=Path)
    args = parser.parse_args()

    retrieval_command = [
        sys.executable,
        str(ROOT_DIR / "scripts" / "run_retrieval.py"),
        "--queries",
        str(args.queries),
        "--output",
        str(args.results),
        "--allow-test-split",
        "--top-k",
        str(args.top_k),
    ]
    if args.elasticsearch_url:
        retrieval_command.extend(("--elasticsearch-url", args.elasticsearch_url))
    if args.retrieval_config is not None:
        retrieval_command.extend(("--retrieval-config", str(args.retrieval_config)))
    if args.reranking_config is not None:
        retrieval_command.extend(("--config", str(args.reranking_config)))

    subprocess.run(retrieval_command, cwd=ROOT_DIR, check=True)

    metrics_command = [
        sys.executable,
        str(ROOT_DIR / "scripts" / "run_final_test_metrics.py"),
        "--queries",
        str(args.queries),
        "--ground-truth",
        str(args.ground_truth),
        "--chunks",
        str(args.chunks),
        "--results",
        str(args.results),
        "--metrics",
        str(args.metrics),
        "--top-k",
        str(args.top_k),
    ]
    subprocess.run(metrics_command, cwd=ROOT_DIR, check=True)


if __name__ == "__main__":
    main()
