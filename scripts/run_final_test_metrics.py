import argparse
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from evaluation.provenance import build_report_metadata, metric_cutoffs
from evaluation.run_evaluation import load_parent_ids, read_json_array, run_evaluation
from evaluation.test_run_freeze import validate_test_gold, verify_test_run

QUERIES_TEST_PATH = ROOT_DIR / "data" / "benchmark" / "queries_test.json"
GROUND_TRUTH_PATH = ROOT_DIR / "data" / "benchmark" / "ground_truth.json"
CHUNKS_PATH = ROOT_DIR / "data" / "chunking_output" / "chunks.jsonl"
RESULTS_DIR = ROOT_DIR / "retrieval" / "results" / "test"
METRICS_PATH = ROOT_DIR / "evaluation" / "results" / "hybrid_reranker_test_metrics.json"
METHODS = ("bm25", "dense", "hybrid", "hybrid_reranker")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Chấm kết quả retrieval đã lưu trên Test Set."
    )
    parser.add_argument("--queries", type=Path, default=QUERIES_TEST_PATH)
    parser.add_argument("--ground-truth", type=Path, default=GROUND_TRUTH_PATH)
    parser.add_argument("--chunks", type=Path, default=CHUNKS_PATH)
    parser.add_argument("--results", type=Path)
    parser.add_argument("--metrics", type=Path)
    parser.add_argument("--method", choices=METHODS, default="hybrid_reranker")
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()

    default_results = (
        RESULTS_DIR / "hybrid_reranker_test.json"
        if args.method == "hybrid_reranker"
        else RESULTS_DIR / f"test_{args.method}.json"
    )
    results_path = args.results or default_results
    metrics_path = args.metrics or (
        METRICS_PATH if args.method == "hybrid_reranker"
        else METRICS_PATH.with_name(f"{args.method}_test_metrics.json")
    )
    print(f"Chấm kết quả {args.method} đã lưu trên Test Set: {results_path}")
    queries = read_json_array(args.queries)
    ground_truth = read_json_array(args.ground_truth)
    validate_test_gold(queries, ground_truth)
    test_run_commit = verify_test_run(
        args.queries,
        args.ground_truth,
        args.chunks,
        ROOT_DIR / "retrieval" / "config.yaml",
        ROOT_DIR / "reranking" / "config.yaml",
        args.top_k,
        METHODS,
    )
    parent_by_chunk = load_parent_ids(args.chunks)
    report_metadata = build_report_metadata(
        results_path,
        args.queries,
        args.ground_truth,
        args.chunks,
        queries,
        args.method,
        "test",
        args.top_k,
    )
    report_metadata["test_run_commit"] = test_run_commit
    run_evaluation(
        results_path,
        queries,
        args.ground_truth,
        metrics_path,
        expected_split="test",
        top_k=args.top_k,
        method=args.method,
        parent_by_chunk=parent_by_chunk,
        ks=metric_cutoffs(args.top_k),
        report_metadata=report_metadata,
    )


if __name__ == "__main__":
    main()
