import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from retrieval.hybrid_retriever import HybridRetriever, RedisJSONCache, build_redis_json_cache


def _hit(chunk_id):
    return {"chunk_id": chunk_id, "text": f"text {chunk_id}"}


class _StaticRetriever:
    def search(self, query, top_k, *, as_of_date):
        return [_hit("c1")]


class RedisJSONCacheTest(unittest.TestCase):
    def test_cache_serializes_json_and_uses_ttl_prefix(self):
        class Client:
            def __init__(self):
                self.values = {}
                self.set_call = None

            def get(self, key):
                return self.values.get(key)

            def setex(self, key, ttl, value):
                self.set_call = (key, ttl, value)
                self.values[key] = value

        client = Client()
        cache = RedisJSONCache(client, prefix="test:retrieval:", ttl_seconds=90)
        value = {"results": [{"chunk_id": "c1", "title": "Điều 1"}]}
        self.assertIsNone(cache.get("abc"))
        cache.set("abc", value)
        self.assertEqual(client.set_call[:2], ("test:retrieval:abc", 90))
        self.assertEqual(cache.get("abc"), value)

    def test_cache_connection_errors_fail_open_as_miss_and_noop(self):
        class OfflineClient:
            def get(self, _key):
                raise ConnectionError("redis offline")

            def setex(self, *_args):
                raise ConnectionError("redis offline")

        cache = RedisJSONCache(OfflineClient(), prefix="test")
        self.assertIsNone(cache.get("key"))
        cache.set("key", {"safe": True})

    def test_invalid_json_is_discarded_and_deleted(self):
        class Client:
            def __init__(self):
                self.deleted = []

            def get(self, _key):
                return "{" 

            def delete(self, key):
                self.deleted.append(key)

        client = Client()
        cache = RedisJSONCache(client, prefix="test")
        self.assertIsNone(cache.get("key"))
        self.assertEqual(client.deleted, ["test:key"])

    def test_factory_pings_redis_before_enabling_cache(self):
        class FakeRedis:
            @staticmethod
            def from_url(url, **kwargs):
                self.assertEqual(url, "redis://localhost:6379/0")
                self.assertTrue(kwargs["decode_responses"])
                return SimpleNamespace(ping=lambda: True)

        with patch.dict(sys.modules, {"redis": SimpleNamespace(Redis=FakeRedis)}):
            cache = build_redis_json_cache("redis://localhost:6379/0")
        self.assertIsInstance(cache, RedisJSONCache)
        self.assertIsNone(build_redis_json_cache(None))

    def test_factory_disables_cache_when_redis_is_unavailable(self):
        class FakeRedis:
            @staticmethod
            def from_url(_url, **_kwargs):
                return SimpleNamespace(ping=lambda: (_ for _ in ()).throw(ConnectionError("offline")))

        with patch.dict(sys.modules, {"redis": SimpleNamespace(Redis=FakeRedis)}):
            self.assertIsNone(build_redis_json_cache("redis://localhost:6379/0"))

    def test_retrieval_cache_key_separates_query_date_and_index_context(self):
        class Cache(dict):
            def set(self, key, value):
                self[key] = value

        cache = Cache()
        retriever = HybridRetriever(
            _StaticRetriever(), _StaticRetriever(), cache=cache,
            cache_context={"corpus_sha256": "corpus-a", "dense_model": "model-a"},
        )
        retriever.search("question one", top_k=1, as_of_date="1995-01-01")
        retriever.search("question one", top_k=1, as_of_date="2026-01-01")
        retriever.search("question two", top_k=1, as_of_date="1995-01-01")
        self.assertEqual(len(cache), 3)
        other_model = HybridRetriever(
            _StaticRetriever(), _StaticRetriever(), cache=cache,
            cache_context={"corpus_sha256": "corpus-a", "dense_model": "model-b"},
        )
        other_model.search("question one", top_k=1, as_of_date="1995-01-01")
        self.assertEqual(len(cache), 4)

    def test_cache_hit_skips_both_retrieval_branches(self):
        class Cache(dict):
            def set(self, key, value):
                self[key] = value

        class CountingRetriever(_StaticRetriever):
            def __init__(self):
                self.calls = 0

            def search(self, query, top_k, *, as_of_date):
                self.calls += 1
                return super().search(query, top_k, as_of_date=as_of_date)

        sparse, dense, cache = CountingRetriever(), CountingRetriever(), Cache()
        retriever = HybridRetriever(sparse, dense, cache=cache)
        first = retriever.retrieve("question", as_of_date="2026-01-01")
        second = retriever.retrieve("question", as_of_date="2026-01-01")
        self.assertEqual(first, second)
        self.assertEqual((sparse.calls, dense.calls), (1, 1))

    def test_production_cli_passes_connected_cache_to_hybrid_retriever(self):
        from scripts import run_retrieval

        class Retriever:
            def search(self, query, top_k, *, as_of_date):
                return []

        cache = object()
        args = run_retrieval.parse_args([
            "--query", "question", "--retriever", "hybrid", "--reranker", "none",
            "--redis-url", "redis://localhost:6379/0",
        ])
        with patch.object(run_retrieval, "build_redis_json_cache", return_value=cache) as create_cache, patch.object(
            run_retrieval, "build_hybrid_retriever", return_value=Retriever()
        ) as build_hybrid, patch.object(run_retrieval, "load_parent_context_config",
                                        return_value=SimpleNamespace(enabled=False)):
            run_retrieval.build_pipeline(args)
        create_cache.assert_called_once()
        self.assertIs(build_hybrid.call_args.kwargs["cache"], cache)
        self.assertEqual(build_hybrid.call_args.kwargs["cache_context"]["reranker"], {"enabled": False})


if __name__ == "__main__":
    unittest.main()
