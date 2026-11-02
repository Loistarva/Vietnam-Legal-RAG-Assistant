import argparse
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from evaluation.run_evaluation import load_parent_ids, read_json_array, run_evaluation

QUERIES_DEV_PATH = ROOT_DIR / "data" / "benchmark" / "queries_dev.json"
GROUND_TRUTH_PATH = ROOT_DIR / "data" / "benchmark" / "ground_truth.json"
CHUNKS_PATH = ROOT_DIR / "data" / "chunking_output" / "chunks.jsonl"
RESULTS_DIR = ROOT_DIR / "retrieval" / "results"
METRICS_DIR = ROOT_DIR / "evaluation" / "results"
METHODS = ("bm25", "dense", "hybrid")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Chấm metric từ kết quả retrieval đã lưu trên Dev Set."
    )
    parser.add_argument("--queries", type=Path, default=QUERIES_DEV_PATH)
    parser.add_argument("--ground-truth", type=Path, default=GROUND_TRUTH_PATH)
    parser.add_argument("--chunks", type=Path, default=CHUNKS_PATH)
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    parser.add_argument("--metrics-dir", type=Path, default=METRICS_DIR)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--methods", nargs="+", choices=METHODS, default=list(METHODS))
    args = parser.parse_args()
    queries = read_json_array(args.queries)
    parent_by_chunk = load_parent_ids(args.chunks)

    for method in args.methods:
        results_path = args.results_dir / f"dev_{method}.json"
        metrics_path = args.metrics_dir / f"{method}_dev_metrics.json"
        print(f"Đang chấm {method} từ {results_path}")
        run_evaluation(
            results_path,
            queries,
            args.ground_truth,
            metrics_path,
            expected_split="dev",
            top_k=args.top_k,
            parent_by_chunk=parent_by_chunk,
        )


if __name__ == "__main__":
    main()
