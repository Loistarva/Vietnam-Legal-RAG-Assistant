import unittest

from retrieval.hybrid_retriever import HybridRetriever, HybridSearchConfig


def hit(chunk_id, score=1.0):
    return {"chunk_id": chunk_id, "text": f"text for {chunk_id}",
            "metadata": {"chunk": chunk_id}, "score": score}


class StubRetriever:
    def __init__(self, results=None, error=None):
        self.results = results or []
        self.error = error
        self.calls = []

    def search(self, query, top_k):
        self.calls.append((query, top_k))
        if self.error:
            raise self.error
        return self.results[:top_k]


class HybridBranchBehaviorTest(unittest.TestCase):
    def create_hybrid(self, bm25_hits, dense_hits, *, bm25_error=None, dense_error=None):
        bm25 = StubRetriever(bm25_hits, bm25_error)
        dense = StubRetriever(dense_hits, dense_error)
        hybrid = HybridRetriever(
            bm25,
            dense,
            HybridSearchConfig(top_k=5, candidate_k=10, rrf_k=60),
        )
        return hybrid, bm25, dense

    def test_bm25_results_are_kept_when_dense_is_empty(self):
        hybrid, _, _ = self.create_hybrid([hit("A"), hit("B")], [])
        results = hybrid.search("query", top_k=5)
        self.assertEqual({row["chunk_id"] for row in results}, {"A", "B"})
        self.assertTrue(all(row["source_ranks"].get("bm25") for row in results))

    def test_dense_results_are_kept_when_bm25_is_empty(self):
        hybrid, _, _ = self.create_hybrid([], [hit("D"), hit("E")])
        results = hybrid.search("query", top_k=5)
        self.assertEqual({row["chunk_id"] for row in results}, {"D", "E"})
        self.assertTrue(all(row["source_ranks"].get("dense") for row in results))

    def test_both_empty_branches_return_empty_list(self):
        hybrid, _, _ = self.create_hybrid([], [])
        self.assertEqual(hybrid.search("query", top_k=5), [])

    def test_shared_chunk_id_is_fused_once_with_both_rank_contributions(self):
        hybrid, _, _ = self.create_hybrid([hit("A"), hit("B")], [hit("B"), hit("C")])
        results = hybrid.search("query", top_k=5)
        by_id = {row["chunk_id"]: row for row in results}
        self.assertEqual(len(results), 3)
        self.assertAlmostEqual(by_id["B"]["rrf_score"], 1 / 62 + 1 / 61)
        self.assertEqual(by_id["B"]["source_ranks"], {"bm25": 2, "dense": 1})

    def test_dense_branch_error_propagates_instead_of_becoming_empty_results(self):
        hybrid, _, _ = self.create_hybrid([hit("A")], [], dense_error=ConnectionError("dense offline"))
        with self.assertRaisesRegex(ConnectionError, "dense offline"):
            hybrid.search("query", top_k=5)

    def test_bm25_branch_error_propagates_instead_of_becoming_empty_results(self):
        hybrid, _, _ = self.create_hybrid([], [hit("D")], bm25_error=RuntimeError("BM25 index failed"))
        with self.assertRaisesRegex(RuntimeError, "BM25 index failed"):
            hybrid.search("query", top_k=5)


if __name__ == "__main__":
    unittest.main()
