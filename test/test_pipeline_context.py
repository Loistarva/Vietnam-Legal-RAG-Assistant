"""Parent-Context Resolver, as_of_date plumbing, reranker text mode and mock warnings (Dev 5)."""
import contextlib
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

from reranking.parent_context import ParentContextResolver, load_parent_context_config  # noqa: E402
from reranking.pipeline import FixtureRetriever, RetrievalPipeline  # noqa: E402
from reranking.reranker import MockScorer, RerankerConfig, candidate_text  # noqa: E402
from scripts import run_retrieval  # noqa: E402

SCHEMA = json.loads((ROOT / "schemas" / "retrieval_schema.json").read_text(encoding="utf-8"))
QUERY = "Điều kiện kết hôn là gì?"


def candidate(chunk_id, score, *, parent_id=None):
    row = {"chunk_id": chunk_id, "document_id": "l_52_2014_qh13", "article_id": "l_52_2014_qh13_art_8",
           "clause_id": "l_52_2014_qh13_art_8_clause_1", "parent_clause_id": "l_52_2014_qh13_art_8_clause_1",
           "chunk_text": f"Nội dung {chunk_id}", "score": score,
           "metadata": {"validity_status": "Còn hiệu lực", "article_number": "8",
                        "breadcrumb": "Chương II > Điều 8 > Khoản 1"}}
    if parent_id:
        row["parent_id"] = parent_id
    return row


PARENTS = [
    {"parent_id": "p8", "text": "Điều 8 " + "x" * 40, "child_ids": ["c1", "c2"]},
    {"parent_id": "p9", "text": "Điều 9 " + "y" * 40, "child_ids": ["c3"]},
]


