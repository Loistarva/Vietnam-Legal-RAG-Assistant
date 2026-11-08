"""Unit checks for Qdrant server mode without requiring a running server."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from embedding.vector_store import LegalVectorStore


def collection_info(dimension=1024):
    return SimpleNamespace(
        config=SimpleNamespace(
            params=SimpleNamespace(vectors=SimpleNamespace(size=dimension)),
        ),
    )


class QdrantServerAdapterTest(unittest.TestCase):
    def test_server_mode_uses_url_and_keeps_sidecar_path(self):
        with patch("embedding.vector_store.QdrantClient") as client_factory:
            client = client_factory.return_value
            client.get_collections.return_value.collections = [
                SimpleNamespace(name="vietnam_legal_chunks")
            ]
            client.get_collection.return_value = collection_info()

            store = LegalVectorStore(
                collection_name="vietnam_legal_chunks",
                dimension=1024,
                storage_path="data/indexes/qdrant_storage",
                url="http://127.0.0.1:6333",
                create_if_missing=False,
            )

        client_factory.assert_called_once_with(url="http://127.0.0.1:6333")
        self.assertTrue(store.is_server)
        self.assertTrue(store.persistent)
        self.assertFalse(store.create_if_missing)
        self.assertEqual(store.storage_path, "data/indexes/qdrant_storage")
        self.assertIs(store.client, client)

    def test_missing_server_collection_fails_closed_without_creating_it(self):
        with patch("embedding.vector_store.QdrantClient") as client_factory:
            client = client_factory.return_value
            client.get_collections.return_value.collections = []
            with self.assertRaisesRegex(ValueError, "http://127.0.0.1:6333"):
                LegalVectorStore(
                    collection_name="vietnam_legal_chunks",
                    storage_path="data/indexes/qdrant_storage",
                    url="http://127.0.0.1:6333",
                    create_if_missing=False,
                )
            client.create_collection.assert_not_called()

    def test_server_collection_with_wrong_dimension_is_rejected(self):
        with patch("embedding.vector_store.QdrantClient") as client_factory:
            client = client_factory.return_value
            client.get_collections.return_value.collections = [
                SimpleNamespace(name="vietnam_legal_chunks")
            ]
            client.get_collection.return_value = collection_info(dimension=768)
            with self.assertRaisesRegex(ValueError, "768"):
                LegalVectorStore(
                    collection_name="vietnam_legal_chunks",
                    dimension=1024,
                    storage_path="data/indexes/qdrant_storage",
                    url="http://127.0.0.1:6333",
                    create_if_missing=False,
                )

    def test_recreate_is_refused_in_server_mode(self):
        with self.assertRaisesRegex(ValueError, "recreate"):
            LegalVectorStore(url="http://127.0.0.1:6333", recreate=True)

    def test_memory_adapter_cannot_receive_a_server_url(self):
        with self.assertRaisesRegex(ValueError, "use_qdrant=False"):
            LegalVectorStore(use_qdrant=False, url="http://127.0.0.1:6333")


if __name__ == "__main__":
    unittest.main(verbosity=2)
