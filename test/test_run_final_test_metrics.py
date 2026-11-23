import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.run_final_test_metrics import main
from embedding.vector_store import chunk_file_sha256


class RunFinalTestMetricsTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.queries_path = self.root / "queries_test.json"
        self.ground_truth_path = self.root / "ground_truth.json"
        self.chunks_path = self.root / "chunks.jsonl"
        self.results_path = self.root / "hybrid_reranker_test.json"
        self.metrics_path = self.root / "hybrid_reranker_test_metrics.json"
        self.query = {
            "id": "Q1",
            "question": "Test question?",
            "category": "test",
            "as_of_date": "2026-10-15",
        }
        self.queries_path.write_text(
            json.dumps([self.query]), encoding="utf-8"
        )
        self.ground_truth_path.write_text(
            json.dumps([{
                "id": "Q1",
                "split": "test",
                "gold_context_ids": ["c1"],
                "gold_context_ids_confirmed": True,
            }]),
            encoding="utf-8",
        )
        self.chunks_path.write_text(
            json.dumps({"chunk_id": "c1", "parent_clause_id": "p1"}) + "\n",
            encoding="utf-8",
        )
        self._write_results()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_results(self):
        config = {
            "top_k": 10,
            "retriever": {
                "backend": "hybrid",
                "corpus_sha256": chunk_file_sha256(self.chunks_path),
            },
            "reranker": {"backend": "cross_encoder"},
            "as_of_date": self.query["as_of_date"],
        }
        self.results_path.write_text(
            json.dumps([{
                "query_id": "Q1",
                "query": self.query["question"],
                "retriever": "hybrid_reranker",
                "top_k": 10,
                "config": config,
                "results": [{
                    "chunk_id": "c1",
                    "parent_clause_id": "p1",
                    "rank": 1,
                }],
            }]),
            encoding="utf-8",
        )

    def _run(self):
        with patch("scripts.run_final_test_metrics.verify_test_run", return_value="locked-commit"), \
             patch("sys.argv", [
            "run_final_test_metrics.py",
            "--queries", str(self.queries_path),
            "--ground-truth", str(self.ground_truth_path),
            "--chunks", str(self.chunks_path),
            "--results", str(self.results_path),
            "--metrics", str(self.metrics_path),
            "--method", "hybrid_reranker",
        ]):
            main()

    def test_test_metric_records_provenance_and_test_split(self):
        from evaluation.test_run_freeze import _file_sha256

        self._run()
        report = json.loads(self.metrics_path.read_text(encoding="utf-8"))
        self.assertEqual(report["label_source"], "ground_truth.gold_context_ids")
        self.assertEqual(report["evaluation_config"]["split"], "test")
        self.assertEqual(report["evaluation_config"]["method"], "hybrid_reranker")
        self.assertEqual(
            report["input_sha256"]["corpus"],
            chunk_file_sha256(self.chunks_path),
        )
        self.assertEqual(
            report["input_sha256"]["queries"],
            _file_sha256(self.queries_path),
        )
        self.assertEqual(
            report["input_sha256"]["ground_truth"],
            _file_sha256(self.ground_truth_path),
        )
        self.assertEqual(
            report["input_sha256"]["retrieval_results"],
            _file_sha256(self.results_path),
        )
        self.assertEqual(report["run_config"]["top_k"], 10)

    def test_test_metric_input_hashes_are_independent_of_windows_line_endings(self):
        from evaluation.test_run_freeze import _file_sha256

        self._run()
        original_hashes = json.loads(
            self.metrics_path.read_text(encoding="utf-8")
        )["input_sha256"]

        for path in (self.queries_path, self.ground_truth_path, self.results_path):
            path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))

        self._run()
        windows_hashes = json.loads(
            self.metrics_path.read_text(encoding="utf-8")
        )["input_sha256"]
        for key, path in (
            ("queries", self.queries_path),
            ("ground_truth", self.ground_truth_path),
            ("retrieval_results", self.results_path),
        ):
            self.assertEqual(original_hashes[key], windows_hashes[key])
            self.assertEqual(windows_hashes[key], _file_sha256(path))

    def test_test_metric_rejects_changed_corpus(self):
        with self.chunks_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps({"chunk_id": "c2"}) + "\n")
        with self.assertRaisesRegex(ValueError, "corpus_sha256 không khớp"):
            self._run()
        self.assertFalse(self.metrics_path.exists())

    def test_test_metric_rejects_empty_gold_instead_of_skipping(self):
        self.ground_truth_path.write_text(
            json.dumps([{
                "id": "Q1",
                "split": "test",
                "gold_context_ids": [],
                "gold_context_ids_confirmed": False,
            }]),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "gold_context_ids thiếu"):
            self._run()
        self.assertFalse(self.metrics_path.exists())

    def test_test_metric_rejects_gold_chunk_missing_from_corpus(self):
        self.ground_truth_path.write_text(
            json.dumps([{
                "id": "Q1",
                "split": "test",
                "gold_context_ids": ["missing-chunk"],
                "gold_context_ids_confirmed": True,
            }]),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "không có trong corpus: missing-chunk"):
            self._run()

        self.assertFalse(self.metrics_path.exists())


if __name__ == "__main__":
    unittest.main()
