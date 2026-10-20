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
    def __init__(self):
        self.indices = FakeIndices()
        self.closed = False

    def ping(self):
        return True

    def options(self, **kwargs):
        return self

    def count(self, index):
        return {"count": 321}

    def close(self):
        self.closed = True


class BM25RetrievalTest(unittest.TestCase):
    def test_chunk_loader_and_elasticsearch_document_use_segmented_content_field(self):
        fixture = ROOT / "embedding" / "data" / "han_gia_dinh_smoke_chunks.json"
        source_chunk = load_chunks(fixture)[0]
        document = load_es_chunks(fixture)[0]
        self.assertTrue(source_chunk["seg_text"])
        self.assertEqual(document["chunk_id"], source_chunk["chunk_id"])
        self.assertEqual(document["content"], source_chunk["text"])
        self.assertEqual(document["content_segmented"], source_chunk["seg_text"])
        self.assertEqual(document["metadata"], source_chunk["metadata"])

    def test_build_function_loads_chunks_creates_index_and_returns_stats(self):
        fixture = ROOT / "embedding" / "data" / "han_gia_dinh_smoke_chunks.json"
        client = FakeBuildClient()

        def fake_bulk(es_client, actions, **kwargs):
            self.assertIs(es_client, client)
            self.assertEqual(len(list(actions)), 321)
            return 321, []

        with patch("retrieval.build_bm25_index.helpers.bulk", side_effect=fake_bulk):
            stats = build_bm25_index(
                chunks_file=fixture,
                index_name="test-legal-chunks",
                client=client,
            )

        self.assertEqual(stats["input_chunks"], 321)
        self.assertEqual(stats["indexed"], 321)
        self.assertEqual(stats["index_count"], 321)
        self.assertEqual(stats["index_name"], "test-legal-chunks")
        self.assertEqual(client.indices.refreshed, "test-legal-chunks")
        self.assertFalse(client.closed)  # Injected client stays owned by caller.

    def test_search_uses_elasticsearch_bm25_and_returns_ranked_shared_chunk_shape(self):
        client = FakeElasticsearchClient([
            {"_id": "chunk-1", "_score": 3.2, "_source": {
                "chunk_id": "chunk-1", "content": "Nội dung luật", "parent_id": "parent-1",
                "metadata": {"article_ref": "Điều 56"},
            }},
        ])
        hits = ElasticsearchBM25Retriever(client, "legal-child-chunks-dev").search("Điều 56", 5)

        self.assertEqual(client.request["index"], "legal-child-chunks-dev")
        self.assertEqual(client.request["size"], 5)
        self.assertEqual(client.request["query"]["bool"]["must"][0]["multi_match"]["query"], "Điều 56")
        self.assertEqual(hits, [{
            "chunk_id": "chunk-1", "text": "Nội dung luật", "parent_id": "parent-1",
            "metadata": {"article_ref": "Điều 56"}, "score": 3.2, "rank": 1,
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
