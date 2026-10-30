"""Integration tests: Dev 4 HybridRetriever + Dev 5 Reranker/pipeline + CLI.

Branch stubs return the exact hit shapes of the real adapters
(ElasticsearchBM25Retriever and LegalVectorStore._format_hit), so the tests run
without Elasticsearch, Qdrant or a model.
"""
import contextlib
import copy
from datetime import date
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reranking.pipeline import (  # noqa: E402
    FixtureRetriever,
    PipelineError,
    RetrievalPipeline,
    load_retrieval_settings,
    to_contract_result,
)
from reranking.reranker import MockScorer, Reranker  # noqa: E402
from retrieval.hybrid_retriever import HybridRetriever, HybridSearchConfig  # noqa: E402
from scripts import run_retrieval  # noqa: E402

FIXTURE_PATH = ROOT / "test" / "fixtures" / "reranker_candidates.json"
FIXTURE = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
RETRIEVAL_SCHEMA = json.loads((ROOT / "schemas" / "retrieval_schema.json").read_text(encoding="utf-8"))
# The schema root is the envelope; each result is validated against RetrievalResultItem.
RESULT_SCHEMA = {"$ref": "#/$defs/RetrievalResultItem", "$defs": RETRIEVAL_SCHEMA["$defs"]}
CONTRACT_FIELDS = {"chunk_id", "document_id", "article_id", "clause_id", "parent_clause_id",
                   "rank", "score", "chunk_text", "metadata"}
QUERY = FIXTURE["query"]


def bm25_hit(chunk_id, rank, *, doc_id="l_52_2014_qh13", validity="Không xác định"):
    """Shape of ElasticsearchBM25Retriever.search rows."""
    article_id = chunk_id.rsplit("_chunk", 1)[0]
    clause_id = f"{article_id}_clause_1"
    return {"chunk_id": chunk_id, "document_id": doc_id, "article_id": article_id, "clause_id": clause_id,
            "parent_clause_id": clause_id, "chunk_text": f"BM25 text {chunk_id}", "text": f"BM25 text {chunk_id}",
            "parent_id": article_id,
            "metadata": {"doc_id": doc_id, "article_number": "8", "validity_status": validity},
            "score": 12.0 - rank, "rank": rank}


def dense_hit(chunk_id, rank, *, parent_clause_id):
    """Shape of LegalVectorStore._format_hit rows."""
    return {"chunk_id": chunk_id, "document_id": "l_52_2014_qh13",
            "article_id": chunk_id.split("_chunk")[0], "clause_id": parent_clause_id,
            "parent_clause_id": parent_clause_id, "rank": rank, "score": 0.9 - rank / 100,
            "chunk_text": f"Dense text {chunk_id}",
            "metadata": {"document_id": "l_52_2014_qh13", "article_number": "8",
                         "validity_status": "Không xác định"}}


class StubBranch:
    def __init__(self, hits=None, error=None):
        self.hits, self.error, self.calls = hits or [], error, []

    def search(self, query, top_k, *, as_of_date):
        self.calls.append((query, top_k, as_of_date))
        if self.error:
            raise self.error
        return copy.deepcopy(self.hits[:top_k])


def make_hybrid(bm25_hits, dense_hits, *, candidate_k=20, bm25_error=None, dense_error=None, reranker=None):
    bm25, dense = StubBranch(bm25_hits, bm25_error), StubBranch(dense_hits, dense_error)
    config = HybridSearchConfig(top_k=candidate_k, candidate_k=candidate_k, rrf_k=60)
    return HybridRetriever(bm25, dense, config, reranker=reranker), bm25, dense


BM25 = [bm25_hit("l_52_2014_qh13_art_8_chunk_2", 1), bm25_hit("l_52_2014_qh13_art_8_chunk_1", 2),
        bm25_hit("l_52_2014_qh13_art_9_chunk_1", 3)]
DENSE = [dense_hit("l_52_2014_qh13_art_8_chunk_1", 1, parent_clause_id="l_52_2014_qh13_art_8_clause_1"),
         dense_hit("l_52_2014_qh13_art_10_chunk_1", 2, parent_clause_id="l_52_2014_qh13_art_10_clause_1")]
