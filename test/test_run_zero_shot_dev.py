import tempfile
import unittest
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
                 patch("scripts.run_zero_shot_dev.evaluate") as evaluate:
                main()

        self.assertEqual(DEFAULT_QUERIES.name, "dev_gold_30_queries_v1.json")
        self.assertEqual(run_benchmark.call_args.args[0], DEFAULT_QUERIES)
        self.assertEqual(run_benchmark.call_args.args[1], results_dir / "zero_shot_dev30_results.json")
        self.assertEqual(evaluate.call_args.kwargs["ground_truth_path"], DEFAULT_GROUND_TRUTH)
        self.assertEqual(evaluate.call_args.kwargs["queries_paths"], [DEFAULT_QUERIES])
        self.assertEqual(
            evaluate.call_args.kwargs["metrics_output_path"],
            results_dir / "zero_shot_dev30_metrics.json",
        )


if __name__ == "__main__":
    unittest.main()
