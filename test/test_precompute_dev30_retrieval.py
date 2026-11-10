"""Unit tests for scripts/precompute_dev30_retrieval.py (copy beside repo tests)."""
from __future__ import annotations

import sys
import tempfile
import unittest
import copy
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[1]
for directory in (REPO_ROOT, REPO_ROOT / "scripts", SCRIPT_DIR):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

import precompute_dev30_retrieval as pipeline
from reranking.reranker import candidate_text


class NewlineHashTests(unittest.TestCase):
    def test_normalized_hash_is_stable_for_lf_crlf_and_bare_cr(self):
        lf = b"line 1\nline 2\n"
        crlf = b"line 1\r\nline 2\r\n"
        bare_cr = b"line 1\rline 2\r"
        expected = pipeline.normalized_bytes_sha256(lf)
        self.assertEqual(pipeline.normalized_bytes_sha256(crlf), expected)
        self.assertEqual(pipeline.normalized_bytes_sha256(bare_cr), expected)
        self.assertNotEqual(pipeline.sha256_bytes(lf), pipeline.sha256_bytes(crlf))

    def test_normalized_file_hash_matches_across_newline_styles(self):
        with tempfile.TemporaryDirectory() as directory:
            lf_path = Path(directory) / "lf.txt"
            crlf_path = Path(directory) / "crlf.txt"
            lf_path.write_bytes(b"line 1\nline 2\n")
            crlf_path.write_bytes(b"line 1\r\nline 2\r\n")
            self.assertEqual(
                pipeline.normalized_file_sha256(lf_path),
                pipeline.normalized_file_sha256(crlf_path),
            )
            self.assertNotEqual(pipeline.sha256_file(lf_path), pipeline.sha256_file(crlf_path))


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
                    "retriever": {
                        "retrieval_top_k": 50,
                        "rrf_k": 60,
                        "corpus_sha256": "7105c484061399010b0f087c6c0d457cd688030b8184b0071f1291a036b6b023",
                    },
                    "as_of_date": "2010-01-01",
                    "reranker": {
                        "backend": "cross_encoder",
                        "model": "BAAI/bge-reranker-v2-m3",
                        "rerank_top_k": 5,
                        "max_candidates": 50,
                        "candidate_text": pipeline.EXPECTED_CANDIDATE_TEXT,
                    }
                },
                "results": [{
                    "chunk_id": f"{query_id}_CHUNK_{rank}",
                    "chunk_text": "Nội dung khoản pháp luật.",
                    "rank": rank,
                    "score": 0.95 - rank / 100,
                    "retrieval_rank": rank + 2,
                    "retrieval_score": 0.02,
                    "metadata": {
                        "title": "Luật Hôn nhân và gia đình 2014",
                        "breadcrumb": "Chương II > Điều 8 > Khoản 1",
                    },
                } for rank in range(1, 6)],
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
        self.assertTrue(all(row["reranked_result_count"] == 5 for row in output))
        self.assertTrue(all(row["source_result_count"] == 5 for row in output))
        self.assertEqual(
            output[0]["results"][0]["candidate_text"],
            "Luật Hôn nhân và gia đình 2014\nChương II > Điều 8 > Khoản 1\nNội dung khoản pháp luật.",
        )

    def test_retrieval_rank_falls_back_to_source_ranks_retrieval(self):
        source = copy.deepcopy(self.source)
        for record in source:
            for hit in record["results"]:
                hit.pop("retrieval_rank", None)
                hit.pop("source_rank", None)
                hit["source_ranks"] = {"bm25": 3, "dense": 1, "retrieval": 1}
        output = pipeline.build_precompute_records(
            source, self.benchmark, self.ids, candidate_text, self.config
        )
        self.assertEqual(
            [hit["retrieval_rank"] for hit in output[0]["results"]],
            [1, 1, 1, 1, 1],
        )

    def test_source_run_config_redacts_absolute_machine_paths(self):
        sanitized = pipeline.sanitize_source_config({
            "retriever": {
                "qdrant_path": r"D:\\AI_PRJ\\wt-leftover\\data\\indexes\\qdrant_storage",
                "scratch": r"C:\\Users\\ADMIN\\AppData\\Local\\Temp\\claude\\scratchpad\\cand_dev_top50.json",
                "retrieval_top_k": 50,
            }
        })
        serialized = str(sanitized)
        self.assertNotIn("AI_PRJ", serialized)
        self.assertNotIn("Users", serialized)
        self.assertIn("qdrant_storage", serialized)
        self.assertIn("cand_dev_top50.json", serialized)
        self.assertEqual(sanitized["retriever"]["retrieval_top_k"], 50)

    def test_selects_top_five_from_ten_result_g3(self):
        ten_result_source = []
        for row in self.source:
            clone = dict(row)
            clone["results"] = [
                {
                    "chunk_id": f"{row['query_id']}_TOP_{rank}",
                    "chunk_text": "Nội dung pháp luật.",
                    "rank": rank,
                    "score": 1.0 - rank / 100,
                    "source_ranks": {"bm25": rank, "dense": rank, "retrieval": rank},
                    "metadata": {"title": "Luật Hôn nhân và gia đình", "breadcrumb": "Điều 1"},
                }
                for rank in range(1, 11)
            ]
            ten_result_source.append(clone)
        output = pipeline.build_precompute_records(
            ten_result_source, self.benchmark, self.ids, candidate_text, self.config,
            expected_corpus_sha256="7105c484061399010b0f087c6c0d457cd688030b8184b0071f1291a036b6b023",
        )
        self.assertTrue(all(row["source_result_count"] == 10 for row in output))
        self.assertTrue(all([hit["rank"] for hit in row["results"]] == [1, 2, 3, 4, 5]
                            for row in output))

    def test_rejects_g3_from_different_corpus(self):
        broken = copy.deepcopy(self.source)
        broken[0]["config"]["retriever"]["corpus_sha256"] = "c" * 64
        with self.assertRaisesRegex(pipeline.PrecomputeError, "khác corpus hiện tại"):
            pipeline.build_precompute_records(
                broken, self.benchmark, self.ids, candidate_text, self.config,
                expected_corpus_sha256="7105c484061399010b0f087c6c0d457cd688030b8184b0071f1291a036b6b023",
            )

    def test_rejects_g3_as_of_date_different_from_benchmark(self):
        broken = copy.deepcopy(self.source)
        broken[0]["config"]["as_of_date"] = "2011-01-01"
        with self.assertRaisesRegex(pipeline.PrecomputeError, "không khớp benchmark"):
            pipeline.build_precompute_records(
                broken, self.benchmark, self.ids, candidate_text, self.config,
                expected_corpus_sha256="7105c484061399010b0f087c6c0d457cd688030b8184b0071f1291a036b6b023",
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