class ParentContextResolverTest(unittest.TestCase):
    def test_best_ranked_child_carries_parent_and_budget_is_respected(self):
        resolver = ParentContextResolver(PARENTS, max_context_chars=60)
        rows = resolver.resolve([candidate("c1", 3), candidate("c2", 2), candidate("c3", 1), candidate("cx", 0)])
        self.assertEqual([r["parent_id"] for r in rows], ["p8", "p8", "p9", None])
        self.assertEqual(rows[0]["parent_text"], PARENTS[0]["text"])
        self.assertIsNone(rows[1]["parent_text"], "second child of p8 shares the parent")
        self.assertIsNone(rows[2]["parent_text"], "p9 would exceed max_context_chars")
        self.assertEqual(resolver.last_stats, {"parents_attached": 1, "parents_shared": 1, "parents_missing": 1,
                                               "parents_over_budget": 1, "upstream_parent_id_replaced": 0,
                                               "context_chars": len(PARENTS[0]["text"])})
        self.assertEqual([r["chunk_id"] for r in rows], ["c1", "c2", "c3", "cx"])

    def test_parents_file_wins_over_a_clause_id_in_upstream_parent_id(self):
        resolver = ParentContextResolver(PARENTS)
        rows = resolver.resolve([candidate("c1", 1, parent_id="l_52_2014_qh13_art_8_clause_1")])
        self.assertEqual(rows[0]["parent_id"], "p8")
        self.assertEqual(rows[0]["parent_text"], PARENTS[0]["text"])
        self.assertEqual(resolver.last_stats["upstream_parent_id_replaced"], 1)

    def test_pipeline_output_with_parent_context_matches_schema(self):
        resolver = ParentContextResolver(PARENTS)
        pipeline = RetrievalPipeline(FixtureRetriever([candidate("c1", 2), candidate("c3", 1)]),
                                     retrieval_top_k=5, parent_resolver=resolver)
        output = pipeline.run(QUERY, 2, query_id="HN_001")
        jsonschema.validate(output, SCHEMA)
        self.assertEqual([r["parent_id"] for r in output["results"]], ["p8", "p9"])
        self.assertEqual(output["stats"]["parent_context"]["parents_attached"], 2)
        self.assertEqual(output["config"]["parent_context"]["max_context_chars"], resolver.max_context_chars)

    def test_repo_parents_cover_every_corpus_chunk(self):
        resolver = ParentContextResolver.from_config(load_parent_context_config(ROOT / "reranking" / "config.yaml"))
        chunk_ids = [json.loads(line)["chunk_id"]
                     for line in (ROOT / "data" / "chunking_output" / "chunks.jsonl").read_text(encoding="utf-8").splitlines()
                     if line.strip()]
        self.assertEqual([c for c in chunk_ids if c not in resolver.child_to_parent], [])

    def test_unknown_config_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            path.write_text("parent_context:\n  max_chars: 10\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "max_chars"):
                load_parent_context_config(path)


class AsOfDateTest(unittest.TestCase):
    def test_as_of_date_reaches_a_retriever_that_accepts_it(self):
        class TemporalRetriever:
            def search(self, query, top_k, *, as_of_date=None):
                self.as_of_date = as_of_date
                return [candidate("c1", 1)]

        retriever = TemporalRetriever()
        output = RetrievalPipeline(retriever, retrieval_top_k=5).run(QUERY, 1, as_of_date="2016-01-01")
        self.assertEqual(retriever.as_of_date, "2016-01-01")
        self.assertEqual(output["config"]["as_of_date"], "2016-01-01")
        self.assertEqual(output["config"]["temporal_filter"], "retriever")

    def test_retriever_without_temporal_filter_is_reported(self):
        pipeline = RetrievalPipeline(FixtureRetriever([candidate("c1", 1)]), retrieval_top_k=5)
        with self.assertLogs("reranking.pipeline", "WARNING"):
            output = pipeline.run(QUERY, 1, as_of_date="2016-01-01")
        self.assertEqual(output["config"]["temporal_filter"], "not_supported_by_retriever")
        self.assertIsNone(pipeline.run(QUERY, 1)["config"]["temporal_filter"])
        with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
            pipeline.run(QUERY, 1, as_of_date="01/01/2016")

    def test_cli_reads_as_of_date_per_question(self):
        with tempfile.TemporaryDirectory() as tmp:
            queries = Path(tmp) / "queries_dev.json"
            queries.write_text(json.dumps([{"id": "HN_001", "question": QUERY, "as_of_date": "2014-06-01"},
                                           {"id": "HN_002", "question": QUERY}], ensure_ascii=False),
                               encoding="utf-8")
            destination = Path(tmp) / "out.json"
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = run_retrieval.main(["--queries", str(queries), "--retriever", "fixture",
                                           "--as-of-date", "2026-10-25", "--no-parent-context",
                                           "--output", str(destination), "--log-level", "ERROR"])
            self.assertEqual(code, 0, stderr.getvalue())
            outputs = json.loads(destination.read_text(encoding="utf-8"))
        self.assertEqual([o["config"]["as_of_date"] for o in outputs], ["2014-06-01", "2026-10-25"])
        self.assertTrue(all(o["config"]["parent_context"] is None for o in outputs))


class RerankerTextModeAndMockWarningTest(unittest.TestCase):
    def test_breadcrumb_mode_prefixes_breadcrumb(self):
        hit = candidate("c1", 1)
        self.assertEqual(candidate_text(hit), "Nội dung c1")
        self.assertEqual(candidate_text(hit, "breadcrumb_chunk_text"), "Chương II > Điều 8 > Khoản 1\nNội dung c1")
        self.assertEqual(MockScorer(text_mode="breadcrumb_chunk_text").score("Điều 8", [hit]), [1.0])
        with self.assertRaisesRegex(ValueError, "candidate_text"):
            RerankerConfig(candidate_text="title")

    def test_cli_warns_when_running_on_mock_components(self):
        with self.assertLogs("run_retrieval", "WARNING") as logs:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = run_retrieval.main(["--query", QUERY, "--retriever", "fixture", "--log-level", "ERROR"])
        self.assertEqual(code, 0)
        self.assertTrue(any("fixture" in line for line in logs.output))
        self.assertTrue(any("mock" in line for line in logs.output))


if __name__ == "__main__":
    unittest.main()
