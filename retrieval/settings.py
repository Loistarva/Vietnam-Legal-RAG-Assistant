"""Validated shared settings for Retrieval and Dense model configuration."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "retrieval" / "config.yaml"
MODEL_SPEC_KEYS = ("dimension", "use_word_segmentation", "text_field")


def _positive_int(value: Any, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{name} phải là số nguyên dương")
    return value


def validate_settings(config: Any) -> dict[str, Any]:
    """Validate schema and cross-field constraints, returning the original mapping."""
    if not isinstance(config, dict):
        raise ValueError("Config phải là YAML mapping")
    required_sections = ("retrieval", "bm25", "dense", "hybrid")
    for section in required_sections:
        if not isinstance(config.get(section), dict):
            raise ValueError(f"Config thiếu section mapping {section!r}")

    retrieval = config["retrieval"]
    retrieval_k = _positive_int(retrieval.get("retrieval_top_k"), "retrieval.retrieval_top_k")
    result_k = _positive_int(retrieval.get("result_top_k"), "retrieval.result_top_k")
    if not isinstance(retrieval.get("corpus_path"), str) or not retrieval["corpus_path"].strip():
        raise ValueError("retrieval.corpus_path phải có giá trị không rỗng")
    if result_k > retrieval_k:
        raise ValueError("retrieval.result_top_k không được lớn hơn retrieval.retrieval_top_k")

    bm25 = config["bm25"]
    for key in ("backend", "index", "text_field", "tokenizer", "tokenizer_version"):
        if not isinstance(bm25.get(key), (str, int)) or not str(bm25[key]).strip():
            raise ValueError(f"bm25.{key} phải có giá trị không rỗng")

    dense = config["dense"]
    models = dense.get("supported_models")
    if not isinstance(models, dict) or not models:
        raise ValueError("dense.supported_models phải là mapping model không rỗng")
    for name, spec in models.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(spec, dict):
            raise ValueError("Mỗi dense.supported_models entry phải là model name và mapping")
        missing = [key for key in MODEL_SPEC_KEYS if key not in spec]
        if missing:
            raise ValueError(f"dense.supported_models.{name} thiếu khóa {missing}")
        _positive_int(spec["dimension"], f"dense.supported_models.{name}.dimension")
        if not isinstance(spec["use_word_segmentation"], bool):
            raise ValueError(f"dense.supported_models.{name}.use_word_segmentation phải là boolean")
        if not isinstance(spec["text_field"], str) or not spec["text_field"].strip():
            raise ValueError(f"dense.supported_models.{name}.text_field phải có giá trị")

    model_name = dense.get("model")
    if model_name not in models:
        raise ValueError(f"Model Dense chưa được đăng ký: {model_name!r}")
    dimension = _positive_int(dense.get("dimension"), "dense.dimension")
    if dimension != models[model_name]["dimension"]:
        raise ValueError(
            f"dense.dimension={dimension} không khớp model {model_name!r} "
            f"(dimension={models[model_name]['dimension']})"
        )
    for key in ("backend", "collection"):
        if not isinstance(dense.get(key), str) or not dense[key].strip():
            raise ValueError(f"dense.{key} phải có giá trị không rỗng")

    hybrid = config["hybrid"]
    if hybrid.get("fusion") != "rrf":
        raise ValueError("hybrid.fusion hiện chỉ hỗ trợ 'rrf'")
    _positive_int(hybrid.get("rrf_k"), "hybrid.rrf_k")
    if "candidate_k" in hybrid or "top_k" in hybrid:
        raise ValueError(
            "Không khai báo hybrid.candidate_k/top_k; dùng retrieval.retrieval_top_k "
            "và retrieval.result_top_k làm nguồn cấu hình duy nhất"
        )
    return config


def load_settings(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load and validate the shared YAML settings; invalid files fail fast."""
    path = Path(config_path) if config_path is not None else DEFAULT_CONFIG_PATH
    if not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy config: {path}")
    try:
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"Không đọc được config YAML {path}: {exc}") from exc
    return validate_settings(config)
