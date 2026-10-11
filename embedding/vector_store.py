"""Dense embedding and Qdrant helpers for the legal chunk schema.

Chunk files may be a flat list of child chunk payloads or the hierarchical
``{children: [...]}`` / ``{examples: [...]}`` formats emitted by chunking.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

MODEL_CONFIGS = {
    "AITeamVN/Vietnamese_Embedding": {"max_seq_length": 2048, "preprocess": "identity"},
    "bkai-foundation-models/vietnamese-bi-encoder": {"max_seq_length": 256, "preprocess": "underthesea"},
    "BAAI/bge-m3": {"max_seq_length": 8192, "preprocess": "identity"},
}


def _normalize_chunk(raw: dict[str, Any]) -> dict[str, Any]:
    chunk_id = raw.get("chunk_id", raw.get("id"))
    text = raw.get("text", raw.get("content"))
    if not isinstance(chunk_id, str) or not chunk_id.strip():
        raise ValueError("Mỗi child chunk phải có chunk_id (hoặc id) dạng chuỗi không rỗng")
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"Chunk {chunk_id!r} thiếu text/content không rỗng")
    metadata = raw.get("metadata")
    if metadata is None:
        reserved = {"id", "chunk_id", "text", "content", "metadata", "embed_text", "seg_text"}
        metadata = {k: v for k, v in raw.items() if k not in reserved}
    if not isinstance(metadata, dict):
        raise ValueError(f"metadata của chunk {chunk_id!r} phải là object")
    if not metadata:
        raise ValueError(f"Chunk {chunk_id!r} thiếu metadata pháp lý")
    return {"chunk_id": chunk_id.strip(), "text": text.strip(), "metadata": metadata,
            "embed_text": raw.get("embed_text") or text.strip()}


def load_chunks(path: str | Path) -> list[dict[str, Any]]:
    """Read flat/hierarchical JSON and normalize it to the internal schema."""
    source = Path(path)
    try:
        data = json.loads(source.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Không đọc được JSON chunk {source}: {exc}") from exc
    records = []
    if isinstance(data, list):
        records = data
    elif isinstance(data, dict) and isinstance(data.get("children"), list):
        records = data["children"]
    elif isinstance(data, dict) and isinstance(data.get("chunks"), list):
        records = data["chunks"]
    elif isinstance(data, dict) and isinstance(data.get("examples"), list):
        for example in data["examples"]:
            records.extend(example.get("child_chunks", []))
    elif isinstance(data, dict) and all(k in data for k in ("chunk_id", "text")):
        records = [data]
    else:
        raise ValueError("Schema JSON không hỗ trợ: cần list child chunks, object children hoặc examples")
    chunks = []
    seen_chunks: dict[str, dict[str, Any]] = {}
    for row in records:
        chunk = _normalize_chunk(row)
        previous = seen_chunks.get(chunk["chunk_id"])
        if previous is not None:
            if not (isinstance(data, dict) and "examples" in data and previous == chunk):
                raise ValueError(f"chunk_id bị trùng hoặc có nội dung mâu thuẫn: {chunk['chunk_id']}")
            continue
        seen_chunks[chunk["chunk_id"]] = chunk
        chunks.append(chunk)
    if not chunks:
        raise ValueError("Không tìm thấy child chunk nào")
    return chunks


def chunk_file_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@dataclass
class EmbeddingService:
    model_name: str
    device: str | None = None
    batch_size: int = 32

    def __post_init__(self) -> None:
        if self.model_name not in MODEL_CONFIGS:
            raise ValueError(f"Model không nằm trong cấu hình khảo sát: {self.model_name}")
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError("Cần cài embedding/requirements.txt (sentence-transformers)") from exc
        started = time.perf_counter()
        kwargs = {"device": self.device} if self.device else {}
        try:
            self.model = SentenceTransformer(self.model_name, **kwargs)
            self.model.max_seq_length = MODEL_CONFIGS[self.model_name]["max_seq_length"]
        except Exception as exc:
            raise RuntimeError(f"Không tải được embedding model {self.model_name}: {exc}") from exc
        self.load_seconds = time.perf_counter() - started
        self.dimension = int(self.model.get_sentence_embedding_dimension())
        if self.dimension < 1:
            raise RuntimeError("Model trả về dimension không hợp lệ")

    def _prepare(self, texts: Sequence[str]) -> list[str]:
        if MODEL_CONFIGS[self.model_name]["preprocess"] != "underthesea":
            return list(texts)
        try:
            from underthesea import word_tokenize
        except ImportError as exc:
            raise RuntimeError("Model BKAI cần cài embedding/requirements-bkai.txt để word-segment đầu vào") from exc
        return [" ".join(token.replace(" ", "_") for token in word_tokenize(text)) for text in texts]

    def _embed(self, texts: Sequence[str]) -> tuple[list[list[float]], float]:
        if not texts or any(not isinstance(t, str) or not t.strip() for t in texts):
            raise ValueError("Danh sách text phải chứa chuỗi không rỗng")
        prepared = self._prepare(texts)
        started = time.perf_counter()
        vectors = self.model.encode(prepared, batch_size=self.batch_size, convert_to_numpy=True,
                                    normalize_embeddings=True, show_progress_bar=False)
        elapsed = time.perf_counter() - started
        result = vectors.tolist()
        if len(result) != len(texts):
            raise RuntimeError("Số vector trả về không khớp số text đầu vào")
        for vector in result:
            if len(vector) != self.dimension or not all(math.isfinite(float(v)) for v in vector):
                raise RuntimeError("Vector rỗng, sai dimension, NaN hoặc vô cực")
        return result, elapsed

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        vectors, self.last_embedding_seconds = self._embed(texts)
        return vectors

    def embed_query(self, query: str) -> list[float]:
        vectors, self.last_query_embedding_seconds = self._embed([query])
        return vectors[0]


class VectorStore:
    def __init__(self, collection_name: str, dimension: int, url: str | None = None,
                 api_key: str | None = None, local_path: str | Path | None = None):
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.http import models
        except ImportError as exc:
            raise RuntimeError("Cần cài embedding/requirements.txt (qdrant-client)") from exc
        self.models = models
        self.collection_name = collection_name
        try:
            local_path = local_path or os.getenv("QDRANT_PATH")
            if local_path:
                storage_path = Path(local_path).expanduser().resolve()
                storage_path.mkdir(parents=True, exist_ok=True)
                self.client = QdrantClient(path=str(storage_path))
            else:
                self.client = QdrantClient(url=url or os.getenv("QDRANT_URL", "http://localhost:6333"),
                                           api_key=api_key or os.getenv("QDRANT_API_KEY"))
            self.client.get_collections()
        except Exception as exc:
            raise RuntimeError("Không mở được Qdrant. Đặt QDRANT_PATH để dùng local embedded, hoặc chạy dịch vụ tại QDRANT_URL (mặc định localhost:6333). "+str(exc)) from exc
        if dimension < 1:
            raise ValueError("dimension phải lớn hơn 0")
        self.dimension = dimension
        self.create_collection()

    def collection_exists(self) -> bool:
        return any(c.name == self.collection_name for c in self.client.get_collections().collections)

    def create_collection(self, recreate: bool = False) -> None:
        if self.collection_exists():
            if not recreate:
                info = self.client.get_collection(self.collection_name)
                size = info.config.params.vectors.size
                if size != self.dimension:
                    raise ValueError(f"Collection {self.collection_name} dimension={size}, yêu cầu {self.dimension}; đổi collection hoặc recreate")
                return
            self.client.delete_collection(self.collection_name)
        self.client.create_collection(self.collection_name, vectors_config=self.models.VectorParams(
            size=self.dimension, distance=self.models.Distance.COSINE))

    def add_chunks(self, chunks: Sequence[dict[str, Any]], vectors: Sequence[Sequence[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("Số chunk và vector không khớp")
        points = []
        for chunk, vector in zip(chunks, vectors):
            if len(vector) != self.dimension or not all(math.isfinite(float(v)) for v in vector):
                raise ValueError(f"Vector của {chunk.get('chunk_id')} sai dimension hoặc chứa giá trị không hữu hạn")
            payload = {"chunk_id": chunk["chunk_id"], "text": chunk["text"], "metadata": chunk["metadata"]}
            points.append(self.models.PointStruct(id=str(uuid.uuid5(uuid.NAMESPACE_URL, chunk["chunk_id"])),
                                                   vector=list(vector), payload=payload))
        self.client.upload_points(self.collection_name, points=points, batch_size=128, wait=True)

    def search(self, query_vector: Sequence[float], top_k: int = 5) -> list[dict[str, Any]]:
        if len(query_vector) != self.dimension:
            raise ValueError(f"Query dimension {len(query_vector)} != collection dimension {self.dimension}")
        if top_k < 1:
            raise ValueError("top_k phải lớn hơn 0")
        started = time.perf_counter()
        hits = self.client.query_points(collection_name=self.collection_name, query=list(query_vector),
                                        limit=top_k, with_payload=True).points
        self.last_search_seconds = time.perf_counter() - started
        return [{"chunk_id": hit.payload["chunk_id"], "score": float(hit.score),
                 "text": hit.payload["text"], "metadata": hit.payload["metadata"]} for hit in hits]

    def delete(self, chunk_ids: Iterable[str]) -> None:
        ids = list(chunk_ids)
        if ids:
            point_ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id)) for chunk_id in ids]
            self.client.delete(self.collection_name, points_selector=self.models.PointIdsList(points=point_ids), wait=True)

    def count(self) -> int:
        return int(self.client.count(self.collection_name, exact=True).count)
