"""Confidence Threshold Filter (architecture: after the Cross-Encoder Reranker, before the
Parent-Context Resolver; "Low Confidence / Rỗng" goes to abstention).

The filter reads the reranker score of the already ranked Top-k results:

* no result at all -> ``empty`` (no generation);
* best score below ``min_top1_score`` -> ``low_confidence`` (no generation);
* otherwise results below ``min_evidence_score`` are dropped. Results are sorted by
  score, so only a tail is removed and the kept rows stay a prefix of the ranking.

LLM Judge and MMR from the diagram are off this sprint (Sprint 9 plan V3). The
values are chosen on the Dev questions outside the 30 official IDs plus Dev 1's
negative set (reports/retrieval/confidence_threshold_dev_calibration.md) and are
recorded as ``threshold_config_version``.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

DEFAULT_CONFIDENCE_CONFIG = Path(__file__).resolve().parent / "confidence.yaml"
CONFIG_KEYS = ("enabled", "score_field", "min_top1_score", "min_evidence_score", "threshold_config_version")
SCORE_FIELDS = ("reranker_score",)


def _optional_unit_score(name: str, value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"confidence.{name} phải là số trong [0, 1] hoặc null")
    if not 0.0 <= float(value) <= 1.0:
        raise ValueError(f"confidence.{name} phải nằm trong [0, 1], nhận được {value}")
    return float(value)


@dataclass(frozen=True)
class ConfidenceConfig:
    enabled: bool = False
    score_field: str = "reranker_score"
    min_top1_score: float | None = None
    min_evidence_score: float | None = None
    threshold_config_version: str = "confidence_off"

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise ValueError("confidence.enabled phải là true/false")
        if self.score_field not in SCORE_FIELDS:
            raise ValueError(f"confidence.score_field phải là một trong {SCORE_FIELDS}")
        object.__setattr__(self, "min_top1_score", _optional_unit_score("min_top1_score", self.min_top1_score))
        object.__setattr__(self, "min_evidence_score",
                           _optional_unit_score("min_evidence_score", self.min_evidence_score))
        if not isinstance(self.threshold_config_version, str) or not self.threshold_config_version.strip():
            raise ValueError("confidence.threshold_config_version không được rỗng")
        if self.enabled and self.min_top1_score is None and self.min_evidence_score is None:
            raise ValueError("confidence.enabled=true cần min_top1_score hoặc min_evidence_score")

    def describe(self) -> dict[str, Any]:
        return {key: getattr(self, key) for key in CONFIG_KEYS}


def load_confidence_config(path: str | Path = DEFAULT_CONFIDENCE_CONFIG, **overrides: Any) -> ConfidenceConfig:
    """Read the ``confidence`` section of reranking/confidence.yaml; unknown keys are rejected."""
    import yaml

    config_path = Path(path)
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"Không đọc được cấu hình {config_path}: {exc}") from exc
    section = data.get("confidence") or {}
    if not isinstance(section, Mapping):
        raise ValueError("confidence phải là YAML mapping")
    unknown = sorted(set(section) - set(CONFIG_KEYS))
    if unknown:
        raise ValueError(f"Khóa lạ trong confidence: {unknown}")
    values = {**section, **{key: value for key, value in overrides.items() if value is not None}}
    return ConfidenceConfig(**values)


@dataclass(frozen=True)
class ConfidenceDecision:
    status: Literal["ok", "empty", "low_confidence"]
    kept: list[dict[str, Any]]
    dropped: list[dict[str, Any]] = field(default_factory=list)
    top1_score: float | None = None

    def describe(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "top1_score": self.top1_score,
            "kept": len(self.kept),
            "dropped_chunk_ids": [row.get("chunk_id") for row in self.dropped],
        }


def _score(row: Mapping[str, Any], score_field: str) -> float:
    value = row.get(score_field)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(
            f"Kết quả {row.get('chunk_id')!r} không có {score_field} dạng số; "
            "ngưỡng tin cậy chỉ áp dụng cho kết quả đã qua Cross-Encoder"
        )
    return float(value)


def apply_confidence_threshold(results: Sequence[Mapping[str, Any]], config: ConfidenceConfig) -> ConfidenceDecision:
    rows = [dict(row) for row in results]
    if not rows:
        return ConfidenceDecision(status="empty", kept=[])
    if not config.enabled:
        top1 = rows[0].get(config.score_field)
        return ConfidenceDecision(status="ok", kept=rows,
                                  top1_score=float(top1) if isinstance(top1, (int, float)) else None)
    scores = [_score(row, config.score_field) for row in rows]
    if any(later > earlier for earlier, later in zip(scores, scores[1:])):
        raise ValueError("Kết quả phải được sắp theo điểm reranker giảm dần trước khi lọc ngưỡng")
    top1 = scores[0]
    if config.min_top1_score is not None and top1 < config.min_top1_score:
        return ConfidenceDecision(status="low_confidence", kept=[], dropped=rows, top1_score=top1)
    floor = config.min_evidence_score
    kept = [row for row, score in zip(rows, scores) if floor is None or score >= floor]
    dropped = rows[len(kept):]
    if not kept:
        return ConfidenceDecision(status="low_confidence", kept=[], dropped=rows, top1_score=top1)
    return ConfidenceDecision(status="ok", kept=kept, dropped=dropped, top1_score=top1)


__all__ = ["DEFAULT_CONFIDENCE_CONFIG", "ConfidenceConfig", "ConfidenceDecision", "apply_confidence_threshold", "load_confidence_config"]
