import tempfile
import unittest
import re
from pathlib import Path
from unittest.mock import patch

from scripts.run_zero_shot_dev import (
    DEFAULT_GROUND_TRUTH,
    DEFAULT_QUERIES,
    main,
)


class RunZeroShotDevTest(unittest.TestCase):
    def test_defaults_to_the_30_question_dataset_and_separate_outputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            results_dir = Path(temp_dir)
            with patch("sys.argv", ["run_zero_shot_dev.py", "--results-dir", str(results_dir)]), \
                 patch("scripts.run_zero_shot_dev.run_benchmark") as run_benchmark, \
                 patch("scripts.run_zero_shot_dev.parse_zero_shot_file") as parse_citations, \
                 patch("scripts.run_zero_shot_dev.evaluate") as evaluate:
                main()

        self.assertEqual(DEFAULT_QUERIES.name, "dev_gold_30_queries_v1.json")
        self.assertEqual(run_benchmark.call_args.args[0], DEFAULT_QUERIES)
        predictions_path = run_benchmark.call_args.args[1]
        self.assertEqual(predictions_path.parent, results_dir / "dev")
        self.assertRegex(
            predictions_path.name,
            r"^\d{8}_zero_shot_qwen25_dev30\.jsonl$",
        )
        parsed_path = predictions_path.with_name(
            f"{predictions_path.stem}_parsed.json"
        )
        self.assertEqual(
            parse_citations.call_args.args,
            (predictions_path, parsed_path),
        )
        self.assertEqual(evaluate.call_args.kwargs["ground_truth_path"], DEFAULT_GROUND_TRUTH)
        self.assertEqual(evaluate.call_args.kwargs["predictions_path"], parsed_path)
        self.assertEqual(evaluate.call_args.kwargs["queries_paths"], [DEFAULT_QUERIES])
        self.assertEqual(
            evaluate.call_args.kwargs["metrics_output_path"],
            results_dir / "metrics_A_B_results" / f"{predictions_path.stem}_metrics.json",
        )


if __name__ == "__main__":
    unittest.main()
