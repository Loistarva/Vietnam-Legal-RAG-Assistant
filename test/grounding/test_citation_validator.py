from copy import deepcopy

import pytest

from grounding.citation_validator import validate_citations
from schemas.models import ContextPayload, EvidenceItem, MappedCitation


def fixture_pair():
    item = EvidenceItem(evidence_index=1, chunk_id="child-1", parent_clause_id="parent-1",
                        document_id="doc-1", article_id="article-1", clause_id="clause-1",
                        content="The selected expanded parent text.", validity_status="valid")
    ctx = ContextPayload(query_id="dev-1", query="question", as_of_date="2026-11-07",
                         as_of_date_source="benchmark", evidence_items=[item])
    citation = MappedCitation(**{k: getattr(item, k) for k in
        ("evidence_index", "chunk_id", "parent_clause_id", "document_id", "article_id", "clause_id")})
    return ctx, citation


def check(ctx, citations, reason, indices=(1,), invalid=()):
    result = validate_citations(ctx, citations, evidence_indices=indices, invalid_indices=invalid)
    assert result.reason == reason
    assert result.grounding_status == "FAIL"
    assert not result.is_grounded
    assert not result.valid_citations


def test_pass_and_no_mutation():
    ctx, c = fixture_pair()
    before = deepcopy((ctx.model_dump(), c.model_dump()))
    result = validate_citations(ctx, [c], evidence_indices=[1])
    assert result.grounding_status == "PASS" and result.is_grounded
    assert result.valid_citations == [c]
    assert before == (ctx.model_dump(), c.model_dump())
    assert not result.unsupported_claims


@pytest.mark.parametrize("field", ["chunk_id", "document_id", "article_id", "clause_id", "parent_clause_id"])
@pytest.mark.parametrize("location", ["citation", "source_map"])
def test_each_provenance_field(field, location):
    ctx, c = fixture_pair()
    if location == "citation":
        setattr(c, field, "wrong")
        reason = "CITATION_PROVENANCE_MISMATCH"
    else:
        ctx.source_map[1][field] = "wrong"
        reason = "SOURCE_MAP_PROVENANCE_MISMATCH"
    check(ctx, [c], reason)


@pytest.mark.parametrize("index", [0, 6, -1, True, False, "1", 1.0, None])
def test_invalid_raw_indices(index):
    ctx, c = fixture_pair()
    check(ctx, [c], "INVALID_EVIDENCE_INDEX", [index])


def test_mapper_failures_cannot_disappear():
    ctx, c = fixture_pair()
    check(ctx, [c], "MAPPER_INVALID_INDICES", [1, 5], [5])


@pytest.mark.parametrize("missing", ["indices", "citations", "both"])
def test_empty_citations_fail(missing):
    ctx, c = fixture_pair()
    check(ctx, [] if missing != "indices" else [c], "MISSING_CITATIONS",
          [] if missing != "citations" else [1])


def test_empty_context():
    ctx, c = fixture_pair()
    ctx.evidence_items = []
    check(ctx, [c], "EMPTY_CONTEXT")


def test_duplicate_context_indices():
    ctx, c = fixture_pair()
    ctx.evidence_items.append(deepcopy(ctx.evidence_items[0]))
    check(ctx, [c], "DUPLICATE_CONTEXT_INDEX")


@pytest.mark.parametrize("key", ["extra", "missing", "string"])
def test_source_map_keys(key):
    ctx, c = fixture_pair()
    if key == "extra":
        ctx.source_map[2] = deepcopy(ctx.source_map[1])
    elif key == "missing":
        ctx.source_map = {}
    else:
        ctx.source_map = {"1": ctx.source_map[1]}
    check(ctx, [c], "SOURCE_MAP_INDEX_MISMATCH")


def test_duplicate_request_and_citation_indices():
    ctx, c = fixture_pair()
    check(ctx, [c], "DUPLICATE_EVIDENCE_INDEX", [1, 1])
    check(ctx, [c, c], "DUPLICATE_CITATION_INDEX")


