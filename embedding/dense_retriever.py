# -*- coding: utf-8 -*-
"""
embedding/dense_retriever.py
Triển khai DenseRetriever tuân thủ Data Contract Sprint 6.
"""
from __future__ import annotations

import hashlib
import math
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from embedding.vector_store import LegalVectorStore

try:
    from underthesea import word_tokenize

    HAS_UNDERTHESEA = True
except ImportError:
    HAS_UNDERTHESEA = False


MODEL_SPECS: Dict[str, Dict[str, Any]] = {
    "BAAI/bge-m3": {
        "dimension": 1024,
        "use_word_segmentation": False,
        "text_field": "embed_text_raw",
    },
    "bkai-foundation-models/vietnamese-bi-encoder": {
        "dimension": 768,
        "use_word_segmentation": True,
        "text_field": "embed_text",
    },
    "AITeamVN/Vietnamese_Embedding": {
        "dimension": 1024,
        "use_word_segmentation": False,
        "text_field": "embed_text_raw",
    },
}

MODEL_DIMENSIONS: Dict[str, int] = {k: v["dimension"] for k, v in MODEL_SPECS.items()}


def load_dense_retrieval_config(config_path: str | Path | None = None) -> Dict[str, Any]:
    """Đọc cấu hình dense từ retrieval/config.yaml nếu có."""
    if config_path is None:
        p = Path(__file__).resolve().parent.parent / "retrieval" / "config.yaml"
    else:
        p = Path(config_path)
    if p.is_file():
        try:
            import yaml

            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            dense_cfg = data.get("dense") or {}
            if isinstance(dense_cfg, dict):
                return dense_cfg
        except Exception:
            pass
    return {}


_DENSE_CONFIG = load_dense_retrieval_config()
DEFAULT_MODEL_NAME = _DENSE_CONFIG.get("model", "BAAI/bge-m3")


def get_model_spec(model_name: str) -> Dict[str, Any]:
    """Lấy thông số chuẩn (dimension, use_word_segmentation, text_field) cho model."""
    if model_name in MODEL_SPECS:
        return dict(MODEL_SPECS[model_name])
    is_bkai = "vietnamese-bi-encoder" in model_name.lower() or "bkai" in model_name.lower()
    return {
        "dimension": 768 if is_bkai else 1024,
        "use_word_segmentation": is_bkai,
        "text_field": "embed_text" if is_bkai else "embed_text_raw",
    }


def preprocess_text(
    text: str,
    is_already_segmented: bool = False,
    use_word_segmentation: bool = False,
    use_mock: bool = False,
) -> str:
    """
    Tiền xử lý văn bản dùng chung cho Query và Corpus:
    - Nếu use_word_segmentation=True: phân tách từ bằng underthesea (báo lỗi dừng ngay nếu thiếu thư viện).
    - Nếu use_word_segmentation=False: chuẩn hóa khoảng trắng, giữ nguyên văn bản thô.
    """
    cleaned = " ".join(str(text or "").strip().split())
    if not cleaned:
        return ""

    if not use_word_segmentation:
        return cleaned

    if is_already_segmented or "_" in cleaned:
        return cleaned

    if not HAS_UNDERTHESEA:
        if not use_mock:
            raise RuntimeError(
                "Model yêu cầu tách từ tiếng Việt (use_word_segmentation=True) nhưng thiếu thư viện 'underthesea'."
            )
        return cleaned

    return word_tokenize(cleaned, format="text")


def deterministic_mock_embed(text: str, dimension: int = 1024) -> List[float]:
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
    - Đồng bộ lựa chọn text field (embed_text vs embed_text_raw) và word segmentation theo model.
    - Trả chunk_text, chunk_id, parent_clause_id, document_id, rank, score, metadata.
    - Hỗ trợ đo latency và chạy độc lập với Mock Embedder hoặc SentenceTransformer.
    """

    def __init__(
        self,
        vector_store: LegalVectorStore,
        model_name: str = DEFAULT_MODEL_NAME,
        embed_fn: Optional[Callable[[Sequence[str]], List[List[float]]]] = None,
        use_mock: bool = False,
        use_word_segmentation: Optional[bool] = None,
        text_field: Optional[str] = None,
        batch_size: int = 32,
    ) -> None:
        self.vector_store = vector_store
        self.model_name = model_name
        self.batch_size = batch_size
        self.use_mock = use_mock or (embed_fn is not None)
        self._custom_embed_fn = embed_fn
        self._st_model: Optional[Any] = None

        spec = get_model_spec(model_name)
        if use_word_segmentation is None:
            self.use_word_segmentation = spec["use_word_segmentation"]
        else:
            self.use_word_segmentation = use_word_segmentation

        self.text_field = text_field or spec["text_field"]

        # Fail-fast: nếu model yêu cầu tách từ mà không có underthesea ở chế độ thật (Lỗi E4 & H8)
        if self.use_word_segmentation and not self.use_mock:
            if not HAS_UNDERTHESEA:
                raise RuntimeError(
                    "Model yêu cầu tách từ tiếng Việt (use_word_segmentation=True) nhưng thiếu thư viện 'underthesea'."
                )

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
        return preprocess_text(
            query,
            is_already_segmented=False,
            use_word_segmentation=self.use_word_segmentation,
            use_mock=self.use_mock,
        )

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
        Nhận danh sách chunk records, chọn đúng trường văn bản (embed_text hoặc embed_text_raw)
        theo cấu hình model để tạo vector và lưu vào Vector Store kèm toàn bộ metadata và chunk_text.
        """
        if not chunks:
            return 0

        embed_texts: List[str] = []
        for idx, ch in enumerate(chunks):
            # Kiểm tra chunk_text hợp lệ
            chunk_text = str(ch.get("chunk_text") or "").strip()
            if not chunk_text:
                cid = ch.get("chunk_id") or ch.get("id") or f"index_{idx}"
                raise ValueError(
                    f"Chunk '{cid}' thiếu 'chunk_text' (không được dùng 'text' thay cho 'chunk_text')."
                )

            # Lấy trường embed text
            raw_field = str(ch.get("embed_text_raw") or "").strip()
            seg_field = str(ch.get("embed_text") or "").strip()

            if not raw_field and not seg_field:
                cid = ch.get("chunk_id") or ch.get("id") or f"index_{idx}"
                raise ValueError(
                    f"Chunk '{cid}' thiếu trường 'embed_text'. Không được dùng 'chunk_text' hoặc 'text' thay thế."
                )

            if self.use_word_segmentation:
                if seg_field:
                    text_to_encode = seg_field
                else:
                    text_to_encode = preprocess_text(
                        raw_field,
                        is_already_segmented=False,
                        use_word_segmentation=True,
                        use_mock=self.use_mock,
                    )
            else:
                if raw_field:
                    text_to_encode = raw_field
                else:
                    text_to_encode = seg_field.replace("_", " ")

            embed_texts.append(text_to_encode)

        vectors = self.encode_texts(embed_texts, is_query=False)
        return self.vector_store.upsert_chunks(chunks, vectors)

    def search(
        self,
        query: str,
        top_k: int = 5,
        exclude_expired: bool = True,
        as_of_date: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
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
            as_of_date=as_of_date,
            filters=filters,
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
        as_of_date: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Trả về kết quả đóng gói đầy đủ theo Retrieval Result Schema (Mục 4.3 Sprint 6).
        """
        results = self.search(
            query=query,
            top_k=top_k,
            exclude_expired=exclude_expired,
            as_of_date=as_of_date,
            filters=filters,
        )
        return {
            "query_id": query_id,
            "retriever": "dense",
            "results": results,
        }
