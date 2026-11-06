import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.run_final_test import (
    ALL_METHODS,
    CHUNKS_PATH,
    GROUND_TRUTH_PATH,
    QUERIES_TEST_PATH,
    main,
)


class RunFinalTestOrchestrationTest(unittest.TestCase):
    def test_baseline_and_final_test_help_work_when_run_as_scripts(self):
        root = Path(__file__).resolve().parents[1]
        scripts = ("run_baselines.py", "run_final_test.py")

        with tempfile.TemporaryDirectory() as working_directory:
            for script in scripts:
                with self.subTest(script=script):
                    result = subprocess.run(
                        [sys.executable, str(root / "scripts" / script), "--help"],
                        cwd=working_directory,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        check=False,
                    )

                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("Chạy", result.stdout)

    def test_runs_three_retrieval_baselines_reranker_and_all_metrics(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            results_path = root / "results" / "hybrid_reranker_test.json"
            metrics_path = root / "metrics" / "hybrid_reranker_test_metrics.json"
            with patch("sys.argv", [
                "run_final_test.py",
                "--results", str(results_path),
                "--metrics", str(metrics_path),
            ]), patch("scripts.run_final_test.subprocess.run") as run:
                with patch("scripts.run_final_test.verify_test_run", return_value="locked-commit"):
                    main()

        calls = [call.args[0] for call in run.call_args_list]
        self.assertEqual(len(calls), 2 + len(ALL_METHODS))
        baseline = calls[0]
        self.assertIn("retrieval.run_dev_retrieval", baseline)
        self.assertEqual(baseline[baseline.index("--output-prefix") + 1], "test")

        reranker = calls[1]
        self.assertIn("run_retrieval.py", reranker[1])
        self.assertEqual(reranker[reranker.index("--retriever") + 1], "hybrid")
        self.assertEqual(reranker[reranker.index("--reranker") + 1], "cross_encoder")

        scored_methods = [
            call[call.index("--method") + 1] for call in calls[2:]
        ]
        self.assertEqual(scored_methods, list(ALL_METHODS))


class TestRunFreezeTest(unittest.TestCase):
    def test_file_hash_is_independent_of_windows_line_endings(self):
        from evaluation.test_run_freeze import _file_sha256

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.txt"
            path.write_bytes(b"first line\r\nsecond line\r\n")
            windows_hash = _file_sha256(path)
            path.write_bytes(b"first line\nsecond line\n")
            linux_hash = _file_sha256(path)

        self.assertEqual(windows_hash, linux_hash)

    def test_committed_freeze_manifests_match_current_test_inputs(self):
        from evaluation.test_run_freeze import verify_test_run
        with patch("evaluation.test_run_freeze._require_committed", return_value="locked-commit"):
            commit = verify_test_run(
                QUERIES_TEST_PATH,
                GROUND_TRUTH_PATH,
                CHUNKS_PATH,
                Path(__file__).resolve().parents[1] / "retrieval" / "config.yaml",
                Path(__file__).resolve().parents[1] / "reranking" / "config.yaml",
                10,
                ALL_METHODS,
            )
        self.assertEqual(commit, "locked-commit")

    def test_preflight_rejects_empty_gold_before_retrieval(self):
        from evaluation.test_run_freeze import verify_test_run

        queries = json.loads(QUERIES_TEST_PATH.read_text(encoding="utf-8"))
        ground_truth = json.loads(GROUND_TRUTH_PATH.read_text(encoding="utf-8"))
        test_ids = {query["id"] for query in queries}
        test_gold = next(row for row in ground_truth if row["id"] in test_ids)
        test_gold["gold_context_ids"] = []
        test_gold["gold_context_ids_confirmed"] = False

        with tempfile.TemporaryDirectory() as temp_dir:
            ground_truth_path = Path(temp_dir) / "ground_truth.json"
            ground_truth_path.write_text(json.dumps(ground_truth), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "gold_context_ids thiếu"):
                verify_test_run(
                    QUERIES_TEST_PATH,
                    ground_truth_path,
                    CHUNKS_PATH,
                    Path(__file__).resolve().parents[1] / "retrieval" / "config.yaml",
                    Path(__file__).resolve().parents[1] / "reranking" / "config.yaml",
                    10,
                    ALL_METHODS,
                )


if __name__ == "__main__":
    unittest.main()
