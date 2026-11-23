import gc
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
qdrant_client = pytest.importorskip("qdrant_client")
from qdrant_client.models import Distance, PointStruct, VectorParams  # noqa: E402

from build_index import drop_local_collection  # noqa: E402


def test_drop_local_collection_leaves_no_points_behind(tmp_path):
    storage = tmp_path / "qdrant_storage"
    client = qdrant_client.QdrantClient(path=str(storage))
    client.create_collection("c", vectors_config=VectorParams(size=2, distance=Distance.COSINE))
    client.upsert("c", [PointStruct(id=i, vector=[1.0, float(i)], payload={}) for i in range(1, 4)])
    client.close()
    del client
    gc.collect()

    drop_local_collection(storage, "c")

    client = qdrant_client.QdrantClient(path=str(storage))
    try:
        assert "c" not in [c.name for c in client.get_collections().collections]
        client.create_collection("c", vectors_config=VectorParams(size=2, distance=Distance.COSINE))
        assert client.count("c").count == 0
    finally:
        client.close()
    assert drop_local_collection(tmp_path / "missing", "c") is None
