import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from retrieval.bm25_retriever import BM25Index


class BM25RetrievalTest(unittest.TestCase):
    def setUp(self):
        self.chunks = [
            {"chunk_id": "law_art_56", "text": "Điều 56 ly hôn đơn phương khi hôn nhân trầm trọng.",
             "metadata": {"document_id": "law", "article_number": "56"}},
            {"chunk_id": "law_art_55", "text": "Thuận tình ly hôn do hai bên tự nguyện.",
             "metadata": {"document_id": "law", "article_number": "55"}},
            {"chunk_id": "law_art_8", "text": "Điều kiện kết hôn về độ tuổi.",
             "metadata": {"document_id": "law", "article_number": "8"}},
        ]
        self.index = BM25Index(self.chunks)

    def test_search_returns_ranked_shared_chunk_shape_and_top_k(self):
        results = self.index.search("Điều kiện ly hôn đơn phương Điều 56", top_k=1)
        self.assertEqual(len(results), 1)
        hit = results[0]
        self.assertEqual(hit["chunk_id"], "law_art_56")
        self.assertEqual(hit["rank"], 1)
        self.assertGreater(hit["score"], 0)
        self.assertEqual(hit["metadata"], {"document_id": "law", "article_number": "56"})
        self.assertIn("text", hit)

    def test_empty_match_and_invalid_top_k(self):
        self.assertEqual(self.index.search("từ khóa không có"), [])
        with self.assertRaises(ValueError):
            self.index.search("ly hôn", top_k=0)

    def test_rejects_empty_chunks_invalid_chunk_and_duplicate_id(self):
        with self.assertRaises(ValueError):
            BM25Index([])
        with self.assertRaises(ValueError):
            BM25Index([{"chunk_id": "missing_text", "metadata": {}}])
        with self.assertRaises(ValueError):
            BM25Index([self.chunks[0], self.chunks[0]])

    def test_rejects_invalid_queries_and_top_k_types(self):
        for query in ("", "   ", None):
            with self.subTest(query=query), self.assertRaises(ValueError):
                self.index.search(query)
        for top_k in (0, -1, 1.5, True):
            with self.subTest(top_k=top_k), self.assertRaises(ValueError):
                self.index.search("ly hôn", top_k=top_k)

    def test_results_are_score_ordered_and_do_not_include_zero_scores(self):
        results = self.index.search("ly hôn")
        self.assertGreater(len(results), 0)
        self.assertEqual(
            [hit["score"] for hit in results],
            sorted((hit["score"] for hit in results), reverse=True),
        )
        self.assertTrue(all(hit["score"] > 0 for hit in results))
        self.assertEqual(
            [hit["rank"] for hit in results],
            list(range(1, len(results) + 1)),
        )

    def test_loads_normalized_fixture_and_returns_shared_result_shape(self):
        fixture = (
            ROOT
            / "embedding"
            / "data"
            / "han_gia_dinh_smoke_chunks.json"
        )
        index = BM25Index.from_file(str(fixture))
        results = index.search("ly hôn đơn phương", top_k=3)

        self.assertEqual(index.document_count, 321)
        self.assertEqual(len(results), 3)
        for hit in results:
            with self.subTest(chunk_id=hit["chunk_id"]):
                self.assertEqual(
                    set(hit), {"rank", "score", "chunk_id", "text", "metadata"}
                )
                self.assertIsInstance(hit["metadata"], dict)
                self.assertGreater(hit["score"], 0)

    def test_exact_article_reference_ranks_matching_article_first(self):
        fixture = (
            ROOT
            / "embedding"
            / "data"
            / "han_gia_dinh_smoke_chunks.json"
        )
        index = BM25Index.from_file(str(fixture))

        first_hit = index.search("Điều 56", top_k=1)[0]
        self.assertEqual(first_hit["metadata"]["article_ref"], "Điều 56")


if __name__ == "__main__":
    unittest.main(verbosity=2)
