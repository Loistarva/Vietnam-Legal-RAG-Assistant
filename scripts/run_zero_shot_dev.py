import argparse
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from evaluation.evaluate_zero_shot import evaluate
from evaluation.citation_parser import parse_zero_shot_file
from evaluation.zero_shot import run_benchmark
from model_gateway.llm_gateway import DEFAULT_CONFIG_PATH

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
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH,
                        help="Shared gateway config used by Run B.")
    parser.add_argument("--rubric-input", type=Path)
    args = parser.parse_args()

    run_name = f"{datetime.now():%Y%m%d}_zero_shot_qwen25_dev30"
    dev_results_dir = args.results_dir / "dev"
    predictions_path = dev_results_dir / f"{run_name}.jsonl"
    parsed_path = dev_results_dir / f"{run_name}_parsed.json"
    metrics_path = args.results_dir / "metrics_A_B_results" / f"{run_name}_metrics.json"
    dev_results_dir.mkdir(parents=True, exist_ok=True)
    run_benchmark(args.queries, predictions_path, config_path=args.config, split="dev")
    parse_zero_shot_file(predictions_path, parsed_path)
    print(f"Generated answers: {predictions_path.resolve()}")
    print(f"Parsed citations:  {parsed_path.resolve()}")
    with tempfile.TemporaryDirectory(prefix="zero-shot-evaluation-", dir=dev_results_dir) as temp_dir:
        evaluate(
            predictions_path=parsed_path,
            ground_truth_path=args.ground_truth,
            metrics_output_path=metrics_path,
            scored_output_path=Path(temp_dir) / "scored.json",
            queries_paths=[args.queries],
            rubric_input_path=args.rubric_input,
        )


if __name__ == "__main__":
    main()
