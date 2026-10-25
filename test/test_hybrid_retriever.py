import unittest

from retrieval.hybrid_retriever import (
    EmbeddingQdrantAdapter,
    ElasticsearchBM25Retriever,
    HybridRetriever,
    HybridSearchConfig,
    hybrid_search,
    reciprocal_rank_fusion,
)


def hit(chunk_id, text=None, score=1.0):
    return {"chunk_id": chunk_id, "text": text or f"text {chunk_id}",
            "metadata": {"article_number": chunk_id}, "score": score}


class HybridRetrieverTest(unittest.TestCase):
    def test_elasticsearch_bm25_adapter_uses_match_and_returns_shared_chunk_shape(self):
        class ElasticsearchStub:
            def search(self, **kwargs):
                self.kwargs = kwargs
                return {"hits": {"hits": [
                    {"_id": "chunk-a", "_score": 3.7, "_source": {
                        "chunk_id": "chunk-a", "text": "kết quả", "metadata": {"article_ref": "Điều 5"}}},
                ]}}

        client = ElasticsearchStub()
        results = ElasticsearchBM25Retriever(client, "legal-chunks").search("Điều 5", top_k=4)
        self.assertEqual(client.kwargs["index"], "legal-chunks")
        self.assertEqual(client.kwargs["size"], 4)
        multi_match = client.kwargs["query"]["bool"]["must"][0]["multi_match"]
        self.assertEqual(multi_match["query"], "Điều 5")
        self.assertEqual(multi_match["fields"], ["content_segmented", "breadcrumb^1.5"])
        self.assertEqual(results, [{
            "chunk_id": "chunk-a",
            "document_id": "",
            "article_id": "",
            "clause_id": "",
            "parent_clause_id": "",
            "rank": 1,
            "score": 3.7,
            "chunk_text": "kết quả",
            "text": "kết quả",
            "parent_id": None,
            "metadata": {"article_ref": "Điều 5"},
        }])

    def test_rrf_combines_overlap_and_preserves_single_branch_results(self):
        bm25 = [hit("A", score=9), hit("C", score=7)]
        dense = [hit("B", score=0.9), hit("A", score=0.8)]
        results = reciprocal_rank_fusion([bm25, dense], top_k=5, rrf_k=60)
        by_id = {row["chunk_id"]: row for row in results}

        self.assertEqual(set(by_id), {"A", "B", "C"})
        self.assertAlmostEqual(by_id["A"]["rrf_score"], 1 / 61 + 1 / 62)
        self.assertAlmostEqual(by_id["B"]["rrf_score"], 1 / 61)
        self.assertAlmostEqual(by_id["C"]["rrf_score"], 1 / 62)
        self.assertEqual(by_id["A"]["source_ranks"], {"bm25": 1, "dense": 2})
        self.assertEqual(by_id["B"]["retrieval_sources"], ["dense"])
        self.assertEqual([row["rank"] for row in results], [1, 2, 3])

    def test_duplicate_ids_within_a_branch_are_returned_once(self):
        results = reciprocal_rank_fusion(
            [[hit("A"), hit("A"), hit("B")], [hit("A"), hit("A"), hit("C")]],
            top_k=10,
            rrf_k=60,
        )
        self.assertEqual([row["chunk_id"] for row in results].count("A"), 1)
        # Rank contribution uses the first occurrence in each branch only.
        a = next(row for row in results if row["chunk_id"] == "A")
        self.assertEqual(a["source_ranks"], {"bm25": 1, "dense": 1})
        self.assertAlmostEqual(a["rrf_score"], 2 / 61)

    def test_empty_result_list_combinations(self):
        cases = [
            ([[hit("A")], [hit("B")]], {"A", "B"}),
            ([[hit("A")], []], {"A"}),
            ([[], [hit("B")]], {"B"}),
            ([[], []], set()),
        ]
        for result_lists, expected_ids in cases:
            with self.subTest(result_lists=result_lists):
                results = reciprocal_rank_fusion(result_lists)
                self.assertEqual({row["chunk_id"] for row in results}, expected_ids)

    def test_rrf_rejects_invalid_top_k_and_rrf_k(self):
        invalid_options = [
            ({"top_k": 0}, "top_k phải là số nguyên lớn hơn 0"),
            ({"top_k": True}, "top_k phải là số nguyên lớn hơn 0"),
            ({"rrf_k": -1}, "rrf_k phải là số nguyên không âm"),
            ({"rrf_k": 1.5}, "rrf_k phải là số nguyên không âm"),
        ]
        for options, message in invalid_options:
            with self.subTest(options=options), self.assertRaisesRegex(ValueError, message):
                reciprocal_rank_fusion([], **options)

    def test_rrf_rejects_hit_without_valid_chunk_id(self):
        for invalid_id in (None, "", 1):
            with self.subTest(chunk_id=invalid_id), self.assertRaisesRegex(
                ValueError, "thiếu chunk_id hợp lệ"
            ):
                reciprocal_rank_fusion([[hit(invalid_id)]])

    def test_hybrid_calls_both_retrievers_and_limits_candidates_and_results(self):
        class BM25:
            def search(self, query, top_k):
                self.args = (query, top_k)
                return [hit("both"), hit("lexical")]

        class Embedder:
            def embed_query(self, query):
                self.query = query
                return [0.1, 0.2]

        class Dense:
            def search(self, vector, top_k):
                self.args = (vector, top_k)
                return [hit("both"), hit("semantic")]

        bm25, embedder, dense = BM25(), Embedder(), Dense()
        results = hybrid_search("query text", bm25, embedder, dense,
                                top_k=2, candidate_k=7, rrf_k=60)
        self.assertEqual(bm25.args, ("query text", 7))
        self.assertEqual(embedder.query, "query text")
        self.assertEqual(dense.args, ([0.1, 0.2], 7))
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["chunk_id"], "both")

    def test_hybrid_retriever_search_uses_dense_retriever_interface(self):
        class BM25:
            def search(self, query, top_k):
                self.call = (query, top_k)
                return [hit("A"), hit("B")]

        class DenseRetrieverStub:
            def search(self, query, top_k):
                self.call = (query, top_k)
                return [hit("B"), hit("C")]

        lexical, dense = BM25(), DenseRetrieverStub()
        retriever = HybridRetriever(
            lexical,
            dense,
            HybridSearchConfig(top_k=2, candidate_k=5, rrf_k=60),
        )
        results = retriever.search("question", top_k=2)
        self.assertEqual(lexical.call, ("question", 5))
        self.assertEqual(dense.call, ("question", 5))
        self.assertEqual(results[0]["chunk_id"], "B")
        self.assertEqual(results[0]["source_ranks"], {"bm25": 2, "dense": 1})

    def test_dense_adapter_embeds_query_then_calls_vector_store(self):
        class Embedder:
            def embed_query(self, query):
                self.query = query
                return [0.3, 0.4]

        class Store:
            def search(self, vector, top_k):
                self.args = (vector, top_k)
                return [hit("D", score=0.8)]

        embedder, store = Embedder(), Store()
        result = EmbeddingQdrantAdapter(embedder, store).search("query", top_k=7)
        self.assertEqual(embedder.query, "query")
        self.assertEqual(store.args, ([0.3, 0.4], 7))
        self.assertEqual(result[0]["chunk_id"], "D")

    def test_hybrid_config_requires_candidate_depth_at_least_top_k(self):
        with self.assertRaisesRegex(ValueError, "candidate_k phải >= top_k"):
            HybridSearchConfig(top_k=10, candidate_k=5, rrf_k=60)

    def test_hybrid_rejects_invalid_query_and_candidate_k_before_retrieval(self):
        class Retriever:
            def search(self, query, top_k):
                raise AssertionError("Retriever should not be called for invalid input")

        class Embedder:
            def embed_query(self, query):
                raise AssertionError("Embedder should not be called for invalid input")

        invalid_inputs = [
            ("", 10, "query phải là chuỗi không rỗng"),
            ("   ", 10, "query phải là chuỗi không rỗng"),
            ("query", 0, "candidate_k phải là số nguyên lớn hơn 0"),
            ("query", True, "candidate_k phải là số nguyên lớn hơn 0"),
        ]
        for query, candidate_k, message in invalid_inputs:
            with self.subTest(query=query, candidate_k=candidate_k):
                with self.assertRaisesRegex(ValueError, message):
                    hybrid_search(
                        query,
                        Retriever(),
                        Embedder(),
                        Retriever(),
                        candidate_k=candidate_k,
                    )

    def test_dense_error_is_propagated_instead_of_silently_falling_back(self):
        class BM25:
            def search(self, query, top_k):
                return [hit("lexical")]

        class Embedder:
            def embed_query(self, query):
                return [0.1]

        class Dense:
            def search(self, vector, top_k):
                raise ConnectionError("Qdrant unavailable")

        with self.assertRaisesRegex(ConnectionError, "Qdrant unavailable"):
            hybrid_search("query", BM25(), Embedder(), Dense())

    def test_embedding_error_is_propagated_instead_of_returning_bm25_only(self):
        class BM25:
            def search(self, query, top_k):
                return [hit("lexical")]

        class Embedder:
            def embed_query(self, query):
                raise RuntimeError("Embedding service unavailable")

        class Dense:
            def search(self, vector, top_k):
                raise AssertionError("Dense search must not run after embedding fails")

        with self.assertRaisesRegex(RuntimeError, "Embedding service unavailable"):
            hybrid_search("query", BM25(), Embedder(), Dense())

    def test_cache_key_separates_metadata_filters_and_fusion_settings(self):
        class Static:
            def search(self, query, top_k):
                return [hit("a"), hit("b")]

        class DictCache(dict):
            def set(self, key, value):
                self[key] = value

        class KeepOnly:
            def __init__(self, chunk_id):
                self.cache_key = f"keep:{chunk_id}"
                self.chunk_id = chunk_id

            def __call__(self, hits):
                return [h for h in hits if h["chunk_id"] == self.chunk_id]

        cache = DictCache()
        only_a = HybridRetriever(Static(), Static(), metadata_filter=KeepOnly("a"), cache=cache)
        only_b = HybridRetriever(Static(), Static(), metadata_filter=KeepOnly("b"), cache=cache)
        other_rrf = HybridRetriever(Static(), Static(), HybridSearchConfig(rrf_k=10), cache=cache)
        self.assertEqual([h["chunk_id"] for h in only_a.search("q", top_k=2)], ["a"])
        self.assertEqual([h["chunk_id"] for h in only_b.search("q", top_k=2)], ["b"])
        other_rrf.search("q", top_k=2)
        self.assertEqual(len(cache), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
