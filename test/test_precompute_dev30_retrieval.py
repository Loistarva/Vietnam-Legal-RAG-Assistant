"""Unit tests for scripts/precompute_dev30_retrieval.py (copy beside repo tests)."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[1]
for directory in (REPO_ROOT, REPO_ROOT / "scripts", SCRIPT_DIR):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

import precompute_dev30_retrieval as pipeline
from reranking.reranker import candidate_text


class ReadOfficialIdsTests(unittest.TestCase):
    def test_requires_exactly_30_unique_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ids.txt"
            path.write_text("\n".join(f"Q{i:02d}" for i in range(30)), encoding="utf-8")
            self.assertEqual(len(pipeline.read_official_ids(path)), 30)

    def test_rejects_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ids.txt"
            path.write_text("\n".join(["Q00"] * 30), encoding="utf-8")
            with self.assertRaises(pipeline.PrecomputeError):
                pipeline.read_official_ids(path)


class BenchmarkTests(unittest.TestCase):
    def test_reads_as_of_date_by_query_id(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "queries.json"
            path.write_text(
                '[{"id":"Q00","question":"Question?","as_of_date":"2010-01-01"}]',
                encoding="utf-8",
            )
            rows = pipeline.read_benchmark(path, ["Q00"])
            self.assertEqual(rows["Q00"]["as_of_date"], "2010-01-01")

    def test_missing_as_of_date_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "queries.json"
            path.write_text('[{"id":"Q00","question":"Question?"}]', encoding="utf-8")
            with self.assertRaises(pipeline.PrecomputeError):
                pipeline.read_benchmark(path, ["Q00"])


class BuildPrecomputeTests(unittest.TestCase):
    def setUp(self):
        self.ids = [f"Q{i:02d}" for i in range(30)]
        self.benchmark = {
            query_id: {
                "query_id": query_id,
                "query": f"Question {query_id}?",
                "as_of_date": "2010-01-01",
            }
            for query_id in self.ids
        }
        self.config = {
            "retrieval_top_k": 50,
            "result_top_k": 10,
            "rrf_k": 60,
            "rerank_top_k": 5,
            "max_candidates": 50,
            "candidate_text": pipeline.EXPECTED_CANDIDATE_TEXT,
            "reranker_backend": "cross_encoder",
            "reranker_model": "BAAI/bge-reranker-v2-m3",
        }
        self.source = [
            {
                "query_id": query_id,
                "query": f"Question {query_id}?",
                "retriever": "hybrid_reranker",
                "config": {
                    "retriever": {"retrieval_top_k": 50, "rrf_k": 60},
                    "reranker": {
                        "backend": "cross_encoder",
                        "model": "BAAI/bge-reranker-v2-m3",
                        "rerank_top_k": 5,
                        "max_candidates": 50,
                        "candidate_text": pipeline.EXPECTED_CANDIDATE_TEXT,
                    }
                },
                "results": [{
                    "chunk_id": f"{query_id}_CHUNK_1",
                    "chunk_text": "Nội dung khoản pháp luật.",
                    "rank": 1,
                    "score": 0.95,
                    "retrieval_rank": 3,
                    "retrieval_score": 0.02,
                    "metadata": {
                        "title": "Luật Hôn nhân và gia đình 2014",
                        "breadcrumb": "Chương II > Điều 8 > Khoản 1",
                    },
                }],
            }
            for query_id in self.ids
        ]

    def test_builds_30_records_with_benchmark_date_and_candidate_text(self):
        output = pipeline.build_precompute_records(
            self.source, self.benchmark, self.ids, candidate_text, self.config
        )
        self.assertEqual(len(output), 30)
        self.assertTrue(all(row["precomputed"] is True for row in output))
        self.assertTrue(all(row["as_of_date"] == "2010-01-01" for row in output))
        self.assertEqual(
            output[0]["results"][0]["candidate_text"],
            "Luật Hôn nhân và gia đình 2014\nChương II > Điều 8 > Khoản 1\nNội dung khoản pháp luật.",
        )

    def test_rejects_wrong_candidate_text_mode(self):
        broken = [dict(self.source[0])]
        broken[0]["config"] = {
            "retriever": {"retrieval_top_k": 50, "rrf_k": 60},
            "reranker": {
                "backend": "cross_encoder",
                "model": "BAAI/bge-reranker-v2-m3",
                "rerank_top_k": 5,
                "max_candidates": 50,
                "candidate_text": "chunk_text",
            },
        }
        with self.assertRaises(pipeline.PrecomputeError):
            pipeline.build_precompute_records(
                broken, self.benchmark, self.ids, candidate_text, self.config
            )

    def test_rejects_missing_official_query(self):
        with self.assertRaises(pipeline.PrecomputeError):
            pipeline.build_precompute_records(
                self.source[:-1], self.benchmark, self.ids, candidate_text, self.config
            )


class ConfigTests(unittest.TestCase):
    def test_reads_result_top_k_from_hybrid_top_k(self):
        retrieval_cfg = {
            "retrieval": {"retrieval_top_k": 50},
            "hybrid": {"top_k": 10, "rrf_k": 60},
        }
        rerank_cfg = {
            "reranker": {
                "rerank_top_k": 5,
                "max_candidates": 50,
                "candidate_text": pipeline.EXPECTED_CANDIDATE_TEXT,
                "backend": "cross_encoder",
                "model": "BAAI/bge-reranker-v2-m3",
            }
        }
        values = pipeline._config_values(retrieval_cfg, rerank_cfg)
        self.assertEqual(values["result_top_k"], 10)
        self.assertEqual(values["retrieval_top_k"], 50)
        self.assertEqual(values["rrf_k"], 60)

    def test_rejects_non_cross_encoder_backend(self):
        retrieval_cfg = {
            "retrieval": {"retrieval_top_k": 50},
            "hybrid": {"top_k": 10, "rrf_k": 60},
        }
        rerank_cfg = {
            "reranker": {
                "rerank_top_k": 5,
                "max_candidates": 50,
                "candidate_text": pipeline.EXPECTED_CANDIDATE_TEXT,
                "backend": "mock",
                "model": "BAAI/bge-reranker-v2-m3",
            }
        }
        with self.assertRaises(pipeline.PrecomputeError):
            pipeline._config_values(retrieval_cfg, rerank_cfg)


if __name__ == "__main__":
    unittest.main(verbosity=2)
