"""Single model registry backed by the validated retrieval configuration.
Owner: Dev 3 (Sprint 9 - Task D3.5).
Consumer: Dev 4 (Qdrant & Vector Indexing).
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

from retrieval.settings import load_settings, validate_settings

try:
    from underthesea import word_tokenize
    HAS_UNDERTHESEA = True
except ImportError:
    HAS_UNDERTHESEA = False

_SHARED_CONFIG = load_settings()
DEFAULT_DENSE_COLLECTION = _SHARED_CONFIG["dense"]["collection"]

DEFAULT_PRODUCTION_MODEL = "BAAI/bge-m3"
DEFAULT_DIMENSION = 1024
DEFAULT_COLLECTION_NAME = "legal_corpus_bge_m3"
DEFAULT_TEXT_FIELD = "embed_text_raw"
DEFAULT_USE_WORD_SEG = False


class ModelRegistry:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = validate_settings(config) if config is not None else _SHARED_CONFIG
        dense = self.config.get("dense")
        if not isinstance(dense, dict) or not isinstance(dense.get("supported_models"), dict):
            raise ValueError("Config thiếu dense.supported_models")
        self.dense_config = dense
        self.models: dict[str, dict[str, Any]] = dense["supported_models"]

    def get_model(self, model_name: str | None = None) -> dict[str, Any]:
        name = model_name or self.dense_config.get("model")
        if name not in self.models:
            raise ValueError(f"Model chưa được đăng ký trong dense.supported_models: {name!r}")
        spec = {"name": name, **self.models[name]}
        if "collection_name" not in spec:
            spec["collection_name"] = (
                DEFAULT_COLLECTION_NAME if name == DEFAULT_PRODUCTION_MODEL else self.dense_config.get("collection", DEFAULT_DENSE_COLLECTION)
            )
        return spec

    def get_default_model(self) -> dict[str, Any]:
        return self.get_model()


# =============================================================================
# Helper functions for Dev 4 (Qdrant integration & Precompute)
# =============================================================================

def get_embedding_spec(model_name: Optional[str] = None) -> Dict[str, Any]:
    """Lấy đặc tả kỹ thuật mô hình nhúng (dimension, use_word_segmentation, text_field, collection_name)."""
    registry = ModelRegistry()
    spec = registry.get_model(model_name)
    return {
        "name": spec["name"],
        "dimension": spec["dimension"],
        "use_word_segmentation": spec.get("use_word_segmentation", False),
        "text_field": spec.get("text_field", DEFAULT_TEXT_FIELD),
        "collection_name": spec.get("collection_name", DEFAULT_COLLECTION_NAME),
    }


def validate_collection_dimension(model_name: str, actual_dimension: int) -> bool:
    """
    Kiểm tra chiều vector của collection Qdrant có khớp với đặc tả mô hình của Dev 3 không.
    Ném ValueError nếu lệch chiều để fail-fast.
    """
    spec = get_embedding_spec(model_name)
    expected_dim = spec["dimension"]
    if actual_dimension != expected_dim:
        raise ValueError(
            f"Lệch chiều vector đối với mô hình {model_name}: "
            f"đặc tả yêu cầu {expected_dim}, nhưng collection thực tế có {actual_dimension}"
        )
    return True


def prepare_text_for_embedding(text: str, model_name: Optional[str] = None) -> str:
    """
    Tiền xử lý văn bản đối xứng trước khi tính vector nhúng:
    - Nếu mô hình yêu cầu word_segmentation=True: áp dụng word_tokenize (underthesea)
    - Nếu mô hình dùng raw text (BAAI/bge-m3): chuẩn hóa khoảng trắng thừa và giữ nguyên từ tự nhiên.
    """
    cleaned = re.sub(r"\s+", " ", text.strip())
    spec = get_embedding_spec(model_name)
    if spec.get("use_word_segmentation", False):
        if HAS_UNDERTHESEA:
            return word_tokenize(cleaned, format="text")
        return cleaned
    return cleaned
