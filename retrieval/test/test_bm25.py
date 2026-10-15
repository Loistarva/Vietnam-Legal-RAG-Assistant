import unittest

from retrieval.bm25_retriever import BM25Index


class BM25SearchTest(unittest.TestCase):
    def setUp(self):
        self.index = BM25Index([
            {"chunk_id": "art_56_chunk_1", "text": "Ly hôn đơn phương khi hôn nhân trầm trọng.",
             "metadata": {"article_ref": "Điều 56"}},
            {"chunk_id": "art_8_chunk_1", "text": "Điều kiện kết hôn về độ tuổi.",
             "metadata": {"article_ref": "Điều 8"}},
        ])

    def test_bm25_returns_ranked_chunk_id_and_shared_payload(self):
        hits = self.index.search("ly hôn đơn phương", top_k=2)
        self.assertTrue(hits)
        self.assertEqual(hits[0]["chunk_id"], "art_56_chunk_1")
        self.assertEqual(hits[0]["rank"], 1)
        self.assertGreater(hits[0]["score"], 0)
        self.assertIsInstance(hits[0]["text"], str)
        self.assertIsInstance(hits[0]["metadata"], dict)

    def test_unmatched_query_returns_empty_list(self):
        self.assertEqual(self.index.search("xyz-no-match"), [])


if __name__ == "__main__":
    unittest.main()
