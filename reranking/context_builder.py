"""Context Aggregator (architecture: Parent-Context Resolver -> Consolidated Context Payload).

Turns the reranked, threshold-filtered rows (already carrying ``parent_id`` and
``parent_text`` from ``reranking.parent_context``) into the canonical
``schemas.models.ContextPayload`` that Dev 3's Prompt Builder renders and Dev 1's
validator checks. It does not resolve parents again.

Evidence ``[i]`` is the i-th ranked child chunk, so ``evidence_index`` maps back to
that child's ``chunk_id``/``document_id``/``article_id``/``clause_id``/``parent_clause_id``.
Its ``content`` is the parent text when the resolver attached it to this child
(best-ranked child of that parent, within budget), else the child's own chunk text.
If one more item would exceed ``max_context_chars``, the parent text falls back to the
chunk text; if even that does not fit, that item and all lower-ranked items are left out.
IDs are copied, never derived: a row without ``parent_clause_id`` is an error.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from schemas.models import ContextPayload, EvidenceItem

MAX_EVIDENCE_ITEMS = 5
REQUIRED_IDS = ("chunk_id", "document_id", "article_id", "clause_id", "parent_clause_id")


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _breadcrumb(meta: Mapping[str, Any]) -> str | None:
    crumb = _text(meta.get("breadcrumb"))
    if crumb:
        return crumb
    parts = []
    if _text(meta.get("chapter")):
        parts.append(meta["chapter"].strip())
    if meta.get("article_number") not in (None, ""):
        parts.append(f"Điều {meta['article_number']}")
    if meta.get("clause_number") not in (None, ""):
        parts.append(f"Khoản {meta['clause_number']}")
    return " > ".join(parts) or None


def evidence_from_row(row: Mapping[str, Any], evidence_index: int, content: str) -> EvidenceItem:
    meta = row.get("metadata") or {}
    if not isinstance(meta, Mapping):
        raise ValueError(f"metadata của {row.get('chunk_id')!r} phải là object")
    missing = [name for name in REQUIRED_IDS if not _text(row.get(name))]
    if missing:
        raise ValueError(f"Kết quả {row.get('chunk_id')!r} thiếu {missing}; không suy ra ID từ trường khác")
    validity = _text(row.get("validity_status")) or _text(meta.get("validity_status"))
    if not validity:
        raise ValueError(f"Kết quả {row['chunk_id']!r} thiếu validity_status")
    return EvidenceItem(
        evidence_index=evidence_index,
        chunk_id=row["chunk_id"],
        parent_clause_id=row["parent_clause_id"],
        document_id=row["document_id"],
        article_id=row["article_id"],
        clause_id=row["clause_id"],
        content=content,
        validity_status=validity,
        effective_from=row.get("effective_from") or meta.get("effective_from"),
        effective_to=row.get("effective_to") or meta.get("effective_to"),
        source_url=_text(meta.get("source_url")),
        document_number=_text(meta.get("document_number")),
        document_title=_text(meta.get("document_title")) or _text(meta.get("title")),
        article_number=None if meta.get("article_number") in (None, "") else str(meta["article_number"]),
        clause_number=None if meta.get("clause_number") in (None, "") else str(meta["clause_number"]),
        breadcrumb=_breadcrumb(meta),
        provision_status=_text(meta.get("provision_status")),
    )


def build_context_payload(rows: Sequence[Mapping[str, Any]], *, query_id: str, query: str, as_of_date: str,
                          as_of_date_source: str, max_context_chars: int,
                          max_items: int = MAX_EVIDENCE_ITEMS) -> tuple[ContextPayload, dict[str, Any]]:
    """Return the payload and a trace of which text each evidence item carries."""
    if not rows:
        raise ValueError("Không có kết quả để dựng ngữ cảnh")
    if not 1 <= max_items <= MAX_EVIDENCE_ITEMS:
        raise ValueError(f"max_items phải trong [1, {MAX_EVIDENCE_ITEMS}]")
    items: list[EvidenceItem] = []
    trace_items: list[dict[str, Any]] = []
    used = 0
    truncated = False
    for row in rows[:max_items]:
        chunk_text = _text(row.get("chunk_text"))
        if not chunk_text:
            raise ValueError(f"Kết quả {row.get('chunk_id')!r} không có chunk_text")
        parent_text = _text(row.get("parent_text"))
        if parent_text and used + len(parent_text) <= max_context_chars:
            content, kind = parent_text, "parent_text"
        elif used + len(chunk_text) <= max_context_chars:
            content, kind = chunk_text, "chunk_text"
            if parent_text:
                truncated = True
        else:
            truncated = True
            break
        item = evidence_from_row(row, len(items) + 1, content)
        items.append(item)
        used += len(item.content)
        trace_items.append({
            "evidence_index": item.evidence_index,
            "chunk_id": item.chunk_id,
            "parent_id": row.get("parent_id"),
            "content": kind,
            "chars": len(item.content),
            "rank": row.get("rank"),
            "reranker_score": row.get("reranker_score"),
        })
    if not items:
        raise ValueError(f"Kết quả hạng 1 dài hơn max_context_chars ({max_context_chars})")
    payload = ContextPayload(
        query_id=query_id, query=query, as_of_date=as_of_date, as_of_date_source=as_of_date_source,
        evidence_items=items, max_context_chars=max_context_chars,
    )
    trace = {
        "evidence": trace_items,
        "context_chars": payload.total_chars,
        "max_context_chars": max_context_chars,
        "context_budget_truncated": truncated,
        "rows_left_out": len(rows) - len(items),
    }
    return payload, trace


__all__ = ["MAX_EVIDENCE_ITEMS", "build_context_payload", "evidence_from_row"]
