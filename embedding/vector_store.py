# -*- coding: utf-8 -*-
"""
embedding/vector_store.py
Quản lý lưu trữ vector và truy vấn kèm Metadata Pre-filter theo Data Contract Sprint 5 & Sprint 6.
"""
from __future__ import annotations

import hashlib
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

VALID_STATUSES = {
    "Còn hiệu lực",
    "Hết hiệu lực",
    "Sắp có hiệu lực",
    "Sửa đổi bổ sung",
    "Không xác định",
}


def chunk_file_sha256(path: str | Path) -> str:
    """Tính hash SHA-256 của file chunk."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_chunks(chunks_file: str | Path) -> List[Dict[str, Any]]:
    """Tải danh sách chunk từ file json hoặc jsonl."""
    path = Path(chunks_file)
    if not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy file chunk tại: {path}")

    reserved = {
        "id", "chunk_id", "text", "content", "chunk_text", "metadata",
        "content_segmented", "seg_text", "embed_text", "embed_text_raw",
    }
    records = []
    if path.suffix.lower() == ".jsonl":
        with path.open("r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if line:
                    item = json.loads(line)
                    if isinstance(item, dict):
                        if "chunk_id" not in item and "id" in item:
                            item["chunk_id"] = item["id"]
                        if "metadata" not in item:
                            item["metadata"] = {k: v for k, v in item.items() if k not in reserved}
                    records.append(item)
    else:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(data, list):
            records = data
        elif isinstance(data, dict) and "chunks" in data:
            records = data["chunks"]
        else:
            records = [data]
        for item in records:
            if isinstance(item, dict):
                if "chunk_id" not in item and "id" in item:
                    item["chunk_id"] = item["id"]
                if "metadata" not in item:
                    item["metadata"] = {k: v for k, v in item.items() if k not in reserved}
    return records


def is_effective_at(record_or_metadata: Dict[str, Any], as_of_date: str) -> bool:
    """
    Kiểm tra một bản ghi chunk hoặc metadata có hiệu lực tại thời điểm as_of_date (YYYY-MM-DD).
    - effective_from <= as_of_date < effective_to (nếu có effective_to).
    - Nếu bản ghi có effective_from > as_of_date -> False (chưa có hiệu lực).
    - Nếu bản ghi có effective_to <= as_of_date -> False (đã hết hiệu lực).
    - Ngược lại -> True.
    """
    if not as_of_date:
        return True
    as_of = str(as_of_date).strip()[:10]

    meta = record_or_metadata.get("metadata") if isinstance(record_or_metadata.get("metadata"), dict) else record_or_metadata

    eff_from = (
        record_or_metadata.get("effective_from")
        or meta.get("effective_from")
        or record_or_metadata.get("effective_date")
        or meta.get("effective_date")
    )
    eff_to = (
        record_or_metadata.get("effective_to")
        if "effective_to" in record_or_metadata
        else meta.get("effective_to")
    )
    if eff_to is None:
        eff_to = record_or_metadata.get("expiry_date") or meta.get("expiry_date")

    if eff_from:
        eff_from_str = str(eff_from).strip()[:10]
        if eff_from_str and eff_from_str > as_of:
            return False

    if eff_to is not None and str(eff_to).strip():
        eff_to_str = str(eff_to).strip()[:10]
        if eff_to_str and eff_to_str <= as_of:
            return False

    return True


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

    if validity_status not in VALID_STATUSES:
        raise ValueError(
            f"Chunk '{chunk_id}' có validity_status '{validity_status}' không hợp lệ. "
            f"Chỉ chấp nhận các giá trị: {sorted(list(VALID_STATUSES))}"
        )

    effective_from = str(
        raw.get("effective_from")
        or raw_meta.get("effective_from")
        or raw.get("effective_date")
        or raw_meta.get("effective_date")
        or ""
    ).strip()

    effective_to = raw.get("effective_to") if "effective_to" in raw else raw_meta.get("effective_to")
    if effective_to is None:
        effective_to = raw.get("expiry_date") or raw_meta.get("expiry_date")
    if effective_to is not None:
        effective_to = str(effective_to).strip()

    source_url = str(
        raw.get("source_url")
        or raw_meta.get("source_url")
        or ""
    ).strip()

    document_type = str(
        raw.get("document_type")
        or raw_meta.get("document_type")
        or ""
    ).strip()

    document_title = str(
        raw.get("document_title")
        or raw_meta.get("document_title")
        or raw.get("title")
        or raw_meta.get("title")
        or ""
    ).strip()

    document_number = str(
        raw.get("document_number")
        or raw_meta.get("document_number")
        or ""
    ).strip()

    article_number = str(
        raw.get("article_number")
        or raw_meta.get("article_number")
        or ""
    ).strip()

    clause_number = str(
        raw.get("clause_number")
        or raw_meta.get("clause_number")
        or ""
    ).strip()

    breadcrumb = str(
        raw.get("breadcrumb")
        or raw_meta.get("breadcrumb")
        or ""
    ).strip()

    source_status = raw.get("source_status") or raw_meta.get("source_status")
    provision_status = raw.get("provision_status") or raw_meta.get("provision_status")

    metadata: Dict[str, Any] = {
        **raw_meta,
        "document_id": document_id,
        "document_number": document_number,
        "document_type": document_type,
        "document_title": document_title,
        "article_number": article_number,
        "clause_number": clause_number,
        "validity_status": validity_status,
        "source_status": source_status if source_status is not None else "",
        "provision_status": provision_status if provision_status is not None else "",
        "effective_date": effective_from,
        "effective_from": effective_from,
        "effective_to": effective_to,
        "source_url": source_url,
        "breadcrumb": breadcrumb,
    }

    result: Dict[str, Any] = {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "article_id": article_id,
        "clause_id": clause_id,
        "parent_clause_id": parent_clause_id,
        "chunk_text": chunk_text,
        "embed_text": embed_text,
        "validity_status": validity_status,
        "effective_from": effective_from,
        "effective_to": effective_to,
        "source_url": source_url,
        "metadata": metadata,
    }
    if source_status is not None:
        result["source_status"] = source_status
    if provision_status is not None:
        result["provision_status"] = provision_status
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
        dimension: int = 1024,
        storage_path: Optional[str] = None,
        use_qdrant: bool = True,
        create_if_missing: bool = True,
    ) -> None:
        self.collection_name = collection_name
        self.dimension = dimension
        self.storage_path = storage_path
        self.use_qdrant = bool(use_qdrant and HAS_QDRANT)
        self.create_if_missing = create_if_missing
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
            if not self.create_if_missing:
                raise ValueError(f"Collection '{self.collection_name}' không tồn tại.")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.dimension,
                    distance=Distance.COSINE,
                ),
            )
        else:
            # Collection đã tồn tại: kiểm tra số chiều (Lỗi E2)
            col_info = self.client.get_collection(self.collection_name)
            params = getattr(col_info.config, "params", None)
            existing_dim = None
            if params and hasattr(params, "vectors"):
                vec_params = params.vectors
                if hasattr(vec_params, "size"):
                    existing_dim = vec_params.size
                elif isinstance(vec_params, dict):
                    existing_dim = getattr(next(iter(vec_params.values()), None), "size", None)

            if existing_dim is not None and existing_dim != self.dimension:
                raise ValueError(
                    f"Collection '{self.collection_name}' có số chiều {existing_dim}, "
                    f"không khớp với cấu hình hiện tại ({self.dimension} chiều)."
                )

    @staticmethod
    def build_active_legal_filter(as_of_date: Optional[str] = None) -> Optional[Any]:
        """
        Tạo bộ lọc trước giai đoạn tính toán khoảng cách vector.
        - Nếu as_of_date is None: lọc loại trừ validity_status == 'Hết hiệu lực'.
        - Nếu as_of_date có giá trị: không lọc cứng validity_status để hỗ trợ historical_law.
        """
        if not HAS_QDRANT:
            return None
        if as_of_date is None:
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
        return None

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
        as_of_date: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k <= 0:
            raise ValueError(f"Tham số top_k phải là số nguyên dương (nhận được: {top_k!r}).")

        if len(query_vector) != self.dimension:
            raise ValueError(
                f"Query vector dimension ({len(query_vector)}) khác cấu hình ({self.dimension})."
            )

        if as_of_date:
            as_of_str = str(as_of_date).strip()[:10]
            # Khi có as_of_date, lọc theo thời điểm hiệu lực thay vì lọc tĩnh
            exclude_expired = False
        else:
            as_of_str = None

        if self.use_qdrant and self.client is not None:
            query_filter = self.build_active_legal_filter(as_of_date=as_of_date) if exclude_expired else None
            fetch_k = max(top_k * 5, 50) if (exclude_expired or as_of_str) else top_k
            if hasattr(self.client, "query_points"):
                response = self.client.query_points(
                    collection_name=self.collection_name,
                    query=list(map(float, query_vector)),
                    query_filter=query_filter,
                    limit=fetch_k,
                    with_payload=True,
                )
                hits = response.points
            else:
                hits = self.client.search(
                    collection_name=self.collection_name,
                    query_vector=list(map(float, query_vector)),
                    query_filter=query_filter,
                    limit=fetch_k,
                    with_payload=True,
                )

            filtered_hits = []
            for hit in hits:
                payload = hit.payload or {}
                if as_of_str:
                    if not is_effective_at(payload, as_of_str):
                        continue
                elif exclude_expired:
                    status = payload.get("validity_status") or payload.get("metadata", {}).get("validity_status")
                    if status == "Hết hiệu lực":
                        continue

                filtered_hits.append(self._format_hit(payload, rank=len(filtered_hits) + 1, score=float(hit.score)))
                if len(filtered_hits) >= top_k:
                    break
            return filtered_hits

        # In-Memory search
        candidates = []
        for item in self._memory_records:
            rec = item["record"]
            if as_of_str:
                if not is_effective_at(rec, as_of_str):
                    continue
            elif exclude_expired:
                status = rec.get("validity_status") or rec.get("metadata", {}).get("validity_status")
                if status == "Hết hiệu lực":
                    continue

            score = _cosine_similarity(query_vector, item["vector"])
            candidates.append((score, rec))

        candidates.sort(key=lambda x: x[0], reverse=True)
        top_candidates = candidates[:top_k]

        return [
            self._format_hit(rec, rank=idx, score=float(score))
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
    def load_snapshot_json(
        cls, snapshot_path: str | Path, expected_dimension: Optional[int] = None
    ) -> "LegalVectorStore":
        data = json.loads(Path(snapshot_path).read_text(encoding="utf-8"))
        snapshot_dim = int(data["dimension"])
        if expected_dimension is not None and snapshot_dim != expected_dimension:
            raise ValueError(
                f"Collection '{data.get('collection_name')}' có số chiều {snapshot_dim}, "
                f"không khớp với cấu hình hiện tại ({expected_dimension} chiều)."
            )
        store = cls(
            collection_name=data["collection_name"],
            dimension=snapshot_dim,
            use_qdrant=False,
        )
        store._memory_records = data.get("records", [])
        return store
