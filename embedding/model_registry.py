"""Single model registry backed by the validated retrieval configuration."""
from __future__ import annotations

from typing import Any

from retrieval.settings import load_settings, validate_settings

_SHARED_CONFIG = load_settings()
DEFAULT_DENSE_COLLECTION = _SHARED_CONFIG["dense"]["collection"]


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
        return {"name": name, **self.models[name]}

    def get_default_model(self) -> dict[str, Any]:
        return self.get_model()