SCORES = {"l_52_2014_qh13_art_10_chunk_1": 0.9, "l_52_2014_qh13_art_8_chunk_2": 0.8,
          "l_52_2014_qh13_art_9_chunk_1": 0.3, "l_52_2014_qh13_art_8_chunk_1": 0.1}


def assert_contract(test, output):
    # Validate entire pipeline output against RetrievalEnvelope schema (issue C7 resolved)
    jsonschema.validate(output, RETRIEVAL_SCHEMA)
    test.assertEqual([row["rank"] for row in output["results"]], list(range(1, len(output["results"]) + 1)))
    for row in output["results"]:
        jsonschema.validate(row, RESULT_SCHEMA)
        test.assertTrue(CONTRACT_FIELDS <= set(row), CONTRACT_FIELDS - set(row))
        test.assertNotIn("text", row, "chunk_text is the only content field")
        test.assertIn("validity_status", row["metadata"])


class HybridRerankerPipelineTest(unittest.TestCase):
    def run_pipeline(self, bm25_hits=BM25, dense_hits=DENSE, *, top_k=3, retrieval_top_k=20, scores=SCORES):
        hybrid, bm25, dense = make_hybrid(bm25_hits, dense_hits, candidate_k=retrieval_top_k)
        reranker = Reranker(MockScorer(scores), rerank_top_k=5, max_candidates=10, backend="mock")
        pipeline = RetrievalPipeline(hybrid, reranker, retrieval_top_k=retrieval_top_k)
        return pipeline.run(QUERY, top_k, query_id="Q_DEV_001"), bm25, dense

    def test_output_matches_shared_schema_and_reranker_order(self):
        output, _, _ = self.run_pipeline()
        assert_contract(self, output)
        self.assertEqual(output["query_id"], "Q_DEV_001")
        self.assertEqual(output["retriever"], "hybrid_mock_reranker")
        self.assertEqual([row["chunk_id"] for row in output["results"]], [
            "l_52_2014_qh13_art_10_chunk_1", "l_52_2014_qh13_art_8_chunk_2", "l_52_2014_qh13_art_9_chunk_1"])
        self.assertEqual([row["score"] for row in output["results"]], [0.9, 0.8, 0.3])

    def test_retriever_label_names_mock_scorer(self):
        hybrid, _, _ = make_hybrid(BM25, DENSE)
        for backend, label in (("mock", "hybrid_mock_reranker"), ("cross_encoder", "hybrid_reranker")):
            with self.subTest(backend=backend):
                reranker = Reranker(MockScorer(SCORES), backend=backend)
                self.assertEqual(RetrievalPipeline(hybrid, reranker).name, label)
        self.assertEqual(RetrievalPipeline(hybrid).name, "hybrid")

    def test_retrieval_top_k_sets_candidate_depth_of_both_branches(self):
        _, bm25, dense = self.run_pipeline(retrieval_top_k=7, top_k=2)
        self.assertEqual(bm25.calls, [(QUERY, 7, date.today().isoformat())])
        self.assertEqual(dense.calls, [(QUERY, 7, date.today().isoformat())])

    def test_metadata_and_ids_are_preserved_without_guessing(self):
        output, _, _ = self.run_pipeline(top_k=4)
        by_id = {row["chunk_id"]: row for row in output["results"]}
        both = by_id["l_52_2014_qh13_art_8_chunk_1"]
        self.assertEqual(both["parent_clause_id"], "l_52_2014_qh13_art_8_clause_1")
        self.assertEqual(both["retrieval_sources"], ["bm25", "dense"])
        bm25_only = by_id["l_52_2014_qh13_art_8_chunk_2"]
        self.assertEqual(bm25_only["document_id"], "l_52_2014_qh13")
        self.assertEqual(bm25_only["parent_clause_id"], "l_52_2014_qh13_art_8_clause_1")
        self.assertEqual(bm25_only["parent_id"], "l_52_2014_qh13_art_8", "parent_id is not parent_clause_id")
        self.assertEqual(bm25_only["chunk_text"], "BM25 text l_52_2014_qh13_art_8_chunk_2")
        for row in output["results"]:
            self.assertEqual(row["metadata"]["validity_status"], "Không xác định")
            self.assertIsInstance(row["source_ranks"]["retrieval"], int)
            self.assertIsInstance(row["source_scores"]["retrieval"], float)
            self.assertEqual(row["reranker_score"], row["score"])
            self.assertIn("rrf_score", row)

    def test_both_branches_empty_returns_empty_results(self):
        output, _, _ = self.run_pipeline([], [])
        self.assertEqual(output["results"], [])
        self.assertEqual(output["stats"]["retrieved_candidates"], 0)
        self.assertEqual(output["stats"]["returned"], 0)

    def test_one_empty_branch_still_reranks_the_other(self):
        output, _, _ = self.run_pipeline(BM25, [])
        assert_contract(self, output)
        self.assertEqual({row["chunk_id"] for row in output["results"]},
                         {"l_52_2014_qh13_art_8_chunk_2", "l_52_2014_qh13_art_9_chunk_1",
                          "l_52_2014_qh13_art_8_chunk_1"})

    def test_branch_adapter_error_propagates_as_retrieval_error(self):
        for kwargs in ({"bm25_error": ConnectionError("Elasticsearch down")},
                       {"dense_error": ConnectionError("Qdrant down")}):
            with self.subTest(**{k: str(v) for k, v in kwargs.items()}):
                hybrid, _, _ = make_hybrid(BM25, DENSE, **kwargs)
                pipeline = RetrievalPipeline(hybrid, Reranker(MockScorer()), retrieval_top_k=20)
                with self.assertRaises(PipelineError) as ctx:
                    pipeline.run(QUERY)
                self.assertEqual(ctx.exception.stage, "retrieval")
                self.assertIsInstance(ctx.exception.cause, ConnectionError)

    def test_reranker_error_propagates_as_rerank_error(self):
        class BrokenScorer:
            def score(self, query, hits):
                raise RuntimeError("CUDA out of memory")

        hybrid, _, _ = make_hybrid(BM25, DENSE)
        pipeline = RetrievalPipeline(hybrid, Reranker(BrokenScorer()), retrieval_top_k=20)
        with self.assertRaises(PipelineError) as ctx:
            pipeline.run(QUERY)
        self.assertEqual(ctx.exception.stage, "rerank")

    def test_malformed_adapter_output_is_reported(self):
        for hits in ([{"text": "no id", "score": 1.0}], [{"chunk_id": "A", "chunk_text": "x"}],
                     [{"chunk_id": "A", "score": 1, "metadata": "bad"}]):
            with self.subTest(hits=hits), self.assertRaises(PipelineError):
                RetrievalPipeline(FixtureRetriever(hits), Reranker(MockScorer())).run(QUERY)

        class NotAList:
            def search(self, query, top_k, *, as_of_date):
                return None

        with self.assertRaisesRegex(PipelineError, "phải trả list"):
            RetrievalPipeline(NotAList(), None).run(QUERY)

    def test_duplicates_from_retriever_are_removed_with_and_without_reranker(self):
        retriever = FixtureRetriever(FIXTURE["candidates"])
        for reranker in (Reranker(MockScorer(FIXTURE["mock_scores"])), None):
            with self.subTest(reranker=reranker):
                output = RetrievalPipeline(retriever, reranker).run(QUERY, 5)
                ids = [row["chunk_id"] for row in output["results"]]
                self.assertEqual(len(ids), len(set(ids)))
                self.assertEqual(output["stats"]["duplicates_removed"], 1)
                assert_contract(self, output)

    def test_without_reranker_keeps_hybrid_order(self):
        hybrid, _, _ = make_hybrid(BM25, DENSE)
        output = RetrievalPipeline(hybrid, None, retrieval_top_k=20).run(QUERY, 3)
        self.assertEqual(output["retriever"], "hybrid")
        self.assertEqual(output["results"][0]["chunk_id"], "l_52_2014_qh13_art_8_chunk_1")  # in both branches
        self.assertIsNone(output["config"]["reranker"])
        assert_contract(self, output)

    def test_reranker_plugs_into_hybrid_retriever_interface(self):
        reranker = Reranker(MockScorer(SCORES), rerank_top_k=2)
        hybrid, _, _ = make_hybrid(BM25, DENSE, reranker=reranker)
        results = hybrid.search(QUERY, top_k=2)
        self.assertEqual([row["chunk_id"] for row in results],
                         ["l_52_2014_qh13_art_10_chunk_1", "l_52_2014_qh13_art_8_chunk_2"])
        self.assertEqual([row["rank"] for row in results], [1, 2])

    def test_top_k_larger_than_candidate_pool_is_rejected(self):
        pipeline = RetrievalPipeline(FixtureRetriever([]), Reranker(MockScorer(), max_candidates=10),
                                     retrieval_top_k=20)
        with self.assertRaisesRegex(ValueError, "không được lớn hơn"):
            pipeline.run(QUERY, 11)
        with self.assertRaisesRegex(ValueError, "query"):
            pipeline.run("  ")

    def test_run_records_config_and_latency(self):
        output, _, _ = self.run_pipeline()
        self.assertEqual(output["config"]["reranker"], {"backend": "mock", "model": None,
                                                        "rerank_top_k": 5, "max_candidates": 10,
                                                        "candidate_text": "chunk_text"})
        self.assertEqual(output["config"]["retriever"]["retrieval_top_k"], 20)
        self.assertEqual(output["config"]["top_k"], 3)
        for key in ("retrieval_latency_ms", "rerank_latency_ms", "total_latency_ms"):
            self.assertGreaterEqual(output["stats"][key], 0.0)
        self.assertEqual(output["stats"]["input_candidates"], 4)
        self.assertEqual(output["stats"]["output_candidates"], 3)


