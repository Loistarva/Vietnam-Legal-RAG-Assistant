"""Single model registry backed by the validated retrieval configuration.
Owner: Dev 3 (Sprint 9 - Task D3.5).
Consumer: Dev 4 (Qdrant & Vector Indexing).
"""
from __future__ import annotations

from typing import Any

from retrieval.settings import load_settings, validate_settings


class ModelRegistry:
    def __init__(self, config: dict[str, Any] | None = None):
        shared_config = load_settings() if config is None else validate_settings(config)
        self.config = shared_config
        dense = self.config.get("dense")
        if not isinstance(dense, dict) or not isinstance(dense.get("supported_models"), dict):
            raise ValueError("Config thiếu dense.supported_models")
        if not dense.get("collection"):
            raise KeyError("Config thiếu dense.collection")
        self.dense_config = dense
        self.models: dict[str, dict[str, Any]] = dense["supported_models"]

    def get_model(self, model_name: str | None = None) -> dict[str, Any]:
        name = model_name or self.dense_config.get("model")
        if not name or name not in self.models:
            raise ValueError(f"Model chưa được đăng ký trong dense.supported_models: {name!r}")
        spec = {"name": name, **self.models[name]}
        collection = self.dense_config.get("collection")
        if not collection:
            raise KeyError("Config thiếu dense.collection")
        spec["collection_name"] = collection
        return spec

    def get_default_model(self) -> dict[str, Any]:
        return self.get_model()


# =============================================================================
# Helper functions for Dev 4 (Qdrant integration & Precompute)
# =============================================================================

def get_embedding_spec(model_name: str | None = None) -> dict[str, Any]:
    """Lấy đặc tả kỹ thuật mô hình nhúng (dimension, use_word_segmentation, text_field, collection_name)."""
    registry = ModelRegistry()
    spec = registry.get_model(model_name)
    dense_cfg = registry.dense_config

    collection = dense_cfg.get("collection")
    if not collection:
        raise KeyError("Config thiếu dense.collection")

    dimension = spec.get("dimension") or dense_cfg.get("dimension")
    if not dimension:
        raise KeyError(f"Cấu hình thiếu dimension cho model: {spec.get('name')}")

    text_field = spec.get("text_field") or dense_cfg.get("text_field")
    if not text_field:
        raise KeyError(f"Cấu hình thiếu text_field cho model: {spec.get('name')}")

    return {
        "name": spec["name"],
        "dimension": dimension,
        "use_word_segmentation": spec.get("use_word_segmentation", False),
        "text_field": text_field,
        "collection_name": collection,
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


def prepare_text_for_embedding(text: str, model_name: str | None = None) -> str:
    """
    Tiền xử lý văn bản đối xứng trước khi tính vector nhúng:
    Wrapper gọi trực tiếp preprocess_text từ embedding.dense_retriever.
    Tự động kiểm tra cờ use_word_segmentation và ném RuntimeError nếu thiếu underthesea khi yêu cầu tách từ.
    """
    from embedding.dense_retriever import preprocess_text

    spec = get_embedding_spec(model_name)
    use_word_seg = spec.get("use_word_segmentation", False)
    return preprocess_text(
        text=text,
        use_word_segmentation=use_word_seg,
    )


def read_index_metadata() -> dict[str, Any]:
    """
    Trả về thông tin metadata cấu hình chỉ mục (collection, vector_size, dimension, model_name, text_field)
    để Dev 4 xác thực khi dựng và vận hành Qdrant Server.
    """
    registry = ModelRegistry()
    spec = registry.get_default_model()
    return {
        "collection_name": registry.dense_config["collection"],
        "vector_size": spec["dimension"],
        "dimension": spec["dimension"],
        "model_name": spec["name"],
        "use_word_segmentation": spec.get("use_word_segmentation", False),
        "text_field": spec.get("text_field", "embed_text_raw"),
    }
