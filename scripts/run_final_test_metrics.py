import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from evaluation.run_evaluation import load_parent_ids, read_json_array, run_evaluation

QUERIES_TEST_PATH = ROOT_DIR / "data" / "benchmark" / "queries_test.json"
GROUND_TRUTH_PATH = ROOT_DIR / "data" / "benchmark" / "ground_truth.json"
CHUNKS_PATH = ROOT_DIR / "data" / "chunking_output" / "chunks.jsonl"
RESULTS_DIR = ROOT_DIR / "retrieval" / "results" / "test"
METRICS_PATH = ROOT_DIR / "evaluation" / "results" / "hybrid_test_metrics.json"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Chấm kết quả retrieval đã lưu trên Test Set."
    )
    parser.add_argument("--queries", type=Path, default=QUERIES_TEST_PATH)
    parser.add_argument("--ground-truth", type=Path, default=GROUND_TRUTH_PATH)
    parser.add_argument("--chunks", type=Path, default=CHUNKS_PATH)
    parser.add_argument("--results", type=Path, default=RESULTS_DIR / "hybrid_test.json")
    parser.add_argument("--metrics", type=Path, default=METRICS_PATH)
    parser.add_argument("--method", choices=("bm25", "dense", "hybrid"), default="hybrid")
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()

    print(f"Chấm kết quả {args.method} đã lưu trên Test Set: {args.results}")
    queries = read_json_array(args.queries)
    parent_by_chunk = load_parent_ids(args.chunks)
    run_evaluation(
        args.results,
        queries,
        args.ground_truth,
        args.metrics,
        expected_split="test",
        top_k=args.top_k,
        parent_by_chunk=parent_by_chunk,
    )


if __name__ == "__main__":
    main()
