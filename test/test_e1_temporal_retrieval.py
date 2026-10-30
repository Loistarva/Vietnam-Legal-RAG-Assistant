import unittest
from datetime import date
import json
from pathlib import Path

from embedding.dense_retriever import DenseRetriever
from embedding.vector_store import LegalVectorStore, load_chunks, normalize_chunk_record
from retrieval.build_bm25_index import _validate_parent_links
from reranking.pipeline import RetrievalPipeline
from retrieval.hybrid_retriever import HybridRetriever, HybridSearchConfig, filter_legal_metadata


class TemporalBM25Stub:
    """BM25-shaped branch that applies the same date predicate as Elasticsearch."""

    def __init__(self, hits):
        self.hits = hits
        self.as_of_dates = []

    def search(self, query, top_k, *, as_of_date):
        self.as_of_dates.append(as_of_date)
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


if __name__ == "__main__":
    unittest.main()
