# -*- coding: utf-8 -*-
"""
embedding/dense_retriever.py
Triển khai DenseRetriever tuân thủ Data Contract Sprint 6.
"""
from __future__ import annotations

import hashlib
import math
import time
from typing import Any, Callable, Dict, List, Optional, Sequence

from embedding.vector_store import LegalVectorStore

try:
    from underthesea import word_tokenize

    HAS_UNDERTHESEA = True
except ImportError:
    HAS_UNDERTHESEA = False


DEFAULT_MODEL_NAME = "bkai-foundation-models/vietnamese-bi-encoder"

MODEL_DIMENSIONS = {
    "bkai-foundation-models/vietnamese-bi-encoder": 768,
    "AITeamVN/Vietnamese_Embedding": 1024,
    "BAAI/bge-m3": 1024,
}


def deterministic_mock_embed(text: str, dimension: int = 768) -> List[float]:
    """
    Hàm tạo vector giả lập tất định (deterministic mock embedding) phục vụ
    phát triển độc lập (Mock-first) và kiểm thử tự động không phụ thuộc GPU/Model thật.
    """
    tokens = [tok.lower() for tok in text.replace("_", " ").split() if tok.strip()]
    if not tokens:
        return [0.0] * dimension

    vec = [0.0] * dimension
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        for i in range(0, len(digest), 4):
            idx = int.from_bytes(digest[i : i + 2], "big") % dimension
            sign = 1.0 if (digest[i + 2] % 2 == 0) else -1.0
            weight = 1.0 + (digest[i + 3] / 255.0)
            vec[idx] += sign * weight

    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


class DenseRetriever:
    """
    Dense Retriever chuẩn hóa theo interface chung của Sprint 6:
    - Dùng `embed_text` khi tạo vector cho corpus chunks.
    - Trả `chunk_text`, `chunk_id`, `parent_clause_id`, `document_id`, `rank`, `score`, `metadata`.
    - Hỗ trợ đo latency và chạy độc lập với Mock Embedder hoặc SentenceTransformer.
    """

    def __init__(
        self,
        vector_store: LegalVectorStore,
        model_name: str = DEFAULT_MODEL_NAME,
        embed_fn: Optional[Callable[[Sequence[str]], List[List[float]]]] = None,
        use_mock: bool = False,
        use_word_segmentation: Optional[bool] = None,
        batch_size: int = 32,
    ) -> None:
        self.vector_store = vector_store
        self.model_name = model_name
        self.batch_size = batch_size
        self.use_mock = use_mock or (embed_fn is not None)
        self._custom_embed_fn = embed_fn
        self._st_model: Optional[Any] = None

        if use_word_segmentation is None:
            self.use_word_segmentation = "vietnamese-bi-encoder" in model_name.lower()
        else:
            self.use_word_segmentation = use_word_segmentation

        self.last_latency_ms: Dict[str, float] = {
            "query_encode_ms": 0.0,
            "vector_search_ms": 0.0,
            "total_ms": 0.0,
        }

    def _load_st_model(self) -> Any:
        if self._st_model is None:
            from sentence_transformers import SentenceTransformer

            self._st_model = SentenceTransformer(self.model_name)
        return self._st_model

    def _preprocess_query(self, query: str) -> str:
        cleaned = " ".join(query.strip().split())
        if not cleaned:
            return ""
        if self.use_word_segmentation and HAS_UNDERTHESEA:
            return word_tokenize(cleaned, format="text")
        return cleaned

    def encode_texts(self, texts: Sequence[str], is_query: bool = False) -> List[List[float]]:
        processed = [
            self._preprocess_query(t) if is_query else t.strip()
            for t in texts
        ]

        if self._custom_embed_fn is not None:
            return self._custom_embed_fn(processed)

        if self.use_mock:
            return [
                deterministic_mock_embed(t, dimension=self.vector_store.dimension)
                for t in processed
            ]

        model = self._load_st_model()
        embeddings = model.encode(
            processed,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [list(map(float, vec)) for vec in embeddings]

    def index_chunks(self, chunks: Sequence[Dict[str, Any]]) -> int:
        """
        Nhận danh sách chunk records, lấy đúng trường `embed_text` để tạo vector
        và lưu vào Vector Store kèm toàn bộ metadata và `chunk_text`.
        """
        if not chunks:
            return 0

        embed_texts: List[str] = []
        for idx, ch in enumerate(chunks):
            etext = str(ch.get("embed_text") or "").strip()
            if not etext:
                cid = ch.get("chunk_id") or f"index_{idx}"
                raise ValueError(
                    f"Chunk '{cid}' thiếu trường 'embed_text'. Không được dùng 'chunk_text' hoặc 'text' thay thế."
                )
            embed_texts.append(etext)

        vectors = self.encode_texts(embed_texts, is_query=False)
        return self.vector_store.upsert_chunks(chunks, vectors)

    def search(
        self,
        query: str,
        top_k: int = 5,
        exclude_expired: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Thực hiện Dense Vector Search theo interface chung Sprint 6.
        - Trả về danh sách kết quả đã xếp hạng (rank 1..K).
        - Xử lý top_k không hợp lệ (raise ValueError) và câu hỏi rỗng (trả về []).
        """
        if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k <= 0:
            raise ValueError(f"top_k phải là số nguyên dương lớn hơn 0 (nhận được: {top_k!r}).")

        if query is None or not str(query).strip():
            self.last_latency_ms = {
                "query_encode_ms": 0.0,
                "vector_search_ms": 0.0,
                "total_ms": 0.0,
            }
            return []

        if self.vector_store.count() == 0:
            self.last_latency_ms = {
                "query_encode_ms": 0.0,
                "vector_search_ms": 0.0,
                "total_ms": 0.0,
            }
            return []

        t0 = time.perf_counter()
        query_vec = self.encode_texts([str(query)], is_query=True)[0]
        t1 = time.perf_counter()

        results = self.vector_store.search(
            query_vector=query_vec,
            top_k=top_k,
            exclude_expired=exclude_expired,
        )
        t2 = time.perf_counter()

        self.last_latency_ms = {
            "query_encode_ms": round((t1 - t0) * 1000.0, 3),
            "vector_search_ms": round((t2 - t1) * 1000.0, 3),
            "total_ms": round((t2 - t0) * 1000.0, 3),
        }
        return results

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        query_id: str = "Q_DEV_001",
        exclude_expired: bool = True,
    ) -> Dict[str, Any]:
        """
        Trả về kết quả đóng gói đầy đủ theo Retrieval Result Schema (Mục 4.3 Sprint 6).
        """
        results = self.search(query=query, top_k=top_k, exclude_expired=exclude_expired)
        return {
            "query_id": query_id,
            "retriever": "dense",
            "results": results,
        }