class ContractMappingTest(unittest.TestCase):
    def test_rrf_row_maps_to_contract(self):
        row = to_contract_result({"chunk_id": "A", "text": "nội dung", "chunk_text": "nội dung",
                                  "metadata": {"doc_id": "d1"}, "rrf_score": 0.03, "rank": 1,
                                  "source_ranks": {"bm25": 1}, "retrieval_sources": ["bm25"]})
        self.assertEqual(row, {
            "chunk_id": "A", "document_id": "d1", "article_id": None, "clause_id": None,
            "parent_clause_id": None, "rank": 1, "score": 0.03, "chunk_text": "nội dung",
            "metadata": {"doc_id": "d1", "validity_status": "Không xác định"},
            "rrf_score": 0.03, "retrieval_sources": ["bm25"], "source_ranks": {"bm25": 1}})

    def test_top_level_validity_status_and_article_number_move_into_metadata(self):
        row = to_contract_result({"chunk_id": "A", "chunk_text": "x", "score": 1, "validity_status": "Còn hiệu lực",
                                  "article_number": "8", "metadata": {}})
        self.assertEqual(row["metadata"], {"validity_status": "Còn hiệu lực", "article_number": "8"})

    def test_pre_rerank_rank_and_score_move_to_source_fields(self):
        row = to_contract_result({"chunk_id": "A", "chunk_text": "x", "metadata": {}, "rank": 1, "score": 0.9,
                                  "source_ranks": {"bm25": 2}, "retrieval_rank": 4, "retrieval_score": 0.015})
        self.assertNotIn("retrieval_rank", row)
        self.assertNotIn("retrieval_score", row)
        self.assertEqual(row["source_ranks"], {"bm25": 2, "retrieval": 4})
        self.assertEqual(row["source_scores"], {"retrieval": 0.015})
        self.assertEqual(row["reranker_score"], 0.9)
        self.assertEqual(to_contract_result(row), row)

    def test_mapping_is_idempotent(self):
        row = to_contract_result(FIXTURE["candidates"][0])
        self.assertEqual(to_contract_result(row), row)


