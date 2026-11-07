import argparse
import os
import subprocess
import sys
from pathlib import Path

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
RERANKER_RESULTS_NAME = "dev_hybrid_reranker.json"
METHODS = ("bm25", "dense", "hybrid", "hybrid_reranker")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Chạy BM25, Dense, Hybrid, Hybrid + Reranker trên Dev rồi chấm metric."
    )
    parser.add_argument("--queries", type=Path, default=QUERIES_DEV_PATH)
    parser.add_argument("--ground-truth", type=Path, default=GROUND_TRUTH_PATH)
    parser.add_argument("--chunks", type=Path, default=CHUNKS_PATH)
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    parser.add_argument("--metrics-dir", type=Path, default=METRICS_DIR)
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--candidate-k", type=int, default=None)
    parser.add_argument("--rrf-k", type=int, default=None)
    parser.add_argument("--model")
    parser.add_argument("--collection")
    parser.add_argument(
        "--elasticsearch-url",
        default=os.getenv("ELASTICSEARCH_URL", "http://localhost:9200"),
    )
    parser.add_argument("--elasticsearch-index")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--reranking-config", type=Path)
    args = parser.parse_args()

    retrieval_command = [
        sys.executable,
        "-m",
        "retrieval.run_dev_retrieval",
        "--queries",
        str(args.queries),
        "--chunks",
        str(args.chunks),
        "--output-dir",
        str(args.results_dir),
    ]
    for option, value in (
        ("--top-k", args.top_k),
        ("--candidate-k", args.candidate_k),
        ("--rrf-k", args.rrf_k),
        ("--model", args.model),
        ("--collection", args.collection),
        ("--elasticsearch-url", args.elasticsearch_url),
        ("--elasticsearch-index", args.elasticsearch_index),
        ("--config", args.config),
    ):
        if value is not None:
            retrieval_command.extend((option, str(value)))

    subprocess.run(retrieval_command, cwd=ROOT_DIR, check=True)

    reranker_retrieval_command = [
        sys.executable,
        str(ROOT_DIR / "scripts" / "run_retrieval.py"),
        "--queries",
        str(args.queries),
        "--chunks",
        str(args.chunks),
        "--output",
        str(args.results_dir / RERANKER_RESULTS_NAME),
        "--retriever",
        "hybrid",
        "--reranker",
        "cross_encoder",
    ]
    if args.top_k is not None:
        reranker_retrieval_command.extend(("--top-k", str(args.top_k)))
    if args.candidate_k is not None:
        reranker_retrieval_command.extend(("--retrieval-top-k", str(args.candidate_k)))
    if args.rrf_k is not None:
        reranker_retrieval_command.extend(("--rrf-k", str(args.rrf_k)))
    if args.elasticsearch_url is not None:
        reranker_retrieval_command.extend(("--elasticsearch-url", args.elasticsearch_url))
    if args.elasticsearch_index is not None:
        reranker_retrieval_command.extend(
            ("--elasticsearch-index", args.elasticsearch_index)
        )
    if args.model is not None:
        reranker_retrieval_command.extend(("--dense-model", args.model))
    if args.collection is not None:
        reranker_retrieval_command.extend(("--collection", args.collection))
    if args.config is not None:
        reranker_retrieval_command.extend(("--retrieval-config", str(args.config)))
    if args.reranking_config is not None:
        reranker_retrieval_command.extend(("--config", str(args.reranking_config)))

    subprocess.run(reranker_retrieval_command, cwd=ROOT_DIR, check=True)

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
        "--methods",
        *METHODS,
    ]
    if args.top_k is not None:
        metrics_command.extend(("--top-k", str(args.top_k)))
    subprocess.run(metrics_command, cwd=ROOT_DIR, check=True)


if __name__ == "__main__":
    main()
