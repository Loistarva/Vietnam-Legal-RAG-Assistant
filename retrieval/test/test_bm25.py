import unittest

from retrieval.hybrid_retriever import ElasticsearchBM25Retriever


class FakeClient:
    def search(self, **kwargs):
        self.kwargs = kwargs
        return {"hits": {"hits": [
            {"_id": "chunk-56", "_score": 2.5,
             "_source": {"content": "Điều 56 ly hôn", "metadata": {"article_ref": "Điều 56"}}},
            {"_id": "chunk-8", "_score": 0.8,
             "_source": {"text": "Điều kiện kết hôn", "metadata": {}}},
        ]}}


class ElasticsearchBM25SearchTest(unittest.TestCase):
    def test_search_preserves_elasticsearch_order_score_and_chunk_fields(self):
        client = FakeClient()
        hits = ElasticsearchBM25Retriever(client, "legal-child-chunks-dev").search("Điều 56", 2)

        self.assertEqual([hit["chunk_id"] for hit in hits], ["chunk-56", "chunk-8"])
        self.assertEqual([hit["rank"] for hit in hits], [1, 2])
        self.assertEqual([hit["score"] for hit in hits], [2.5, 0.8])
        self.assertEqual(hits[0]["text"], "Điều 56 ly hôn")
        self.assertEqual(hits[1]["text"], "Điều kiện kết hôn")
        self.assertEqual(client.kwargs["index"], "legal-child-chunks-dev")


if __name__ == "__main__":
    unittest.main()