class RetrievalConfigTest(unittest.TestCase):
    def test_reads_repository_retrieval_config(self):
        settings = load_retrieval_settings()
        self.assertEqual(settings["retrieval_top_k"], 50)
        self.assertEqual(settings["rrf_k"], 60)

    def test_retrieval_top_k_key_takes_precedence_over_candidate_k(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            path.write_text("retrieval:\n  retrieval_top_k: 100\nhybrid:\n  candidate_k: 50\n  rrf_k: 10\n",
                            encoding="utf-8")
            settings = load_retrieval_settings(path)
        self.assertEqual((settings["retrieval_top_k"], settings["rrf_k"]), (100, 10))


class CliTest(unittest.TestCase):
    def run_cli(self, *args):
        # Offline runs pick the mock scorer explicitly; the configured default is the cross-encoder.
        if "--reranker" not in args:
            args = (*args, "--reranker", "mock")
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = run_retrieval.main([*args, "--log-level", "ERROR"])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_single_query_with_fixture_retriever_prints_contract_json(self):
        code, out, err = self.run_cli("--query", QUERY, "--top-k", "3", "--retriever", "fixture")
        self.assertEqual(code, 0, err)
        output = json.loads(out)
        assert_contract(self, output)
        self.assertEqual(output["retriever"], "fixture_mock_reranker")
        self.assertEqual(len(output["results"]), 3)
        self.assertEqual(output["results"][0]["chunk_id"], "l_52_2014_qh13_art_8_chunk_1")

    def test_reranker_none_and_overrides(self):
        code, out, err = self.run_cli("--query", QUERY, "--retriever", "fixture", "--reranker", "none",
                                      "--retrieval-top-k", "4", "--top-k", "2")
        self.assertEqual(code, 0, err)
        output = json.loads(out)
        self.assertEqual(output["retriever"], "fixture")
        self.assertEqual([row["chunk_id"] for row in output["results"]],
                         ["l_52_2014_qh13_art_9_chunk_1", "l_22_2000_qh10_art_9_chunk_1"])
        self.assertEqual(output["config"]["retriever"]["retrieval_top_k"], 4)

    def test_batch_queries_write_output_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            queries = Path(tmp) / "queries_dev.json"
            queries.write_text(json.dumps([{"id": "HN_001", "question": QUERY},
                                           {"id": "HN_002", "question": "Nam bao nhiêu tuổi được kết hôn?"}],
                                          ensure_ascii=False), encoding="utf-8")
            destination = Path(tmp) / "out" / "results.json"
            eval_destination = Path(tmp) / "out" / "eval.json"
            code, out, err = self.run_cli("--queries", str(queries), "--retriever", "fixture",
                                          "--output", str(destination), "--eval-output", str(eval_destination))
            self.assertEqual(code, 0, err)
            self.assertEqual(out, "")
            outputs = json.loads(destination.read_text(encoding="utf-8"))
            eval_rows = json.loads(eval_destination.read_text(encoding="utf-8"))
        self.assertEqual([row["query_id"] for row in outputs], ["HN_001", "HN_002"])
        self.assertEqual(eval_rows[0], {"query_id": "HN_001",
                                        "retrieved_chunk_ids": [row["chunk_id"] for row in outputs[0]["results"]]})
        for output in outputs:
            assert_contract(self, output)
            self.assertEqual(len(output["results"]), 5)

    def test_test_split_is_refused_unless_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            queries = Path(tmp) / "queries_test.json"
            queries.write_text(json.dumps([{"id": "HN_200", "question": QUERY}]), encoding="utf-8")
            code, _, err = self.run_cli("--queries", str(queries), "--retriever", "fixture")
            self.assertEqual(code, 2)
            self.assertIn("Test set", err)
            code, _, err = self.run_cli("--queries", str(queries), "--retriever", "fixture", "--allow-test-split")
            self.assertEqual(code, 0, err)

    def test_invalid_input_exits_with_code_2(self):
        for args in (["--query", "   "], ["--query", QUERY, "--top-k", "0"],
                     ["--query", QUERY, "--retrieval-top-k", "2", "--top-k", "3"],
                     ["--query", QUERY, "--candidates", "missing.json"]):
            with self.subTest(args=args):
                code, out, err = self.run_cli(*args, "--retriever", "fixture")
                self.assertEqual(code, 2, err)
                self.assertEqual(out, "")
                self.assertIn("ERROR", err)

    def test_defaults_are_hybrid_and_cross_encoder(self):
        args = run_retrieval.parse_args(["--query", QUERY])
        self.assertEqual(args.retriever, "hybrid")
        self.assertIsNone(args.reranker)
        self.assertEqual(run_retrieval.load_reranker_config(args.config).backend, "cross_encoder")

    def test_two_stage_run_matches_single_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            queries = Path(tmp) / "queries_dev.json"
            queries.write_text(json.dumps([{"id": "HN_001", "question": QUERY}], ensure_ascii=False),
                               encoding="utf-8")
            stage1, stage2, single = (Path(tmp) / name for name in ("candidates.json", "reranked.json", "single.json"))
            common = ("--queries", str(queries), "--no-parent-context", "--top-k", "3")
            code, _, err = self.run_cli("--queries", str(queries), "--retriever", "fixture", "--reranker", "none",
                                        "--no-parent-context", "--retrieval-top-k", "6", "--top-k", "5",
                                        "--output", str(stage1))
            self.assertEqual(code, 0, err)
            code, _, err = self.run_cli(*common, "--retriever", "precomputed", "--candidates", str(stage1),
                                        "--retrieval-top-k", "5", "--output", str(stage2))
            self.assertEqual(code, 0, err)
            code, _, err = self.run_cli(*common, "--retriever", "fixture", "--retrieval-top-k", "6",
                                        "--output", str(single))
            self.assertEqual(code, 0, err)
            reranked = json.loads(stage2.read_text(encoding="utf-8"))[0]
            expected = json.loads(single.read_text(encoding="utf-8"))[0]
        assert_contract(self, reranked)
        self.assertEqual(reranked["retriever"], "fixture_mock_reranker")
        self.assertEqual(reranked["config"]["retriever"]["candidates"], str(stage1))
        self.assertEqual([(row["chunk_id"], row["score"]) for row in reranked["results"]],
                         [(row["chunk_id"], row["score"]) for row in expected["results"]])

    def test_precomputed_candidates_are_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage1 = Path(tmp) / "candidates.json"
            code, _, err = self.run_cli("--query", QUERY, "--query-id", "HN_001", "--retriever", "fixture",
                                        "--no-parent-context", "--top-k", "3", "--output", str(stage1))
            self.assertEqual(code, 0, err)
            # Already reranked: rejected before any query runs.
            code, _, err = self.run_cli("--query", QUERY, "--retriever", "precomputed", "--candidates", str(stage1))
            self.assertEqual(code, 2)
            self.assertIn("--reranker none", err)
            code, _, err = self.run_cli("--query", QUERY, "--query-id", "HN_001", "--retriever", "fixture",
                                        "--reranker", "none", "--no-parent-context", "--top-k", "3",
                                        "--output", str(stage1))
            self.assertEqual(code, 0, err)
            for args, message in ((["--query-id", "HN_999"], "HN_999"),
                                  (["--query-id", "HN_001", "--retrieval-top-k", "5"], "--top-k 5")):
                with self.subTest(args=args):
                    code, _, err = self.run_cli("--query", QUERY, "--retriever", "precomputed",
                                                "--candidates", str(stage1), "--top-k", "2", *args)
                    self.assertEqual(code, 1)
                    self.assertIn(message, err)
            code, _, err = self.run_cli("--query", QUERY, "--retriever", "precomputed")
            self.assertEqual(code, 2)
            self.assertIn("--candidates", err)

    def test_hybrid_without_elasticsearch_url_fails_cleanly(self):
        code, out, err = self.run_cli("--query", QUERY, "--retriever", "hybrid", "--elasticsearch-url", "")
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("elasticsearch", err.lower())

    def test_mock_dense_retriever_runs_end_to_end_on_a_chunk_file(self):
        # Expired documents are filtered out by the retrievers (issue E1), so take in-force chunks only.
        corpus = [row for row in map(json.loads, filter(str.strip,
                  (ROOT / "data" / "chunking_output" / "chunks.jsonl").read_text(encoding="utf-8-sig").splitlines()))
                  if row["metadata"]["validity_status"] != "Hết hiệu lực"][:40]
        with tempfile.TemporaryDirectory() as tmp:
            chunks = Path(tmp) / "chunks.jsonl"
            chunks.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in corpus), encoding="utf-8")
            code, out, err = self.run_cli("--query", "điều kiện kết hôn", "--retriever", "mock", "--chunks", str(chunks),
                                          "--retrieval-top-k", "10", "--top-k", "3")
        self.assertEqual(code, 0, err)
        output = json.loads(out)
        assert_contract(self, output)
        self.assertEqual(output["retriever"], "mock_mock_reranker")
        self.assertEqual(len(output["results"]), 3)
        corpus_ids = {row["chunk_id"] for row in corpus}
        self.assertTrue({row["chunk_id"] for row in output["results"]} <= corpus_ids)


if __name__ == "__main__":
    unittest.main(verbosity=2)
