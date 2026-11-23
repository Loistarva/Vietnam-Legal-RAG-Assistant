import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.run_baselines_metrics import main
from embedding.vector_store import chunk_file_sha256


class RunBaselinesMetricsTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.queries_path = self.root / "queries.json"
        self.ground_truth_path = self.root / "ground_truth.json"
        self.chunks_path = self.root / "chunks.jsonl"
        self.results_dir = self.root / "retrieval"
        self.metrics_dir = self.root / "metrics"
        self.results_dir.mkdir()
        self.query = {
            "id": "Q1",
            "question": "What is the question?",
            "category": "test",
            "as_of_date": "2026-10-15",
        }
        self.queries_path.write_text(
            json.dumps([self.query]), encoding="utf-8"
        )
        self.ground_truth_path.write_text(
            json.dumps([{
                "id": "Q1",
                "split": "dev",
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
            "corpus_sha256": chunk_file_sha256(self.chunks_path),
            "as_of_date": self.query["as_of_date"],
        }
        results = [{
            "query_id": "Q1",
            "query": self.query["question"],
            "retriever": "hybrid",
            "top_k": 10,
            "config": config,
            "results": [{
                "chunk_id": "c1",
                "parent_clause_id": "p1",
                "rank": 1,
            }],
        }]
        (self.results_dir / "dev_hybrid.json").write_text(
            json.dumps(results), encoding="utf-8"
        )

    def _run(self):
        with patch("sys.argv", [
            "run_baselines_metrics.py",
            "--queries", str(self.queries_path),
            "--ground-truth", str(self.ground_truth_path),
            "--chunks", str(self.chunks_path),
            "--results-dir", str(self.results_dir),
            "--metrics-dir", str(self.metrics_dir),
            "--methods", "hybrid",
        ]):
            main()

    def test_metric_records_gold_context_source_and_input_provenance(self):
        from evaluation.test_run_freeze import _file_sha256

        self._run()
        report_path = self.metrics_dir / "hybrid_dev_metrics.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["label_source"], "ground_truth.gold_context_ids")
        self.assertEqual(
            report["input_sha256"]["corpus"],
            chunk_file_sha256(self.chunks_path),
        )
        self.assertEqual(
            report["input_sha256"]["queries"],
            _file_sha256(self.queries_path),
        )
        self.assertEqual(report["run_config"]["top_k"], 10)
        self.assertNotIn("label_source", report["per_question"][0])

    def test_changed_corpus_is_rejected(self):
        with self.chunks_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps({"chunk_id": "c2"}) + "\n")
        with self.assertRaisesRegex(ValueError, "corpus_sha256 không khớp"):
            self._run()
        self.assertFalse((self.metrics_dir / "hybrid_dev_metrics.json").exists())

    def test_changed_question_text_is_rejected(self):
        self.query["question"] = "Changed question"
        self.queries_path.write_text(
            json.dumps([self.query]), encoding="utf-8"
        )
        with self.assertRaisesRegex(ValueError, "query text không khớp"):
            self._run()
        self.assertFalse((self.metrics_dir / "hybrid_dev_metrics.json").exists())

    def test_gold_chunk_missing_from_corpus_is_rejected_before_scoring(self):
        self.ground_truth_path.write_text(
            json.dumps([{
                "id": "Q1",
                "split": "dev",
                "gold_context_ids": ["missing-chunk"],
                "gold_context_ids_confirmed": True,
            }]),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "không có trong corpus: missing-chunk"):
            self._run()

        self.assertFalse((self.metrics_dir / "hybrid_dev_metrics.json").exists())

    def test_gold_chunk_without_parent_metadata_is_validated_against_corpus(self):
        self.chunks_path.write_text(
            json.dumps({"chunk_id": "c1"}) + "\n",
            encoding="utf-8",
        )
        self._write_results()

        self._run()

        self.assertTrue((self.metrics_dir / "hybrid_dev_metrics.json").exists())


if __name__ == "__main__":
    unittest.main()
