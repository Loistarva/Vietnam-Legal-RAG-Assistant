import tempfile
import unittest
from datetime import date
from pathlib import Path

from evaluation.run_metrics import default_run_a_input


class DefaultRunAInputTest(unittest.TestCase):
    def test_prefers_todays_run_when_present(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            results_dir = Path(temp_dir)
            today_run = results_dir / "20261115_zero_shot_qwen25_dev30.jsonl"
            older_run = results_dir / "20261114_zero_shot_qwen25_dev30.jsonl"
            today_run.touch()
            older_run.touch()

            self.assertEqual(
                default_run_a_input(results_dir, date(2026, 11, 15)),
                today_run,
            )

    def test_falls_back_to_latest_existing_run_not_after_today(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            results_dir = Path(temp_dir)
            older_run = results_dir / "20261114_zero_shot_qwen25_dev30.jsonl"
            future_run = results_dir / "20261116_zero_shot_qwen25_dev30.jsonl"
            malformed_run = results_dir / "latest_zero_shot_qwen25_dev30.jsonl"
            older_run.touch()
            future_run.touch()
            malformed_run.touch()

            self.assertEqual(
                default_run_a_input(results_dir, date(2026, 11, 15)),
                older_run,
            )

    def test_returns_todays_expected_path_when_no_run_exists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            results_dir = Path(temp_dir)

            self.assertEqual(
                default_run_a_input(results_dir, date(2026, 11, 15)),
                results_dir / "20261115_zero_shot_qwen25_dev30.jsonl",
            )


if __name__ == "__main__":
    unittest.main()
