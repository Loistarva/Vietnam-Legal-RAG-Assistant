from __future__ import annotations

import json

import pytest

from schemas.models import RAGOutputRecord
from scripts.enrich_batch_routes import enrich_results


def _record(query_id: str = "Q1") -> dict:
    return RAGOutputRecord(
        query_id=query_id,
        query="Điều kiện kết hôn là gì?",
        as_of_date="2026-10-15",
        as_of_date_source="benchmark",
        answer="",
        grounding_status="ABSTAIN",
        abstained=True,
        abstention_reason="LOW_CONFIDENCE",
        abstention_source="confidence_filter",
        needs_clarification=False,
        prompt_version="v1.2",
        done_reason="not_generated",
        truncated=False,
        corpus_version="corpus-v1",
        retrieval_config_version="retrieval-v1",
        threshold_config_version="threshold-v1",
        latency_ms=1.0,
        llm_calls=0,
    ).model_dump(mode="json")


def test_route_enrichment_writes_separate_validated_handoff(tmp_path):
    source = tmp_path / "source.jsonl"
    output = tmp_path / "handoff" / "results.jsonl"
    source_row = {
        "query_id": "Q1", "as_of_date": "2026-10-15", "status": "SUCCESS",
        "result": _record(),
    }
    source.write_text(json.dumps(source_row, ensure_ascii=False) + "\n", encoding="utf-8")

    summary = enrich_results(source, output)

    enriched = json.loads(output.read_text(encoding="utf-8").splitlines()[0])
    assert enriched["result"]["route"] == "LEGAL_IN_SCOPE"
    assert summary["record_count"] == summary["unique_query_id_count"] == 1
    assert source.read_text(encoding="utf-8").strip() == json.dumps(source_row, ensure_ascii=False)
    with pytest.raises(FileExistsError):
        enrich_results(source, output)


def test_route_enrichment_rejects_mismatched_query_ids(tmp_path):
    source = tmp_path / "source.jsonl"
    source.write_text(json.dumps({
        "query_id": "wrapper-id", "as_of_date": "2026-10-15", "result": _record("result-id"),
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="không khớp"):
        enrich_results(source, tmp_path / "handoff.jsonl")
