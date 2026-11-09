"""Confidence Threshold Filter (reranking/confidence.py)."""
from __future__ import annotations

import pytest

from reranking.confidence import ConfidenceConfig, apply_confidence_threshold, load_confidence_config


def rows(*scores):
    return [{"chunk_id": f"c{i}", "reranker_score": s} for i, s in enumerate(scores, 1)]


def test_disabled_passes_everything():
    decision = apply_confidence_threshold(rows(0.01, 0.001), ConfidenceConfig())
    assert decision.status == "ok" and len(decision.kept) == 2


def test_empty_is_empty_even_when_disabled():
    assert apply_confidence_threshold([], ConfidenceConfig()).status == "empty"


def test_low_top1():
    config = ConfidenceConfig(enabled=True, min_top1_score=0.5, threshold_config_version="v")
    decision = apply_confidence_threshold(rows(0.49, 0.2), config)
    assert decision.status == "low_confidence" and decision.kept == [] and decision.top1_score == 0.49


def test_tail_is_dropped():
    config = ConfidenceConfig(enabled=True, min_top1_score=0.5, min_evidence_score=0.3, threshold_config_version="v")
    decision = apply_confidence_threshold(rows(0.9, 0.3, 0.29), config)
    assert [r["chunk_id"] for r in decision.kept] == ["c1", "c2"]
    assert decision.describe()["dropped_chunk_ids"] == ["c3"]


def test_evidence_floor_alone_can_reject_all():
    config = ConfidenceConfig(enabled=True, min_evidence_score=0.5, threshold_config_version="v")
    assert apply_confidence_threshold(rows(0.4), config).status == "low_confidence"


def test_unsorted_and_missing_scores_fail_closed():
    config = ConfidenceConfig(enabled=True, min_top1_score=0.1, threshold_config_version="v")
    with pytest.raises(ValueError, match="giảm dần"):
        apply_confidence_threshold(rows(0.2, 0.9), config)
    with pytest.raises(ValueError, match="reranker_score"):
        apply_confidence_threshold([{"chunk_id": "c1", "score": 0.9}], config)


@pytest.mark.parametrize("kwargs", [
    {"enabled": True, "threshold_config_version": "v"},
    {"min_top1_score": 1.5},
    {"min_top1_score": True},
    {"threshold_config_version": " "},
    {"score_field": "rrf_score"},
])
def test_invalid_config(kwargs):
    with pytest.raises(ValueError):
        ConfidenceConfig(**kwargs)


def test_load_from_yaml(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("confidence:\n  enabled: true\n  min_top1_score: 0.3\n  threshold_config_version: t\n",
                    encoding="utf-8")
    assert load_confidence_config(path).min_top1_score == 0.3
    path.write_text("confidence:\n  typo: 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="typo"):
        load_confidence_config(path)


def test_repo_config_loads():
    config = load_confidence_config()
    assert config.threshold_config_version
