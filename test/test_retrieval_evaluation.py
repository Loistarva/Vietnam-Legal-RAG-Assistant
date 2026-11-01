import json
import hashlib
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from retrieval.retrieval_evaluation import evaluate
from retrieval.settings import load_settings


RUN_CONFIG = {
    "top_k": 10, "candidate_k": 50, "rrf_k": 60,
    "dense_model": "BAAI/bge-m3", "dimension": 1024,
    "collection": "vietnam_legal_chunks", "elasticsearch_index": "legal-child-chunks-dev",
    "fusion": "rrf",
}


class RetrievalEvaluationTest(unittest.TestCase):
    def test_duplicate_question_without_id_and_duplicate_query_id_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dev_path = root / "dev.json"
            rows = [
                {"question": "same", "relevant_chunk_ids": ["A"]},
                {"query": "same", "relevant_chunk_ids": ["B"]},
            ]
            dev_path.write_text(json.dumps(rows), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "thiếu id"):
                evaluate(dev_path, root / "missing-results", root / "output")
            rows[0]["id"] = "Q1"
            rows[1]["query_id"] = "Q1"
            dev_path.write_text(json.dumps(rows), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "id/query_id trùng"):
                evaluate(dev_path, root / "missing-results", root / "output")

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
                "id": "Q-HIST",
                "question": query,
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
            temporal_config = {
                **RUN_CONFIG,
                "as_of_date": as_of_date,
                "corpus_sha256": hashlib.sha256(chunks_path.read_bytes()).hexdigest(),
            }
            for method in ("bm25", "dense", "hybrid"):
                envelope = [{
                    "query_id": "Q-HIST",
                    "query": query,
                    "retriever": method,
                    "top_k": 10,
                    "config": temporal_config,
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
            dev_path.write_text(json.dumps([{"id": "Q1", "question": query,
                                             "relevant_chunk_ids": ["A", "B"]}]), encoding="utf-8")
            chunks_path.write_text(json.dumps([
                {"chunk_id": "A", "chunk_text": "relevant A", "metadata": {"article_ref": "A"}},
                {"chunk_id": "B", "chunk_text": "relevant B", "metadata": {"article_ref": "B"}},
                {"chunk_id": "C", "chunk_text": "irrelevant", "metadata": {"article_ref": "C"}},
            ]), encoding="utf-8")
            results_dir.mkdir()
            run_config = {**RUN_CONFIG, "corpus_sha256": hashlib.sha256(chunks_path.read_bytes()).hexdigest()}
            for method in ("bm25", "dense", "hybrid"):
                envelope = [{
                    "query_id": "Q1",
                    "query": query,
                    "retriever": method,
                    "config": run_config,
                    "top_k": 10,
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

    def test_metrics_cutoff_and_report_follow_shared_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = load_settings()
            settings["retrieval"]["result_top_k"] = 2
            settings["retrieval"]["retrieval_top_k"] = 5
            config_path = root / "config.yaml"
            config_path.write_text(yaml.safe_dump(settings, allow_unicode=True), encoding="utf-8")
            dev_path, chunks_path = root / "dev.json", root / "chunks.json"
            results_dir, output_dir = root / "results", root / "output"
            query = "question"
            dev_path.write_text(json.dumps([{"id": "Q1", "question": query,
                                             "relevant_chunk_ids": ["A", "B"]}]), encoding="utf-8")
            chunks_path.write_text(json.dumps([
                {"chunk_id": "A", "text": "relevant A", "metadata": {}},
                {"chunk_id": "B", "text": "relevant B", "metadata": {}},
                {"chunk_id": "C", "text": "irrelevant", "metadata": {}},
            ]), encoding="utf-8")
            results_dir.mkdir()
            run_config = {
                **RUN_CONFIG, "top_k": 2, "candidate_k": 5,
                "corpus_sha256": hashlib.sha256(chunks_path.read_bytes()).hexdigest(),
            }
            for method in ("bm25", "dense", "hybrid"):
                (results_dir / f"dev_{method}.json").write_text(json.dumps([{
                    "query_id": "Q1", "query": query, "retriever": method,
                    "config": run_config,
                    "top_k": 2,
                    "results": [
                        {"chunk_id": "C", "score": 1.0, "rank": 1},
                        {"chunk_id": "A", "score": 0.9, "rank": 2},
                    ],
                }]), encoding="utf-8")
            metrics = evaluate(dev_path, results_dir, output_dir, chunks_path, config_path=config_path)
            self.assertEqual(metrics["hybrid"]["recall_at_2"], 0.5)
            report = (output_dir / "retrieval_report.md").read_text(encoding="utf-8")
            self.assertIn("Recall@2", report)
            self.assertIn("candidate depth=5", report)

    def test_result_config_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dev_path, chunks_path = root / "dev.json", root / "chunks.json"
            results_dir = root / "results"
            dev_path.write_text(json.dumps([{"id": "Q1", "question": "question",
                                             "relevant_chunk_ids": ["A"]}]), encoding="utf-8")
            chunks_path.write_text(json.dumps([{"chunk_id": "A", "text": "A", "metadata": {}}]), encoding="utf-8")
            results_dir.mkdir()
            actual_hash = hashlib.sha256(chunks_path.read_bytes()).hexdigest()
            for changed, invalid_value in (("rrf_k", 20), ("dense_model", "unknown/model"),
                                           ("corpus_sha256", "f" * 64)):
                bad_config = {**RUN_CONFIG, "corpus_sha256": actual_hash, changed: invalid_value}
                for method in ("bm25", "dense", "hybrid"):
                    (results_dir / f"dev_{method}.json").write_text(json.dumps([{
                        "query_id": "Q1", "query": "question", "retriever": method, "config": bad_config,
                        "top_k": 10,
                        "results": [{"chunk_id": "A", "score": 1.0, "rank": 1}],
                    }]), encoding="utf-8")
                with self.subTest(config_field=changed), self.assertRaisesRegex(
                    ValueError, "không khớp shared config"
                ):
                    evaluate(dev_path, results_dir, root / "output", chunks_path)

    def test_flat_format_rejected_raises_value_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dev_path = root / "dev.json"
            chunks_path = root / "chunks.json"
            results_dir = root / "results"
            output_dir = root / "output"
            query = "question"
            dev_path.write_text(json.dumps([{"id": "Q1", "question": query,
                                             "relevant_chunk_ids": ["A"]}]), encoding="utf-8")
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

    def test_evaluator_uses_query_id_for_duplicate_question_text_and_resolves_relative_chunks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dev_path, chunks_path = root / "dev.json", root / "relative" / "chunks.json"
            results_dir, output_dir = root / "results", root / "output"
            chunks_path.parent.mkdir()
            chunks_path.write_text(json.dumps([
                {"chunk_id": "A", "text": "A", "metadata": {}},
                {"chunk_id": "B", "text": "B", "metadata": {}},
            ]), encoding="utf-8")
            same_question = "Cùng một câu hỏi"
            dev_path.write_text(json.dumps([
                {"id": "Q1", "question": same_question, "relevant_chunk_ids": ["A"]},
                {"id": "Q2", "question": same_question, "relevant_chunk_ids": ["B"]},
            ]), encoding="utf-8")
            results_dir.mkdir()
            config = {
                **RUN_CONFIG,
                "corpus_sha256": hashlib.sha256(chunks_path.read_bytes()).hexdigest(),
            }
            for method in ("bm25", "dense", "hybrid"):
                (results_dir / f"dev_{method}.json").write_text(json.dumps([
                    {"query_id": "Q1", "query": same_question, "retriever": method,
                     "config": config, "top_k": 10,
                     "results": [{"chunk_id": "A", "score": 1.0, "rank": 1}]},
                    {"query_id": "Q2", "query": same_question, "retriever": method,
                     "config": config, "top_k": 10,
                     "results": [{"chunk_id": "A", "score": 1.0, "rank": 1}]},
                ]), encoding="utf-8")
            with patch("retrieval.retrieval_evaluation.ROOT", root):
                metrics = evaluate(dev_path, results_dir, output_dir, Path("relative/chunks.json"))
            self.assertEqual(metrics["hybrid"]["query_count"], 2.0)
            self.assertEqual(metrics["hybrid"]["recall_at_10"], 0.5)


if __name__ == "__main__":
    unittest.main()