def test_dropped_mapping_and_outside_context():
    ctx, c = fixture_pair()
    check(ctx, [c], "CITATION_INDEX_SET_MISMATCH", [1, 2])
    c.evidence_index = 2
    check(ctx, [c], "CITATION_OUTSIDE_CONTEXT", [2])


def test_parent_id_cannot_replace_selected_chunk():
    ctx, c = fixture_pair()
    c.chunk_id = c.parent_clause_id
    check(ctx, [c], "CITATION_PROVENANCE_MISMATCH")


def test_multiple_items_sorted_and_subset_allowed():
    ctx, c = fixture_pair()
    second = ctx.evidence_items[0].model_copy(update={"evidence_index": 2, "chunk_id": "child-2"})
    ctx = ContextPayload(query_id=ctx.query_id, query=ctx.query, as_of_date=ctx.as_of_date,
                         as_of_date_source=ctx.as_of_date_source,
                         evidence_items=[ctx.evidence_items[0], second])
    c2 = c.model_copy(update={"evidence_index": 2, "chunk_id": "child-2"})
    result = validate_citations(ctx, [c2, c], evidence_indices=[2, 1])
    assert [x.evidence_index for x in result.valid_citations] == [1, 2]
    assert validate_citations(ctx, [c2], evidence_indices=[2]).is_grounded


def test_bad_types():
    ctx, c = fixture_pair()
    check({}, [c], "INVALID_CONTEXT_TYPE")
    check(ctx, [{}], "INVALID_CITATION_TYPE")


@pytest.mark.parametrize("field", ["content", "chunk_id", "parent_clause_id", "document_id", "article_id", "clause_id"])
def test_mutated_empty_evidence(field):
    ctx, c = fixture_pair()
    setattr(ctx.evidence_items[0], field, " ")
    check(ctx, [c], "EMPTY_EVIDENCE_FIELD")


def test_mutated_index_and_oversized_context():
    ctx, c = fixture_pair()
    ctx.evidence_items[0].evidence_index = True
    check(ctx, [c], "INVALID_CONTEXT_INDEX")
    ctx, c = fixture_pair()
    ctx.evidence_items *= 6
    check(ctx, [c], "TOO_MANY_EVIDENCE_ITEMS")


def test_actual_dev3_mapper_integration():
    from generation.prompt_builder import map_evidence_indices_to_citations
    ctx, _ = fixture_pair()
    citations, invalid = map_evidence_indices_to_citations([1], ctx)
    assert validate_citations(ctx, citations, evidence_indices=[1], invalid_indices=invalid).is_grounded
    citations, invalid = map_evidence_indices_to_citations([1, 5], ctx)
    check(ctx, citations, "MAPPER_INVALID_INDICES", [1, 5], invalid)
    # Even a successful mapper must not authorize tampered source_map content.
    ctx.source_map[1]["chunk_id"] = "retrieved-but-not-selected"
    citations, invalid = map_evidence_indices_to_citations([1], ctx)
    check(ctx, citations, "SOURCE_MAP_PROVENANCE_MISMATCH", [1], invalid)


@pytest.mark.parametrize("value", [None, 1, "1", {1}, {"index": 1}])
@pytest.mark.parametrize("argument,reason", [
    ("citations", "INVALID_CITATION_TYPE"),
    ("evidence_indices", "INVALID_EVIDENCE_INDEX"),
    ("invalid_indices", "INVALID_MAPPER_RESULT"),
])
def test_malformed_containers_fail_closed(value, argument, reason):
    ctx, c = fixture_pair()
    kwargs = dict(citations=[c], evidence_indices=[1], invalid_indices=[])
    kwargs[argument] = value
    result = validate_citations(ctx, **kwargs)
    assert result.reason == reason
    assert not result.is_grounded


