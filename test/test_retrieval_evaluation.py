import json
import math
import tempfile
import unittest
from pathlib import Path

from retrieval.retrieval_evaluation import evaluate


class RetrievalEvaluationTest(unittest.TestCase):
    def test_temporal_violation_rate_checks_effective_dates_and_counts_missing_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dev_path = root / "dev.json"
            chunks_path = root / "chunks.json"
            results_dir = root / "results"
            output_dir = root / "output"
            query = "historical question"
            as_of_date = "2024-06-01"
            dev_path.write_text(json.dumps([{
                "query": query,
                "as_of_date": as_of_date,
                "relevant_chunk_ids": ["valid"],
            }]), encoding="utf-8")
            chunks_path.write_text(json.dumps([
                {"chunk_id": "valid", "text": "valid", "effective_from": "2020-01-01",
                 "effective_to": None, "metadata": {}},
                {"chunk_id": "future", "text": "future", "effective_from": "2027-01-01",
                 "effective_to": None, "metadata": {}},
                {"chunk_id": "expired", "text": "expired", "effective_from": "1980-01-01",
                 "effective_to": "2001-01-01", "metadata": {}},
                {"chunk_id": "unknown", "text": "unknown", "metadata": {}},
            ]), encoding="utf-8")
            results_dir.mkdir()
            for method in ("bm25", "dense", "hybrid"):
                envelope = [{
                    "query_id": "Q-HIST",
                    "query": query,
                    "retriever": method,
                    "config": {"as_of_date": as_of_date},
                    "results": [
                        {"chunk_id": "valid", "score": 1.0, "rank": 1},
                        {"chunk_id": "future", "score": 0.9, "rank": 2},
                        {"chunk_id": "expired", "score": 0.8, "rank": 3},
                        {"chunk_id": "unknown", "score": 0.7, "rank": 4},
                    ],
                }]
                (results_dir / f"dev_{method}.json").write_text(json.dumps(envelope), encoding="utf-8")

            metrics = evaluate(dev_path, results_dir, output_dir, chunks_path)
            hybrid = metrics["hybrid"]
            self.assertEqual(hybrid["temporal_checked_count"], 3.0)
            self.assertEqual(hybrid["temporal_violation_count"], 2.0)
            self.assertEqual(hybrid["temporal_metadata_missing_count"], 1.0)
            self.assertAlmostEqual(hybrid["temporal_violation_rate"], 2 / 3)
            report = (output_dir / "retrieval_report.md").read_text(encoding="utf-8")
            self.assertIn("Temporal Violation Rate", report)
            self.assertIn("2 / 3", report)

    def test_recall_mrr_ndcg_and_precision_are_computed_from_dev_labels(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dev_path = root / "dev.json"
            chunks_path = root / "chunks.json"
            results_dir = root / "results"
            output_dir = root / "output"
            query = "question"
            dev_path.write_text(json.dumps([{"query": query, "relevant_chunk_ids": ["A", "B"]}]), encoding="utf-8")
            chunks_path.write_text(json.dumps([
                {"chunk_id": "A", "text": "relevant A", "metadata": {"article_ref": "A"}},
                {"chunk_id": "B", "text": "relevant B", "metadata": {"article_ref": "B"}},
                {"chunk_id": "C", "text": "irrelevant", "metadata": {"article_ref": "C"}},
            ]), encoding="utf-8")
            results_dir.mkdir()
            for method in ("bm25", "dense", "hybrid"):
                envelope = [{
                    "query_id": "Q1",
                    "query": query,
                    "retriever": method,
                    "results": [
                        {"chunk_id": "C", "score": 1.0, "rank": 1},
                        {"chunk_id": "A", "score": 0.9, "rank": 2},
                        {"chunk_id": "B", "score": 0.8, "rank": 3},
                    ],
                }]
                (results_dir / f"dev_{method}.json").write_text(json.dumps(envelope), encoding="utf-8")

            metrics = evaluate(dev_path, results_dir, output_dir, chunks_path)
            row = metrics["hybrid"]
            expected_ndcg = (1 / math.log2(3) + 1 / math.log2(4)) / (1 + 1 / math.log2(3))
            self.assertEqual(row["recall_at_10"], 1.0)
            self.assertEqual(row["mrr_at_10"], 0.5)
            self.assertAlmostEqual(row["ndcg_at_10"], expected_ndcg)
            self.assertEqual(row["precision_at_10"], 0.2)

    def test_flat_format_rejected_raises_value_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dev_path = root / "dev.json"
            chunks_path = root / "chunks.json"
            results_dir = root / "results"
            output_dir = root / "output"
            query = "question"
            dev_path.write_text(json.dumps([{"query": query, "relevant_chunk_ids": ["A"]}]), encoding="utf-8")
            chunks_path.write_text(json.dumps([
                {"chunk_id": "A", "text": "relevant A", "metadata": {"article_ref": "A"}},
            ]), encoding="utf-8")
            results_dir.mkdir()
            for method in ("bm25", "dense", "hybrid"):
                flat_rows = [{"query": query, "chunk_id": "A", "score": 1.0, "rank": 1}]
                (results_dir / f"dev_{method}.json").write_text(json.dumps(flat_rows), encoding="utf-8")

            with self.assertRaises(ValueError) as ctx:
                evaluate(dev_path, results_dir, output_dir, chunks_path)
            self.assertIn("RetrievalEnvelope", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
