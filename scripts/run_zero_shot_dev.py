import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from evaluation.evaluate_zero_shot import evaluate
from evaluation.zero_shot import run_benchmark

DEFAULT_QUERIES = ROOT_DIR / "evaluation" / "datasets" / "dev_gold_30_queries_v1.json"
DEFAULT_GROUND_TRUTH = ROOT_DIR / "data" / "benchmark" / "ground_truth.json"
DEFAULT_RESULTS_DIR = ROOT_DIR / "evaluation" / "results"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Zero-shot generation and evaluation on the selected 30-question Dev set."
    )
    parser.add_argument("--queries", type=Path, default=DEFAULT_QUERIES)
    parser.add_argument("--ground-truth", type=Path, default=DEFAULT_GROUND_TRUTH)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--model", default="qwen2.5:7b")
    parser.add_argument("--rubric-input", type=Path)
    args = parser.parse_args()

    prefix = "zero_shot_dev30"
    predictions_path = args.results_dir / f"{prefix}_results.json"
    metrics_path = args.results_dir / f"{prefix}_metrics.json"
    scored_path = args.results_dir / f"{prefix}_scored.json"
    rubric_csv_path = args.results_dir / f"{prefix}_rubric_table.csv"

    run_benchmark(args.queries, predictions_path, args.model)
    evaluate(
        predictions_path=predictions_path,
        ground_truth_path=args.ground_truth,
        metrics_output_path=metrics_path,
        scored_output_path=scored_path,
        rubric_csv_path=rubric_csv_path,
        queries_paths=[args.queries],
        rubric_input_path=args.rubric_input,
    )


if __name__ == "__main__":
    main()
