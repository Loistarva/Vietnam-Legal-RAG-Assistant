import json
import re
import unicodedata
from pathlib import Path

import pytest

from grounding.citation_validator import validate_citations
from schemas.models import ContextPayload, MappedCitation

ROOT = Path(__file__).resolve().parents[2]
CASES = [json.loads(line) for line in (ROOT / "evaluation/quality/grounding_cases_sprint11.jsonl").read_text("utf8").splitlines()]


def fixture():
    ctx = ContextPayload.model_validate_json((ROOT / "test/fixtures/grounding/sprint11/base_context.json").read_text("utf8"))
    item = ctx.evidence_items[0]
    citation = MappedCitation(**{k: getattr(item, k) for k in
                               ("evidence_index", "chunk_id", "parent_clause_id", "document_id", "article_id", "clause_id")})
    return ctx, citation


@pytest.mark.parametrize("case", CASES, ids=[r["id"] for r in CASES])
def test_synthetic_cases(case):
    ctx, c = fixture()
    item = ctx.evidence_items[0]
    indices, citations = [1], [c]
    mutation = case["mutation"]
    if mutation == "start_inclusive":
        ctx.as_of_date = "2020-01-01"
    elif mutation == "end_exclusive":
        ctx.as_of_date = "2027-01-01"
    elif mutation == "before_start":
        ctx.as_of_date = "2019-12-31"
    elif mutation == "historical":
        ctx.as_of_date = "2021-01-01"
        item.validity_status = ctx.source_map[1]["validity_status"] = "expired"
    elif mutation == "empty_context":
        ctx.evidence_items = []
    elif mutation == "missing_citations":
        indices, citations = [], []
    elif mutation == "duplicate_indices":
        indices = [1, 1]
    elif mutation == "outside_context":
        indices, c.evidence_index = [2], 2
    elif mutation == "citation_metadata":
        c.document_id = "ANOTHER_SYNTHETIC_DOC"
    elif mutation == "source_metadata":
        ctx.source_map[1]["chunk_id"] = "ANOTHER_SYNTHETIC_CHILD"
    elif mutation == "bad_index":
        indices = [0]
    elif mutation == "temporal_map":
        ctx.source_map[1]["effective_to"] = "2025-01-01"
    elif mutation == "invalid_interval":
        item.effective_to = ctx.source_map[1]["effective_to"] = item.effective_from
    elif mutation == "invalid_as_of":
        ctx.as_of_date = "2026-99-01"
    elif mutation == "noncontiguous":
        item.evidence_index = 2
    elif mutation == "bad_effective_date":
        item.effective_from = ctx.source_map[1]["effective_from"] = "not-a-date"
    elif mutation == "empty_content":
        item.content = " "
    result = validate_citations(ctx, citations, evidence_indices=indices)
    assert result.status == case["expected_status"]
    assert result.reason == case["expected_code"]
    assert result.violation_codes == ([] if result.status == "PASS" else [case["expected_code"]])
    assert result.validated_answer is None  # Validator never releases a generated answer.
    assert not result.unsupported_claims  # No semantic hallucination judgement.


@pytest.mark.parametrize("field", ["validity_status", "source_url", "document_number", "document_title",
                                   "article_number", "clause_number", "breadcrumb", "provision_status"])
def test_displayed_source_metadata_cannot_be_tampered(field):
    ctx, c = fixture()
    ctx.source_map[1][field] = "tampered"
    assert validate_citations(ctx, [c], evidence_indices=[1]).reason == "SOURCE_MAP_METADATA_MISMATCH"


def test_uncited_expired_context_is_also_rejected():
    ctx, c = fixture()
    item = ctx.evidence_items[0].model_copy(update={"evidence_index": 2, "effective_to": "2021-01-01"})
    ctx = ContextPayload(query_id=ctx.query_id, query=ctx.query, as_of_date=ctx.as_of_date,
                         as_of_date_source=ctx.as_of_date_source, evidence_items=[ctx.evidence_items[0], item])
    assert validate_citations(ctx, [c], evidence_indices=[1]).reason == "EVIDENCE_EXPIRED_AS_OF_DATE"


def test_legacy_undated_evidence_does_not_invent_validity_dates():
    ctx, c = fixture()
    for name in ("effective_from", "effective_to"):
        setattr(ctx.evidence_items[0], name, None)
        ctx.source_map[1][name] = None
    result = validate_citations(ctx, [c], evidence_indices=[1])
    assert result.status == "PASS"  # Structural only, not proof of current legal effectivity.


def normalize(text):
    text = unicodedata.normalize("NFKD", text.casefold().replace("đ", "d"))
    return " ".join(re.findall(r"\w+", "".join(c for c in text if not unicodedata.combining(c))))


def queries(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"question", "query"} and isinstance(item, str):
                yield normalize(item)
            elif isinstance(item, (dict, list)):
                yield from queries(item)
    elif isinstance(value, list):
        for item in value:
            yield from queries(item)


def test_fixture_ids_labels_and_no_query_overlap_with_benchmark_negative_holdout():
    assert len(CASES) == 18 and len({r["id"] for r in CASES}) == 18
    fixture_queries = {normalize(r["query"]) for r in CASES}
    assert len(fixture_queries) == len(CASES)
    scanned = []
    paths = list((ROOT / "data/benchmark").glob("queries_*.json"))
    paths += list((ROOT / "evaluation/negative_set").glob("*queries*.jsonl"))
    paths += [p for p in (ROOT / "evaluation").rglob("*.jsonl") if "holdout" in str(p).casefold()]
    for path in paths:
        text = path.read_text("utf-8-sig")
        values = [json.loads(line) for line in text.splitlines() if line.strip()] if path.suffix == ".jsonl" else json.loads(text)
        assert fixture_queries.isdisjoint(set(queries(values))), str(path)
        scanned.append(path)
    assert any(p.name == "queries_dev.json" for p in scanned)
    assert any("negative" in str(p) for p in scanned)
    assert all(r["origin"] == "synthetic_authored_sprint11" and r["semantic_assessment"] == "not_performed" for r in CASES)
