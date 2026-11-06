import argparse
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from evaluation.test_run_freeze import verify_test_run

QUERIES_TEST_PATH = ROOT_DIR / "data" / "benchmark" / "queries_test.json"
GROUND_TRUTH_PATH = ROOT_DIR / "data" / "benchmark" / "ground_truth.json"
CHUNKS_PATH = ROOT_DIR / "data" / "chunking_output" / "chunks.jsonl"
RESULTS_DIR = ROOT_DIR / "retrieval" / "results" / "test"
RESULTS_PATH = RESULTS_DIR / "hybrid_reranker_test.json"
METRICS_DIR = ROOT_DIR / "evaluation" / "results"
METRICS_PATH = METRICS_DIR / "hybrid_reranker_test_metrics.json"
BASELINE_METHODS = ("bm25", "dense", "hybrid")
ALL_METHODS = (*BASELINE_METHODS, "hybrid_reranker")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Chạy BM25, Dense, Hybrid, Hybrid + Reranker trên Test rồi chấm metric."
    )
    parser.add_argument("--queries", type=Path, default=QUERIES_TEST_PATH)
    parser.add_argument("--ground-truth", type=Path, default=GROUND_TRUTH_PATH)
    parser.add_argument("--chunks", type=Path, default=CHUNKS_PATH)
    parser.add_argument("--results", type=Path, default=RESULTS_PATH)
    parser.add_argument("--metrics", type=Path, default=METRICS_PATH)
    parser.add_argument("--results-dir", type=Path, default=None)
    parser.add_argument("--metrics-dir", type=Path, default=None)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--elasticsearch-url")
    parser.add_argument("--retrieval-config", type=Path)
    parser.add_argument("--reranking-config", type=Path)
    args = parser.parse_args()

    retrieval_config = args.retrieval_config or ROOT_DIR / "retrieval" / "config.yaml"
    reranking_config = args.reranking_config or ROOT_DIR / "reranking" / "config.yaml"
    test_run_commit = verify_test_run(
        args.queries,
        args.ground_truth,
        args.chunks,
        retrieval_config,
        reranking_config,
        args.top_k,
        ALL_METHODS,
    )
    print(f"Test freeze và cấu hình đã xác minh tại commit {test_run_commit}")

    results_dir = args.results_dir or args.results.parent
    metrics_dir = args.metrics_dir or args.metrics.parent
    baseline_retrieval_command = [
        sys.executable,
        "-m",
        "retrieval.run_dev_retrieval",
        "--queries",
        str(args.queries),
        "--chunks",
        str(args.chunks),
        "--output-dir",
        str(results_dir),
        "--output-prefix",
        "test",
        "--top-k",
        str(args.top_k),
    ]
    if args.elasticsearch_url:
        baseline_retrieval_command.extend(("--elasticsearch-url", args.elasticsearch_url))
    baseline_retrieval_command.extend(("--config", str(retrieval_config)))

    subprocess.run(baseline_retrieval_command, cwd=ROOT_DIR, check=True)

    reranker_retrieval_command = [
        sys.executable,
        str(ROOT_DIR / "scripts" / "run_retrieval.py"),
        "--queries",
        str(args.queries),
        "--output",
        str(args.results),
        "--allow-test-split",
        "--retriever",
        "hybrid",
        "--reranker",
        "cross_encoder",
        "--top-k",
        str(args.top_k),
    ]
    if args.elasticsearch_url:
        reranker_retrieval_command.extend(("--elasticsearch-url", args.elasticsearch_url))
    reranker_retrieval_command.extend(("--retrieval-config", str(retrieval_config)))
    reranker_retrieval_command.extend(("--config", str(reranking_config)))

    subprocess.run(reranker_retrieval_command, cwd=ROOT_DIR, check=True)

    for method in ALL_METHODS:
        metrics_command = [
            sys.executable,
            str(ROOT_DIR / "scripts" / "run_final_test_metrics.py"),
            "--queries",
            str(args.queries),
            "--ground-truth",
            str(args.ground_truth),
            "--chunks",
            str(args.chunks),
            "--method",
            method,
            "--top-k",
            str(args.top_k),
        ]
        if method == "hybrid_reranker":
            metrics_command.extend(("--results", str(args.results), "--metrics", str(args.metrics)))
        else:
            metrics_command.extend((
                "--results", str(results_dir / f"test_{method}.json"),
                "--metrics", str(metrics_dir / f"{method}_test_metrics.json"),
            ))
        subprocess.run(metrics_command, cwd=ROOT_DIR, check=True)


if __name__ == "__main__":
    main()
