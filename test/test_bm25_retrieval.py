import unittest
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from retrieval.hybrid_retriever import ElasticsearchBM25Retriever
from retrieval.build_bm25_index import build_bm25_index, load_chunks as load_es_chunks
from embedding.vector_store import load_chunks


class FakeElasticsearchClient:
    def __init__(self, hits):
        self.hits = hits
        self.request = None

    def search(self, **kwargs):
        self.request = kwargs
        return {"hits": {"hits": self.hits}}


class FakeIndices:
    def __init__(self):
        self.created = None
        self.refreshed = None

    def exists(self, index):
        return False

    def create(self, **kwargs):
        self.created = kwargs

    def refresh(self, index):
        self.refreshed = index


class FakeBuildClient:
    def __init__(self, document_count: int):
        self.indices = FakeIndices()
        self.document_count = document_count
        self.closed = False

    def ping(self):
        return True

    def options(self, **kwargs):
        return self

    def count(self, index):
        return {"count": self.document_count}

    def close(self):
        self.closed = True


class BM25RetrievalTest(unittest.TestCase):
    def test_chunk_loader_and_elasticsearch_document_use_segmented_content_field(self):
        fixture = ROOT / "data" / "chunking_output" / "chunks.jsonl"
        source_chunk = load_chunks(fixture)[0]
        document = load_es_chunks(fixture)[0]
        self.assertTrue(source_chunk["seg_text"])
        self.assertEqual(document["chunk_id"], source_chunk["chunk_id"])
        self.assertEqual(document["parent_id"], source_chunk["parent_id"])
        self.assertEqual(document["document_id"], source_chunk["document_id"])
        self.assertEqual(document["doc_id"], source_chunk["doc_id"])
        self.assertEqual(document["article_id"], source_chunk["article_id"])
        self.assertEqual(document["clause_id"], source_chunk["clause_id"])
        self.assertEqual(document["parent_clause_id"], source_chunk["parent_clause_id"])
        self.assertEqual(document["content"], source_chunk["text"])
        self.assertEqual(document["content_segmented"], source_chunk["seg_text"])
        self.assertEqual(document["metadata"], source_chunk["metadata"])

    def test_build_function_loads_chunks_creates_index_and_returns_stats(self):
        fixture = ROOT / "data" / "chunking_output" / "chunks.jsonl"
        expected = len(load_chunks(fixture))
        client = FakeBuildClient(expected)

        def fake_bulk(es_client, actions, **kwargs):
            self.assertIs(es_client, client)
            self.assertEqual(len(list(actions)), expected)
            return expected, []

        with patch("retrieval.build_bm25_index.helpers.bulk", side_effect=fake_bulk):
            stats = build_bm25_index(
                chunks_file=fixture,
                index_name="test-legal-chunks",
                client=client,
            )

        self.assertEqual(stats["input_chunks"], expected)
        self.assertEqual(stats["indexed"], expected)
        self.assertEqual(stats["index_count"], expected)
        self.assertEqual(stats["index_name"], "test-legal-chunks")
        self.assertEqual(client.indices.refreshed, "test-legal-chunks")
        properties = client.indices.created["mappings"]["properties"]
        for field in ("parent_id", "doc_id", "document_id", "article_id", "clause_id", "parent_clause_id"):
            with self.subTest(field=field):
                self.assertEqual(properties[field]["type"], "keyword")
        self.assertEqual(properties["effective_from"]["type"], "date")
        self.assertEqual(properties["effective_to"]["type"], "date")
        self.assertFalse(client.closed)  # Injected client stays owned by caller.

    def test_build_fails_when_bulk_index_reports_errors_or_missing_documents(self):
        fixture = ROOT / "data" / "chunking_output" / "chunks.jsonl"
        expected = len(load_chunks(fixture))
        client = FakeBuildClient(expected)

        def failed_bulk(es_client, actions, **kwargs):
            self.assertIs(es_client, client)
            list(actions)
            return expected - 1, [{"index": {"error": "simulated bulk failure"}}]

        with patch("retrieval.build_bm25_index.helpers.bulk", side_effect=failed_bulk):
            with self.assertRaisesRegex(RuntimeError, "errors=1"):
                build_bm25_index(
                    chunks_file=fixture,
                    index_name="test-legal-chunks",
                    client=client,
                )

    def test_search_uses_elasticsearch_bm25_and_returns_ranked_shared_chunk_shape(self):
        client = FakeElasticsearchClient([
            {"_id": "chunk-1", "_score": 3.2, "_source": {
                "chunk_id": "chunk-1", "content": "Nội dung luật",
                "parent_id": "article-1", "doc_id": "doc-1", "document_id": "doc-1",
                "article_id": "article-1", "clause_id": "clause-1", "parent_clause_id": "clause-1",
                "metadata": {"article_ref": "Điều 56"},
            }},
        ])
        hits = ElasticsearchBM25Retriever(client, "legal-child-chunks-dev").search("Điều 56", 5)

        self.assertEqual(client.request["index"], "legal-child-chunks-dev")
        self.assertEqual(client.request["size"], 5)
        bool_query = client.request["query"]["bool"]
        self.assertEqual(bool_query["minimum_should_match"], 1)
        self.assertEqual(bool_query["should"][0]["multi_match"]["query"], "Điều 56")
        self.assertEqual(bool_query["should"][1]["multi_match"]["fields"], ["content_segmented"])
        self.assertEqual(hits, [{
            "chunk_id": "chunk-1",
            "document_id": "doc-1",
            "article_id": "article-1",
            "clause_id": "clause-1",
            "parent_clause_id": "clause-1",
            "rank": 1,
            "score": 3.2,
            "chunk_text": "Nội dung luật",
            "parent_id": "article-1",
            "effective_from": None,
            "effective_to": None,
            "metadata": {"article_ref": "Điều 56"},
        }])

    def test_search_returns_empty_list_when_elasticsearch_has_no_hits(self):
        client = FakeElasticsearchClient([])
        self.assertEqual(ElasticsearchBM25Retriever(client, "idx").search("không có", 10), [])

    def test_search_rejects_empty_query_and_invalid_top_k(self):
        retriever = ElasticsearchBM25Retriever(FakeElasticsearchClient([]), "idx")
        with self.assertRaises(ValueError):
            retriever.search("  ", 10)
        with self.assertRaises(ValueError):
            retriever.search("luật", 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
