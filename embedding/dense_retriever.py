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

from embedding.vector_store import LegalVectorStore, chunk_file_sha256, read_index_metadata
from embedding.model_registry import ModelRegistry
from retrieval.settings import load_settings

try:
    from underthesea import word_tokenize

    HAS_UNDERTHESEA = True
except ImportError:
    HAS_UNDERTHESEA = False


SPEC_KEYS = ("dimension", "use_word_segmentation", "text_field")


def load_dense_retrieval_config(config_path: str | Path | None = None) -> Dict[str, Any]:
    """Compatibility wrapper over the shared validated Retrieval settings loader."""
    return load_settings(config_path)["dense"]


def load_model_specs(dense_cfg: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Bảng model lấy từ dense.supported_models của config, nguồn duy nhất (E2)."""
    specs: Dict[str, Dict[str, Any]] = {}
    for name, spec in (dense_cfg.get("supported_models") or {}).items():
        missing = [k for k in SPEC_KEYS if not isinstance(spec, dict) or k not in spec]
        if missing:
            raise ValueError(f"dense.supported_models.{name} thiếu khoá {missing}")
        specs[name] = {k: spec[k] for k in SPEC_KEYS}
    return specs


_DENSE_CONFIG = load_dense_retrieval_config()
MODEL_REGISTRY = ModelRegistry()
MODEL_SPECS: Dict[str, Dict[str, Any]] = load_model_specs(_DENSE_CONFIG)
MODEL_DIMENSIONS: Dict[str, int] = {k: v["dimension"] for k, v in MODEL_SPECS.items()}
DEFAULT_MODEL_NAME = MODEL_REGISTRY.get_default_model()["name"]


def get_model_spec(model_name: str) -> Dict[str, Any]:
    """Lấy thông số (dimension, use_word_segmentation, text_field) của model trong config."""
    model = MODEL_REGISTRY.get_model(model_name)
    return {key: model[key] for key in SPEC_KEYS}


def preprocess_text(
    text: str,
    is_already_segmented: bool = False,
    use_word_segmentation: bool = False,
    use_mock: bool = False,
) -> str:
    """
    Tiền xử lý văn bản dùng chung cho Query và Corpus:
    - Nếu use_word_segmentation=True: phân tách từ bằng underthesea (báo lỗi dừng ngay nếu thiếu thư viện).
      Chuỗi có sẵn dấu "_" vẫn được tách từ; chỉ bỏ qua khi is_already_segmented=True.
    - Nếu use_word_segmentation=False: chuẩn hóa khoảng trắng, giữ nguyên văn bản thô.
    """
    cleaned = " ".join(str(text or "").strip().split())
    if not cleaned:
        return ""

    if not use_word_segmentation:
        return cleaned

    if is_already_segmented:
        return cleaned

    if not HAS_UNDERTHESEA:
        if not use_mock:
            raise RuntimeError(
                "Model yêu cầu tách từ tiếng Việt (use_word_segmentation=True) nhưng thiếu thư viện 'underthesea'."
            )
        return cleaned

    return word_tokenize(cleaned, format="text")


def underthesea_version() -> Optional[str]:
    """Phiên bản underthesea đang cài, ghi vào metadata index của model cần tách từ."""
    if not HAS_UNDERTHESEA:
        return None
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("underthesea")
    except PackageNotFoundError:
        return None


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
        model_name: str | None = None,
        embed_fn: Optional[Callable[[Sequence[str]], List[List[float]]]] = None,
        use_mock: bool = False,
        use_word_segmentation: Optional[bool] = None,
        text_field: Optional[str] = None,
        batch_size: int = 32,
        corpus_path: str | Path | None = None,
        settings: Dict[str, Any] | None = None,
    ) -> None:
        self.vector_store = vector_store
        self.batch_size = batch_size
        self.settings = settings if settings is not None else load_settings()
        self.model_registry = ModelRegistry(self.settings)
        self.model_name = model_name or self.settings["dense"]["model"]
        configured_corpus = self.settings["retrieval"]["corpus_path"]
        self.corpus_path = (
            Path(corpus_path) if corpus_path is not None
            else Path(__file__).resolve().parents[1] / configured_corpus
        )
        self.use_mock = use_mock or (embed_fn is not None)
        self._custom_embed_fn = embed_fn
        self._st_model: Optional[Any] = None

        model_spec = self.model_registry.get_model(self.model_name)
        spec = {key: model_spec[key] for key in SPEC_KEYS}
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

        # In real embedding mode the collection dimension must be the model's true output
        # dimension. Mock/custom embedders intentionally remain free to use test dimensions.
        if not self.use_mock and vector_store.dimension != spec["dimension"]:
            raise ValueError(
                f"Dimension VectorStore ({vector_store.dimension}) không khớp model "
                f"{self.model_name!r} ({spec['dimension']})"
            )

        self.last_latency_ms: Dict[str, float] = {
            "query_encode_ms": 0.0,
            "vector_search_ms": 0.0,
            "total_ms": 0.0,
        }

        # Mở collection có sẵn để truy vấn: kiểm metadata do build_index.py ghi (E2)
        if getattr(vector_store, "persistent", False) and not vector_store.create_if_missing:
            self.verify_index()

    def verify_index(self, corpus_sha256: Optional[str] = None) -> Dict[str, Any]:
        """
        So metadata của collection (build_index.py ghi) với model đang dùng; lệch thì raise ValueError.
        Truyền corpus_sha256 để so luôn hash của file chunk đã index.
        """
        store = self.vector_store
        meta = read_index_metadata(store.storage_path, store.collection_name)
        if meta is None:
            raise ValueError(
                f"Collection '{store.collection_name}' không có file metadata; dựng lại bằng scripts/build_index.py."
            )
        expected: Dict[str, Any] = {
            "model_name": self.model_name,
            "dimension": store.dimension,
            "use_word_segmentation": self.use_word_segmentation,
            "text_field": self.text_field,
            "collection_name": store.collection_name,
            "chunk_count": store.count(),
            "mock_mode": self.use_mock,
        }
        stored_hash = meta.get("corpus_sha256")
        if not isinstance(stored_hash, str) or len(stored_hash) != 64:
            raise ValueError(
                f"Collection '{store.collection_name}' thiếu corpus_sha256 hợp lệ trong metadata; "
                "dựng lại bằng scripts/build_index.py."
            )
        if self.use_word_segmentation:
            expected["underthesea_version"] = underthesea_version()
        if corpus_sha256 is not None:
            expected["corpus_sha256"] = corpus_sha256
        else:
            if not self.corpus_path.is_file():
                raise ValueError(
                    f"Không tìm thấy corpus để xác minh metadata Dense: {self.corpus_path}. "
                    "Truyền corpus_sha256 đã xác minh hoặc cập nhật retrieval.corpus_path."
                )
            expected["corpus_sha256"] = chunk_file_sha256(self.corpus_path)
        mismatched = {k: (meta.get(k), v) for k, v in expected.items() if meta.get(k) != v}
        if mismatched:
            details = "; ".join(f"{k}: index {a!r}, hiện tại {b!r}" for k, (a, b) in mismatched.items())
            raise ValueError(
                f"Collection '{store.collection_name}' không khớp cấu hình ({details}); "
                "dựng lại bằng scripts/build_index.py."
            )
        return meta

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

    def corpus_text(self, chunk: Dict[str, Any]) -> str:
        """
        Văn bản đưa vào encode ở phía corpus: self.text_field (embed_text_raw ở mọi model trong
        config), thiếu thì lấy embed_text bỏ dấu "_". Model cần tách từ thì tách chuỗi này bằng
        cùng preprocess_text với câu hỏi (E4), không dùng embed_text do chunker tách theo từng phần.
        """
        text = str(chunk.get(self.text_field) or "").strip()
        if not text:
            text = str(chunk.get("embed_text_raw") or "").strip()
        if not text:
            text = str(chunk.get("embed_text") or "").strip().replace("_", " ")
        if self.use_word_segmentation:
            return preprocess_text(text, use_word_segmentation=True, use_mock=self.use_mock)
        return text

    def index_chunks(self, chunks: Sequence[Dict[str, Any]]) -> int:
        """
        Nhận danh sách chunk records, tạo vector từ corpus_text và lưu vào Vector Store
        kèm toàn bộ metadata và chunk_text.
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

            if not str(ch.get("embed_text_raw") or "").strip() and not str(ch.get("embed_text") or "").strip():
                cid = ch.get("chunk_id") or ch.get("id") or f"index_{idx}"
                raise ValueError(
                    f"Chunk '{cid}' thiếu trường 'embed_text'. Không được dùng 'chunk_text' hoặc 'text' thay thế."
                )

            embed_texts.append(self.corpus_text(ch))

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
        - Trả về danh sách kết quả đã xếp hạng (rank 1..K); store rỗng thì trả [].
        - top_k không hợp lệ hoặc câu hỏi rỗng thì raise ValueError như BM25 và Hybrid (E14).
        """
        if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k <= 0:
            raise ValueError(f"top_k phải là số nguyên dương lớn hơn 0 (nhận được: {top_k!r}).")

        if query is None or not str(query).strip():
            raise ValueError("Câu hỏi không được rỗng.")

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
