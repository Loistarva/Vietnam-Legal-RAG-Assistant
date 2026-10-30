import unittest
from importlib.metadata import PackageNotFoundError
from unittest.mock import patch

from retrieval.hybrid_retriever import ElasticsearchBM25Retriever, _segment_bm25_query


class FakeClient:
    def search(self, **kwargs):
        self.kwargs = kwargs
        return {"hits": {"hits": [
            {"_id": "chunk-56", "_score": 2.5,
             "_source": {
                 "chunk_id": "chunk-56",
                 "parent_id": "parent-56",
                 "document_id": "doc-56",
                 "doc_id": "doc-56",
                 "article_id": "article-56",
                 "clause_id": "clause-56",
                 "parent_clause_id": "clause-56",
                 "content": "Điều 56 ly hôn",
                 "metadata": {"article_ref": "Điều 56"},
             }},
            {"_id": "chunk-8", "_score": 0.8,
             "_source": {
                 "text": "Điều kiện kết hôn",
                 "parent_id": "parent-8",
                 "metadata": {},
             }},
        ]}}


class ElasticsearchBM25SearchTest(unittest.TestCase):
    def test_search_preserves_elasticsearch_order_score_and_chunk_fields(self):
        client = FakeClient()
        with patch("retrieval.hybrid_retriever._segment_bm25_query", return_value="Điều_56") as tokenize:
            hits = ElasticsearchBM25Retriever(client, "legal-child-chunks-dev").search(
                " Điều 56 ", 2, as_of_date="2026-10-30"
            )

        tokenize.assert_called_once_with("Điều 56")
        self.assertEqual([hit["chunk_id"] for hit in hits], ["chunk-56", "chunk-8"])
        self.assertEqual([hit["rank"] for hit in hits], [1, 2])
        self.assertEqual([hit["score"] for hit in hits], [2.5, 0.8])
        self.assertEqual(hits[0]["chunk_text"], "Điều 56 ly hôn")
        self.assertEqual(hits[1]["chunk_text"], "Điều kiện kết hôn")
        self.assertNotIn("text", hits[0])
        self.assertEqual(hits[0]["document_id"], "doc-56")
        self.assertEqual(hits[0]["article_id"], "article-56")
        self.assertEqual(hits[0]["clause_id"], "clause-56")
        self.assertEqual(hits[0]["parent_clause_id"], "clause-56")
        self.assertEqual(hits[0]["parent_id"], "parent-56")
        # Thiếu ID tường minh thì không suy diễn từ chunk_id hoặc parent_id.
        self.assertEqual(hits[1]["article_id"], "")
        self.assertEqual(hits[1]["clause_id"], "")
        self.assertEqual(hits[1]["parent_clause_id"], "")
        self.assertEqual(hits[1]["parent_id"], "parent-8")
        self.assertEqual(client.kwargs["index"], "legal-child-chunks-dev")

        bool_query = client.kwargs["query"]["bool"]
        self.assertEqual(bool_query["minimum_should_match"], 1)
        self.assertEqual(len(bool_query["should"]), 2)
        self.assertEqual(
            bool_query["should"][0]["multi_match"]["query"],
            "Điều 56",
        )
        self.assertEqual(
            bool_query["should"][0]["multi_match"]["fields"],
            ["content", "breadcrumb^1.5"],
        )
        self.assertEqual(
            bool_query["should"][1]["multi_match"]["query"],
            "Điều_56",
        )
        self.assertEqual(
            bool_query["should"][1]["multi_match"]["fields"],
            ["content_segmented"],
        )
        self.assertNotIn("must_not", bool_query)
        self.assertEqual(bool_query["filter"][0]["bool"]["should"][0],
                         {"range": {"effective_from": {"lte": "2026-10-30"}}})
        self.assertEqual(bool_query["filter"][1]["bool"]["should"][0],
                         {"range": {"effective_to": {"gt": "2026-10-30"}}})

    def test_query_tokenizer_fails_clearly_when_dependency_is_missing(self):
        with patch(
            "retrieval.hybrid_retriever.package_version",
            side_effect=PackageNotFoundError("underthesea"),
        ):
            with self.assertRaisesRegex(RuntimeError, "underthesea==9.5.0"):
                _segment_bm25_query("Điều kiện kết hôn")

    def test_query_tokenizer_rejects_version_that_does_not_match_corpus(self):
        with patch("retrieval.hybrid_retriever.package_version", return_value="9.4.0"):
            with self.assertRaisesRegex(RuntimeError, "không khớp corpus BM25"):
                _segment_bm25_query("Điều kiện kết hôn")


if __name__ == "__main__":
    unittest.main()
