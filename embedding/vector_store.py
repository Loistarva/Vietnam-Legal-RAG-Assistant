# -*- coding: utf-8 -*-
"""
embedding/vector_store.py
Quản lý lưu trữ vector và truy vấn kèm Metadata Pre-filter theo Data Contract Sprint 5 & Sprint 6.
"""
from __future__ import annotations

import json
import math
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        Distance,
        FieldCondition,
        Filter,
        MatchValue,
        PointStruct,
        VectorParams,
    )

    HAS_QDRANT = True
except ImportError:
    HAS_QDRANT = False


def normalize_chunk_record(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Chuẩn hóa bản ghi chunk từ output của Chunking (Sprint 5) hoặc fixture (Sprint 6)
    về đúng cấu trúc Data Contract dùng chung.
    """
    chunk_id = str(raw.get("chunk_id") or raw.get("id") or "").strip()
    if not chunk_id:
        raise ValueError("Chunk record thiếu trường bắt buộc 'chunk_id'.")

    chunk_text = str(raw.get("chunk_text") or "").strip()
    if not chunk_text:
        raise ValueError(
            f"Chunk '{chunk_id}' thiếu 'chunk_text' (không được dùng 'text' thay cho 'chunk_text')."
        )

    embed_text = str(raw.get("embed_text") or "").strip()
    if not embed_text:
        raise ValueError(
            f"Chunk '{chunk_id}' thiếu 'embed_text' (payload bắt buộc tại giao điểm Chunking -> Embedding)."
        )

    raw_meta = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}

    # Đọc trực tiếp các trường ID từ root-level của bản ghi
    parent_clause_id = str(
        raw.get("parent_clause_id")
        or raw_meta.get("parent_clause_id")
        or raw.get("clause_id")
        or ""
    ).strip()
    if not parent_clause_id:
        raise ValueError(f"Chunk '{chunk_id}' thiếu 'parent_clause_id'.")

    document_id = str(
        raw.get("document_id")
        or raw_meta.get("document_id")
        or chunk_id.split("_art_")[0]
    ).strip()

    article_id = str(
        raw.get("article_id")
        or raw_meta.get("article_id")
        or (parent_clause_id.split("_clause_")[0] if "_clause_" in parent_clause_id else "")
    ).strip()

    clause_id = str(
        raw.get("clause_id")
        or raw_meta.get("clause_id")
        or parent_clause_id
    ).strip()

    validity_status = str(
        raw.get("validity_status")
        or raw_meta.get("validity_status")
        or "Không xác định"
    ).strip()

    metadata: Dict[str, Any] = {
        "document_id": document_id,
        "document_number": raw.get("document_number") or raw_meta.get("document_number") or "",
        "document_title": raw.get("document_title") or raw_meta.get("document_title") or raw.get("title") or "",
        "article_number": raw.get("article_number") or raw_meta.get("article_number") or "",
        "clause_number": raw.get("clause_number") or raw_meta.get("clause_number") or "",
        "validity_status": validity_status,
        "source_url": raw.get("source_url") or raw_meta.get("source_url") or "",
        "breadcrumb": raw.get("breadcrumb") or raw_meta.get("breadcrumb") or "",
    }
    if "effective_from" in raw_meta or "effective_from" in raw:
        metadata["effective_from"] = raw_meta.get("effective_from") or raw.get("effective_from")
    if "effective_to" in raw_meta or "effective_to" in raw:
        metadata["effective_to"] = raw_meta.get("effective_to") or raw.get("effective_to")

    result: Dict[str, Any] = {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "article_id": article_id,
        "clause_id": clause_id,
        "parent_clause_id": parent_clause_id,
        "chunk_text": chunk_text,
        "embed_text": embed_text,
        "validity_status": validity_status,
        "metadata": metadata,
    }
    if "embed_text_raw" in raw:
        result["embed_text_raw"] = raw["embed_text_raw"]
    if "point_ref" in raw and raw["point_ref"] is not None:
        result["point_ref"] = raw["point_ref"]
    return result


def _cosine_similarity(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class LegalVectorStore:
    """
    Vector Store hỗ trợ Qdrant (local disk / memory) và fallback bộ nhớ trong (In-Memory)
    phục vụ phát triển độc lập bằng mock/stub và chạy production.
    """

    def __init__(
        self,
        collection_name: str = "vietnam_legal_chunks",
        dimension: int = 768,
        storage_path: Optional[str] = None,
        use_qdrant: bool = True,
    ) -> None:
        self.collection_name = collection_name
        self.dimension = dimension
        self.storage_path = storage_path
        self.use_qdrant = bool(use_qdrant and HAS_QDRANT)
        self._memory_records: List[Dict[str, Any]] = []
        self.client: Optional[Any] = None

        if self.use_qdrant:
            if storage_path and storage_path != ":memory:":
                Path(storage_path).mkdir(parents=True, exist_ok=True)
                self.client = QdrantClient(path=storage_path)
            else:
                self.client = QdrantClient(":memory:")
            self._ensure_collection()

    def _ensure_collection(self) -> None:
        if not self.client:
            return
        existing = [c.name for c in self.client.get_collections().collections]
        if self.collection_name not in existing:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.dimension,
                    distance=Distance.COSINE,
                ),
            )

    @staticmethod
    def build_active_legal_filter() -> Optional[Any]:
        """
        Tạo bộ lọc loại trừ văn bản có validity_status == 'Hết hiệu lực'
        trước giai đoạn tính toán khoảng cách vector (Ràng buộc kỹ thuật Task 5).
        """
        if not HAS_QDRANT:
            return None
        return Filter(
            must_not=[
                FieldCondition(
                    key="metadata.validity_status",
                    match=MatchValue(value="Hết hiệu lực"),
                ),
                FieldCondition(
                    key="validity_status",
                    match=MatchValue(value="Hết hiệu lực"),
                ),
            ]
        )

    def upsert_chunks(
        self,
        chunks: Sequence[Dict[str, Any]],
        vectors: Sequence[Sequence[float]],
    ) -> int:
        if len(chunks) != len(vectors):
            raise ValueError(
                f"Số lượng chunks ({len(chunks)}) không khớp số lượng vectors ({len(vectors)})."
            )
        if not chunks:
            return 0

        normalized_records = [normalize_chunk_record(c) for c in chunks]

        if self.use_qdrant and self.client is not None:
            points = []
            for record, vec in zip(normalized_records, vectors):
                if len(vec) != self.dimension:
                    raise ValueError(
                        f"Vector dimension ({len(vec)}) khác cấu hình collection ({self.dimension})."
                    )
                point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, record["chunk_id"]))
                points.append(
                    PointStruct(
                        id=point_id,
                        vector=list(map(float, vec)),
                        payload=record,
                    )
                )
            self.client.upsert(collection_name=self.collection_name, points=points)
            return len(points)

        # In-Memory mode (phục vụ mock/stub hoặc môi trường chưa cài Qdrant)
        existing_map = {r["record"]["chunk_id"]: idx for idx, r in enumerate(self._memory_records)}
        for record, vec in zip(normalized_records, vectors):
            if len(vec) != self.dimension:
                raise ValueError(
                    f"Vector dimension ({len(vec)}) khác cấu hình store ({self.dimension})."
                )
            entry = {"record": record, "vector": list(map(float, vec))}
            cid = record["chunk_id"]
            if cid in existing_map:
                self._memory_records[existing_map[cid]] = entry
            else:
                self._memory_records.append(entry)
        return len(normalized_records)

    def search(
        self,
        query_vector: Sequence[float],
        top_k: int = 5,
        exclude_expired: bool = True,
    ) -> List[Dict[str, Any]]:
        if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k <= 0:
            raise ValueError(f"Tham số top_k phải là số nguyên dương (nhận được: {top_k!r}).")

        if len(query_vector) != self.dimension:
            raise ValueError(
                f"Query vector dimension ({len(query_vector)}) khác cấu hình ({self.dimension})."
            )

        if self.use_qdrant and self.client is not None:
            query_filter = self.build_active_legal_filter() if exclude_expired else None
            if hasattr(self.client, "query_points"):
                response = self.client.query_points(
                    collection_name=self.collection_name,
                    query=list(map(float, query_vector)),
                    query_filter=query_filter,
                    limit=top_k,
                    with_payload=True,
                )
                hits = response.points
            else:
                hits = self.client.search(
                    collection_name=self.collection_name,
                    query_vector=list(map(float, query_vector)),
                    query_filter=query_filter,
                    limit=top_k,
                    with_payload=True,
                )

            results: List[Dict[str, Any]] = []
            for rank_idx, hit in enumerate(hits, start=1):
                payload = hit.payload or {}
                results.append(self._format_hit(payload, rank=rank_idx, score=float(hit.score)))
            return results

        # In-Memory search
        candidates = []
        for item in self._memory_records:
            rec = item["record"]
            status = rec.get("validity_status") or rec.get("metadata", {}).get("validity_status")
            if exclude_expired and status == "Hết hiệu lực":
                continue
            score = _cosine_similarity(query_vector, item["vector"])
            candidates.append((score, rec))

        candidates.sort(key=lambda x: x[0], reverse=True)
        top_candidates = candidates[:top_k]

        return [
            self._format_hit(rec, rank=idx, score= float(score))
            for idx, (score, rec) in enumerate(top_candidates, start=1)
        ]

    @staticmethod
    def _format_hit(payload: Dict[str, Any], rank: int, score: float) -> Dict[str, Any]:
        return {
            "chunk_id": payload["chunk_id"],
            "document_id": payload["document_id"],
            "article_id": payload["article_id"],
            "clause_id": payload["clause_id"],
            "parent_clause_id": payload["parent_clause_id"],
            "rank": rank,
            "score": round(score, 6),
            "chunk_text": payload["chunk_text"],
            "metadata": payload.get("metadata", {}),
        }

    def count(self) -> int:
        if self.use_qdrant and self.client is not None:
            return int(self.client.count(collection_name=self.collection_name, exact=True).count)
        return len(self._memory_records)

    def save_snapshot_json(self, output_path: str | Path) -> None:
        """Lưu bản sao metadata & vectors phục vụ nạp nhanh hoặc kiểm thử độc lập."""
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "collection_name": self.collection_name,
            "dimension": self.dimension,
            "records": self._memory_records,
        }
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load_snapshot_json(cls, snapshot_path: str | Path) -> "LegalVectorStore":
        data = json.loads(Path(snapshot_path).read_text(encoding="utf-8"))
        store = cls(
            collection_name=data["collection_name"],
            dimension=int(data["dimension"]),
            use_qdrant=False,
        )
        store._memory_records = data.get("records", [])
        return store
