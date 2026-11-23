import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.run_baselines import METHODS, RERANKER_RESULTS_NAME, main


class RunBaselinesOrchestrationTest(unittest.TestCase):
    def test_defaults_elasticsearch_url_for_retrieval_commands(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("sys.argv", [
                "run_baselines.py",
                "--results-dir", str(Path(temp_dir) / "retrieval"),
                "--metrics-dir", str(Path(temp_dir) / "metrics"),
            ]), patch.dict("os.environ", {}, clear=True), patch(
                "scripts.run_baselines.subprocess.run"
            ) as run:
                main()

        calls = [call.args[0] for call in run.call_args_list]
        for command in calls[:2]:
            self.assertEqual(
                command[command.index("--elasticsearch-url") + 1],
                "http://localhost:9200",
            )

    def test_runs_baselines_reranker_and_all_metric_methods(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            results_dir = root / "retrieval"
            metrics_dir = root / "metrics"
            retrieval_config = root / "retrieval.yaml"
            reranking_config = root / "reranking.yaml"
            with patch("sys.argv", [
                "run_baselines.py",
                "--results-dir", str(results_dir),
                "--metrics-dir", str(metrics_dir),
                "--top-k", "5",
                "--candidate-k", "20",
                "--rrf-k", "42",
                "--model", "test-dense-model",
                "--collection", "test-collection",
                "--elasticsearch-url", "http://localhost:9200",
                "--elasticsearch-index", "test-index",
                "--config", str(retrieval_config),
                "--reranking-config", str(reranking_config),
            ]), patch("scripts.run_baselines.subprocess.run") as run:
                main()

        calls = [call.args[0] for call in run.call_args_list]
        self.assertEqual(len(calls), 3)
        self.assertIn("retrieval.run_dev_retrieval", calls[0])

        reranker = calls[1]
        self.assertIn("run_retrieval.py", reranker[1])
        self.assertEqual(reranker[reranker.index("--output") + 1],
                         str(results_dir / RERANKER_RESULTS_NAME))
        self.assertEqual(reranker[reranker.index("--retriever") + 1], "hybrid")
        self.assertEqual(reranker[reranker.index("--reranker") + 1], "cross_encoder")
        self.assertEqual(reranker[reranker.index("--retrieval-top-k") + 1], "20")
        self.assertEqual(reranker[reranker.index("--rrf-k") + 1], "42")
        self.assertEqual(reranker[reranker.index("--dense-model") + 1], "test-dense-model")
        self.assertEqual(reranker[reranker.index("--collection") + 1], "test-collection")
        self.assertEqual(reranker[reranker.index("--retrieval-config") + 1],
                         str(retrieval_config))
        self.assertEqual(reranker[reranker.index("--config") + 1],
                         str(reranking_config))
        self.assertNotIn("--allow-test-split", reranker)

        metrics = calls[2]
        methods_start = metrics.index("--methods") + 1
        self.assertEqual(
            metrics[methods_start:methods_start + len(METHODS)], list(METHODS)
        )
        self.assertEqual(metrics[metrics.index("--top-k") + 1], "5")
        self.assertIn(sys.executable, calls[0])
        self.assertIn(sys.executable, metrics)


if __name__ == "__main__":
    unittest.main()