@pytest.mark.parametrize("value", [None, [{}], "bad"])
def test_mutated_evidence_container(value):
    ctx, c = fixture_pair()
    ctx.evidence_items = value
    check(ctx, [c], "INVALID_CONTEXT_EVIDENCE")


@pytest.mark.parametrize("value", [None, [], "bad"])
def test_mutated_source_map_container(value):
    ctx, c = fixture_pair()
    ctx.source_map = value
    check(ctx, [c], "SOURCE_MAP_INDEX_MISMATCH")


@pytest.mark.parametrize("index", [True, 0, 6, "1", None])
def test_mutated_citation_index(index):
    ctx, c = fixture_pair()
    c.evidence_index = index
    check(ctx, [c], "INVALID_CITATION_INDEX")


@pytest.mark.parametrize("indices", [[2], [1, 3], [2, 1]])
def test_mutated_context_must_keep_prompt_numbering(indices):
    ctx, c = fixture_pair()
    original = ctx.evidence_items[0]
    ctx.evidence_items = [original.model_copy(update={"evidence_index": i}) for i in indices]
    ctx.source_map = {i: deepcopy(ctx.source_map[1]) for i in indices}
    c.evidence_index = indices[0]
    check(ctx, [c], "NON_CONTIGUOUS_CONTEXT_INDEX", [indices[0]])


@pytest.mark.parametrize("field", ["chunk_id", "document_id", "article_id", "clause_id", "parent_clause_id"])
@pytest.mark.parametrize("location", ["citation", "source_map"])
def test_missing_citation_metadata_never_passes(field, location):
    ctx, c = fixture_pair()
    if location == "citation":
        setattr(c, field, None)
        reason = "CITATION_PROVENANCE_MISMATCH"
    else:
        del ctx.source_map[1][field]
        reason = "SOURCE_MAP_PROVENANCE_MISMATCH"
    check(ctx, [c], reason)


def test_outside_context_failure_does_not_mutate_or_repair_input():
    ctx, c = fixture_pair()
    # A retrieved chunk omitted from the prompt cannot be added by validation.
    c = c.model_copy(update={"evidence_index": 2, "chunk_id": "retrieved-not-selected"})
    indices, invalid = [2], []
    before = deepcopy((ctx.model_dump(), c.model_dump(), indices, invalid))
    result = validate_citations(ctx, [c], evidence_indices=indices, invalid_indices=invalid)
    assert result.reason == "CITATION_OUTSIDE_CONTEXT"
    assert result.grounding_status == "FAIL"
    assert result.invalid_indices == [2]
    assert result.valid_citations == []
    assert before == (ctx.model_dump(), c.model_dump(), indices, invalid)


def test_validation_requires_no_provider_or_api(monkeypatch):
    import socket

    def deny_network(*args, **kwargs):
        pytest.fail("Citation validation must not use network services")

    monkeypatch.setattr(socket, "socket", deny_network)
    monkeypatch.setattr(socket, "create_connection", deny_network)
    ctx, c = fixture_pair()
    assert validate_citations(ctx, [c], evidence_indices=[1]).grounding_status == "PASS"
    check(ctx, [c], "INVALID_EVIDENCE_INDEX", [0])


def test_handoff_samples_match_canonical_schema_and_actual_results():
    import json
    from pathlib import Path
    from schemas.models import GroundingResult

    samples = json.loads((Path(__file__).parent / "fixtures" / "week10_grounding_results.json").read_text(encoding="utf-8"))
    ctx, c = fixture_pair()
    passed = validate_citations(ctx, [c], evidence_indices=[1])
    c = c.model_copy(update={"evidence_index": 2, "chunk_id": "retrieved-not-selected"})
    failed = validate_citations(ctx, [c], evidence_indices=[2])
    assert GroundingResult.model_validate(samples["pass"]) == passed
    assert GroundingResult.model_validate(samples["fail"]) == failed
