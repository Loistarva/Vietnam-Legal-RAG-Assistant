"""Week 10 D1.1: check citation provenance, not claim truth or legal correctness.

The caller must supply the exact ContextPayload rendered into the prompt, all
original model indices and the mapper's invalid indices. Never validate against
the retrieval pool or silently discard mapper failures before calling here.
"""
from collections.abc import Sequence

from schemas.models import ContextPayload, EvidenceItem, GroundingResult, MappedCitation

_FIELDS = ("chunk_id", "document_id", "article_id", "clause_id", "parent_clause_id")


def validate_citations(
    context_payload: ContextPayload,
    citations: Sequence[MappedCitation],
    *,
    evidence_indices: Sequence[int],
    invalid_indices: Sequence[int] = (),
) -> GroundingResult:
    """Return all-or-nothing PASS/FAIL with a stable machine-readable reason.

    Empty citations fail closed. Abstention/clarification policy belongs to the
    orchestration Gate; this validator never authorizes answer emission itself.
    Duplicate indices fail rather than hiding duplicate/conflicting mappings.
    """
    def fail(reason: str, indices: Sequence[int] = ()) -> GroundingResult:
        # GroundingResult only permits integer invalid_indices. Malformed raw
        # values are represented by reason, never coerced to a valid index.
        bad = sorted({i for i in indices if type(i) is int})
        return GroundingResult(grounding_status="FAIL", is_grounded=False,
                               invalid_indices=bad, reason=reason)

    if not isinstance(context_payload, ContextPayload):
        return fail("INVALID_CONTEXT_TYPE")
    def is_sequence(value: object) -> bool:
        return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))

    if not is_sequence(citations):
        return fail("INVALID_CITATION_TYPE")
    if any(not isinstance(c, MappedCitation) for c in citations):
        return fail("INVALID_CITATION_TYPE")
    if not is_sequence(evidence_indices):
        return fail("INVALID_EVIDENCE_INDEX")
    if not is_sequence(invalid_indices):
        return fail("INVALID_MAPPER_RESULT")
    if invalid_indices:
        return fail("MAPPER_INVALID_INDICES", invalid_indices)
    if any(type(i) is not int or not 1 <= i <= 5 for i in evidence_indices):
        return fail("INVALID_EVIDENCE_INDEX", evidence_indices)
    if len(set(evidence_indices)) != len(evidence_indices):
        return fail("DUPLICATE_EVIDENCE_INDEX", evidence_indices)
    items = context_payload.evidence_items
    if not is_sequence(items) or any(not isinstance(item, EvidenceItem) for item in items):
        return fail("INVALID_CONTEXT_EVIDENCE")
    if not items:
        return fail("EMPTY_CONTEXT")
    if len(items) > 5:
        return fail("TOO_MANY_EVIDENCE_ITEMS")
    indices = [item.evidence_index for item in items]
    if any(type(i) is not int or not 1 <= i <= 5 for i in indices):
        return fail("INVALID_CONTEXT_INDEX", indices)
    if len(set(indices)) != len(indices):
        return fail("DUPLICATE_CONTEXT_INDEX", indices)
    # Pydantic checks this at construction, but payloads remain mutable. Do not
    # authorize a context that no longer follows the prompt's [1]..[n] contract.
    if indices != list(range(1, len(items) + 1)):
        return fail("NON_CONTIGUOUS_CONTEXT_INDEX", indices)
    if any(not isinstance(getattr(item, field), str) or not getattr(item, field).strip()
           for item in items for field in (*_FIELDS, "content")):
        return fail("EMPTY_EVIDENCE_FIELD")
    selected = {item.evidence_index: item for item in items}
    source_map = context_payload.source_map
    if (not isinstance(source_map, dict) or set(source_map) != set(selected)
            or any(type(i) is not int for i in source_map)):
        return fail("SOURCE_MAP_INDEX_MISMATCH")
    for idx, item in selected.items():
        source = source_map[idx]
        if not isinstance(source, dict) or any(source.get(f) != getattr(item, f) for f in _FIELDS):
            return fail("SOURCE_MAP_PROVENANCE_MISMATCH", [idx])
    if not evidence_indices or not citations:
        return fail("MISSING_CITATIONS")
    citation_indices = [c.evidence_index for c in citations]
    if any(type(i) is not int or not 1 <= i <= 5 for i in citation_indices):
        return fail("INVALID_CITATION_INDEX", citation_indices)
    if len(set(citation_indices)) != len(citation_indices):
        return fail("DUPLICATE_CITATION_INDEX", citation_indices)
    if set(citation_indices) != set(evidence_indices):
        return fail("CITATION_INDEX_SET_MISMATCH", evidence_indices)
    for citation in citations:
        idx = citation.evidence_index
        if idx not in selected:
            return fail("CITATION_OUTSIDE_CONTEXT", [idx])
        if any(getattr(citation, f) != getattr(selected[idx], f) for f in _FIELDS):
            return fail("CITATION_PROVENANCE_MISMATCH", [idx])
    return GroundingResult(grounding_status="PASS", is_grounded=True,
                           valid_citations=sorted(citations, key=lambda c: c.evidence_index),
                           reason="CITATIONS_MATCH_SELECTED_CONTEXT")
