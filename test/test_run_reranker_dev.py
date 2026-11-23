import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.run_reranker_dev import RESULTS_NAME, main


class RunRerankerDevTest(unittest.TestCase):
    def test_runs_only_dev_reranker_and_its_metrics(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            queries = root / "queries.json"
            queries.write_text(
                json.dumps([{"id": "HN_001", "question": "?", "split": "dev"}]),
                encoding="utf-8",
            )
            results_dir = root / "results"
            metrics_dir = root / "metrics"
            with patch("sys.argv", [
                "run_reranker_dev.py",
                "--queries", str(queries),
                "--results-dir", str(results_dir),
                "--metrics-dir", str(metrics_dir),
                "--top-k", "5",
                "--elasticsearch-url", "http://localhost:9200",
            ]), patch("scripts.run_reranker_dev.subprocess.run") as run:
                main()

        calls = [call.args[0] for call in run.call_args_list]
        self.assertEqual(len(calls), 2)
        retrieval, metrics = calls
        self.assertIn("run_retrieval.py", retrieval[1])
        self.assertEqual(retrieval[retrieval.index("--retriever") + 1], "hybrid")
        self.assertEqual(retrieval[retrieval.index("--reranker") + 1], "cross_encoder")
        self.assertEqual(
            retrieval[retrieval.index("--output") + 1],
            str(results_dir / RESULTS_NAME),
        )
        self.assertNotIn("--allow-test-split", retrieval)
        self.assertEqual(
            metrics[metrics.index("--methods") + 1],
            "hybrid_reranker",
        )
        self.assertEqual(metrics[metrics.index("--top-k") + 1], "5")
        self.assertIn(sys.executable, retrieval)
        self.assertIn(sys.executable, metrics)

    def test_rejects_non_dev_queries_before_running_commands(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            queries = Path(temp_dir) / "queries_test.json"
            queries.write_text(
                json.dumps([{"id": "HN_200", "question": "?", "split": "test"}]),
                encoding="utf-8",
            )
            with patch("sys.argv", [
                "run_reranker_dev.py", "--queries", str(queries),
            ]), patch("scripts.run_reranker_dev.subprocess.run") as run:
                with self.assertRaises(SystemExit) as exc:
                    main()

        self.assertEqual(exc.exception.code, 2)
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
