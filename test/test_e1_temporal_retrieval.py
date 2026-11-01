import unittest
from datetime import date
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from embedding.dense_retriever import DenseRetriever
from embedding.vector_store import LegalVectorStore, load_chunks, normalize_chunk_record
from evaluation.bm25_baseline import BM25Retriever
from retrieval.build_bm25_index import _validate_parent_links
from reranking.pipeline import RetrievalPipeline
from retrieval.hybrid_retriever import (
    ElasticsearchBM25Retriever,
    HybridRetriever,
    HybridSearchConfig,
    filter_legal_metadata,
)
from scripts.run_retrieval import parse_args


class TemporalBM25Stub:
    """BM25-shaped branch that applies the same date predicate as Elasticsearch."""

    def __init__(self, hits):
        self.hits = hits
        self.as_of_dates = []

    def search(self, query, top_k, *, as_of_date, exclude_expired=True):
        self.as_of_dates.append(as_of_date)
        if not exclude_expired:
            return [dict(hit) for hit in self.hits[:top_k]]
        return filter_legal_metadata(self.hits, as_of=date.fromisoformat(as_of_date))[:top_k]


class E1TemporalRetrievalEndToEndTest(unittest.TestCase):
    def test_dense_parent_id_matches_repository_parent_chunk_registry(self):
        root = Path(__file__).resolve().parents[1]
        chunks_path = root / "data" / "chunking_output" / "chunks.jsonl"
        parents_path = root / "data" / "chunking_output" / "parents.json"
        chunks = load_chunks(chunks_path)
        normalized = [normalize_chunk_record(chunk) for chunk in chunks]
        _validate_parent_links(chunks_path, normalized)
        parents = {
            row["parent_id"]: set(row["child_ids"])
            for row in json.loads(parents_path.read_text(encoding="utf-8-sig"))
        }
        as_of_date = "2026-10-30"
        chosen = next(
            row for row in normalized
            if row["effective_from"] and row["effective_from"] <= as_of_date
            and (row["effective_to"] is None or as_of_date < row["effective_to"])
        )
        vectors = [
            [1.0, 0.0] if row["chunk_id"] == chosen["chunk_id"] else [0.0, 1.0]
            for row in normalized
        ]
        store = LegalVectorStore(
            collection_name="e6-parent-contract-test",
            dimension=2,
            storage_path=":memory:",
            use_qdrant=True,
        )
        store.upsert_chunks(normalized, vectors)

        hits = store.search([1.0, 0.0], top_k=1, as_of_date=as_of_date)

        self.assertEqual(hits[0]["chunk_id"], chosen["chunk_id"])
        hit = hits[0]
        self.assertIn(hit["parent_id"], parents)
        self.assertIn(hit["chunk_id"], parents[hit["parent_id"]])
        self.assertEqual(hit["parent_id"], chosen["parent_id"])

    def test_qdrant_filters_before_top_k_and_dense_preserves_contract(self):
        records = [
            {
                "chunk_id": "future-nearest",
                "document_id": "doc-future",
                "article_id": "doc-future-art-1",
                "clause_id": "doc-future-art-1-clause-1",
                "parent_clause_id": "doc-future-art-1-clause-1",
                "parent_id": "doc-future-art-1",
                "chunk_text": "Chưa có hiệu lực",
                "embed_text": "chưa có hiệu lực",
                "effective_from": "2025-01-01",
                "validity_status": "Còn hiệu lực",
                "metadata": {},
            },
            {
                "chunk_id": "eligible-next",
                "document_id": "doc-current",
                "article_id": "doc-current-art-1",
                "clause_id": "doc-current-art-1-clause-1",
                "parent_clause_id": "doc-current-art-1-clause-1",
                "parent_id": "doc-current-art-1",
                "chunk_text": "Đang có hiệu lực",
                "embed_text": "đang có hiệu lực",
                "effective_from": "2020-01-01",
                "validity_status": "Còn hiệu lực",
                "metadata": {},
            },
        ]
        store = LegalVectorStore(
            collection_name="e1-prefilter-test",
            dimension=2,
            storage_path=":memory:",
            use_qdrant=True,
        )
        store.upsert_chunks(records, [[1.0, 0.0], [0.8, 0.6]])

        hits = store.search([1.0, 0.0], top_k=1, as_of_date="2024-01-01")

        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["chunk_id"], "eligible-next")
        for field in (
            "parent_id", "document_id", "article_id", "clause_id",
            "parent_clause_id", "effective_from", "effective_to",
        ):
            self.assertIn(field, hits[0])
        self.assertEqual(hits[0]["parent_id"], "doc-current-art-1")

    def test_expired_chunk_without_effective_to_is_rejected(self):
        record = {
            "chunk_id": "expired-without-end",
            "document_id": "doc-1",
            "article_id": "doc-1-art-1",
            "clause_id": "doc-1-art-1-clause-1",
            "parent_clause_id": "doc-1-art-1-clause-1",
            "parent_id": "doc-1-art-1",
            "chunk_text": "Văn bản hết hiệu lực",
            "embed_text": "văn bản hết hiệu lực",
            "validity_status": "Hết hiệu lực",
            "metadata": {},
        }
        with self.assertRaisesRegex(ValueError, "thiếu effective_to"):
            normalize_chunk_record(record)

    def test_historical_chunk_survives_hybrid_and_pipeline_only_at_historical_date(self):
        old = {
            "chunk_id": "old-law-chunk",
            "document_id": "old-law",
            "article_id": "old-law-art-1",
            "clause_id": "old-law-art-1-clause-1",
            "parent_clause_id": "old-law-art-1-clause-1",
            "parent_id": "old-law-parent-1",
            "chunk_text": "Quy định lịch sử về pháp luật.",
            "embed_text": "quy định lịch sử pháp luật",
            "embed_text_raw": "Quy định lịch sử về pháp luật.",
            "effective_from": "1987-01-03",
            "effective_to": "2001-01-01",
            "validity_status": "Hết hiệu lực",
            "metadata": {"validity_status": "Hết hiệu lực"},
        }
        current = {
            "chunk_id": "current-law-chunk",
            "document_id": "current-law",
            "article_id": "current-law-art-1",
            "clause_id": "current-law-art-1-clause-1",
            "parent_clause_id": "current-law-art-1-clause-1",
            "parent_id": "current-law-parent-1",
            "chunk_text": "Quy định hiện hành về pháp luật.",
            "embed_text": "quy định hiện hành pháp luật",
            "embed_text_raw": "Quy định hiện hành về pháp luật.",
            "effective_from": "2020-01-01",
            "effective_to": None,
            "validity_status": "Còn hiệu lực",
            "metadata": {"validity_status": "Còn hiệu lực"},
        }

        store = LegalVectorStore(
            collection_name="e1-temporal-test",
            dimension=64,
            storage_path=":memory:",
            use_qdrant=True,
        )
        dense = DenseRetriever(
            vector_store=store,
            use_mock=True,
            use_word_segmentation=False,
        )
        dense.index_chunks([old, current])
        sparse = TemporalBM25Stub([old, current])
        hybrid = HybridRetriever(
            sparse,
            dense,
            HybridSearchConfig(top_k=5, candidate_k=5),
        )
        pipeline = RetrievalPipeline(hybrid, retrieval_top_k=5)

        historical = pipeline.run("Quy định pháp luật lịch sử?", as_of_date="1995-06-01")
        current_result = pipeline.run("Quy định pháp luật lịch sử?", as_of_date="2026-10-30")

        historical_ids = {row["chunk_id"] for row in historical["results"]}
        current_ids = {row["chunk_id"] for row in current_result["results"]}
        self.assertIn("old-law-chunk", historical_ids)
        self.assertNotIn("old-law-chunk", current_ids)
        self.assertIn("current-law-chunk", current_ids)
        self.assertEqual(historical["config"]["as_of_date"], "1995-06-01")
        self.assertEqual(historical["config"]["temporal_filter"], "retriever")
        self.assertEqual(sparse.as_of_dates, ["1995-06-01", "2026-10-30"])

    def test_elasticsearch_bm25_retriever_build_temporal_filter(self):
        # 1. as_of_date given and exclude_expired=True
        clauses = ElasticsearchBM25Retriever.build_temporal_filter("2024-05-01", exclude_expired=True)
        self.assertEqual(len(clauses), 2)
        # Check range for effective_from
        from_should = clauses[0]["bool"]["should"]
        self.assertEqual(from_should[0]["range"]["effective_from"]["lte"], "2024-05-01")
        self.assertEqual(from_should[1]["bool"]["must_not"][0]["exists"]["field"], "effective_from")
        # Check range for effective_to
        to_should = clauses[1]["bool"]["should"]
        self.assertEqual(to_should[0]["range"]["effective_to"]["gt"], "2024-05-01")
        self.assertEqual(to_should[1]["bool"]["must_not"][0]["exists"]["field"], "effective_to")

        # 2. as_of_date given and exclude_expired=False (e.g. historical questions)
        no_filter = ElasticsearchBM25Retriever.build_temporal_filter("2024-05-01", exclude_expired=False)
        self.assertEqual(no_filter, [])

        # 3. as_of_date is None and exclude_expired=True
        default_filter = ElasticsearchBM25Retriever.build_temporal_filter(None, exclude_expired=True)
        self.assertEqual(len(default_filter), 1)
        self.assertIn("must_not", default_filter[0]["bool"])

        # 4. as_of_date is None and exclude_expired=False
        all_included = ElasticsearchBM25Retriever.build_temporal_filter(None, exclude_expired=False)
        self.assertEqual(all_included, [])

    @patch("evaluation.bm25_baseline.Elasticsearch")
    def test_bm25_retriever_search_with_temporal_filter(self, mock_es_cls):
        mock_client = MagicMock()
        mock_es_cls.return_value = mock_client
        mock_client.ping.return_value = True
        mock_client.indices.exists.return_value = True
        mock_client.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_id": "test_chunk_1",
                        "_score": 2.5,
                        "_source": {
                            "chunk_id": "test_chunk_1",
                            "content": "Nội dung điều kiện kết hôn",
                            "metadata": {
                                "doc_id": "l_52_2014_qh13",
                                "effective_from": "2015-01-01",
                                "effective_to": None,
                                "validity_status": "Còn hiệu lực",
                            },
                        },
                    }
                ]
            }
        }

        retriever = BM25Retriever(es_url="http://localhost:9200", index_name="test_index")
        results = retriever.search("kết hôn", top_k=3, as_of_date="2026-10-15", exclude_expired=True)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["chunk_id"], "test_chunk_1")
        self.assertEqual(results[0]["rank"], 1)

        # Verify ES query structure
        call_args = mock_client.search.call_args[1]
        self.assertEqual(call_args["size"], 3)
        query = call_args["query"]
        self.assertIn("bool", query)
        self.assertIn("filter", query["bool"])
        filters = query["bool"]["filter"]
        self.assertEqual(len(filters), 2)

    def test_hybrid_retriever_cache_distinguishes_as_of_date_and_exclude_expired(self):
        sparse = MagicMock()
        sparse.search.return_value = []
        dense = MagicMock()
        dense.search.return_value = []

        hybrid = HybridRetriever(sparse, dense, HybridSearchConfig(top_k=5, candidate_k=5))
        key1 = hybrid._make_cache_key("kết hôn", as_of_date="2024-01-01", exclude_expired=True, metadata_filter=None)
        key2 = hybrid._make_cache_key("kết hôn", as_of_date="2024-01-01", exclude_expired=False, metadata_filter=None)
        key3 = hybrid._make_cache_key("kết hôn", as_of_date="2026-01-01", exclude_expired=True, metadata_filter=None)
        key4 = hybrid._make_cache_key("kết hôn", as_of_date="2024-01-01", exclude_expired=True, metadata_filter={"doc_id": "doc1"})

        self.assertNotEqual(key1, key2)
        self.assertNotEqual(key1, key3)
        self.assertNotEqual(key1, key4)

    def test_cli_parse_args_exclude_expired(self):
        args_default = parse_args(["--query", "Điều kiện kết hôn"])
        self.assertTrue(args_default.exclude_expired)

        args_disabled = parse_args(["--query", "Điều kiện kết hôn", "--no-exclude-expired"])
        self.assertFalse(args_disabled.exclude_expired)

        args_explicit = parse_args(["--query", "Điều kiện kết hôn", "--exclude-expired"])
        self.assertTrue(args_explicit.exclude_expired)


if __name__ == "__main__":
    unittest.main()
