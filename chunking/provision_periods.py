"""Khoảng hiệu lực cấp Điều/Khoản cho văn bản hết hiệu lực một phần.

Registry (data/reference/document_versions.json) chỉ có ngày hết hiệu lực cấp văn bản.
data/reference/provision_periods.json ghi các Điều/Khoản đã bị bãi bỏ hoặc sửa đổi
bởi một văn bản khác trong corpus; exporter dùng file này để ghi effective_to và
provision_status vào chunk, để lọc theo thời điểm (retrieval/temporal.py) loại được
các Điều/Khoản đó sau ngày văn bản sửa đổi có hiệu lực.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "reference" / "provision_periods.json"
PROVISION_STATUSES = frozenset({"repealed", "amended"})
REQUIRED_KEYS = ("id", "document_id", "provision_status", "effective_to", "changed_by", "provision", "evidence_chunk_id")


@dataclass(frozen=True)
class ProvisionOverride:
    id: str
    document_id: str
    articles: frozenset[str]
    clauses: frozenset[tuple[str, str]]
    points: frozenset[tuple[str, str, str]]
    chapters: tuple[str, ...]
    provision_status: str
    effective_to: str
    changed_by: str
    provision: str
    evidence_chunk_id: str
    quoted_clauses: frozenset[tuple[str, str, str]] = frozenset()
    evidence_context_ids: tuple[str, ...] = ()

    def scope_of(
        self, document_id: str, article_number: Any, clause_number: Any, point_ref: Any = None,
        quoted_clause_number: Any = None,
    ) -> tuple[str, ...] | None:
        """Phạm vi khớp: article, clause, point hoặc quoted_clause (a, k, q).

        Bản ghi cấp Điểm chỉ khớp chunk chứa đúng một Điểm (point_ref "Điểm p"); exporter
        tách các Khoản đó theo Điểm (split_point_clause_ids).
        """
        if document_id != self.document_id:
            return None
        article = str(article_number) if article_number is not None else None
        if article in self.articles:
            return ("article", article)
        clause = str(clause_number) if clause_number is not None else None
        quoted = str(quoted_clause_number) if quoted_clause_number is not None else None
        if (article, clause, quoted) in self.quoted_clauses:
            return ("quoted_clause", article, clause, quoted)
        if (article, clause) in self.clauses:
            return ("clause", article, clause)
        if isinstance(point_ref, str) and point_ref.startswith("Điểm ") and "-" not in point_ref:
            point = point_ref.removeprefix("Điểm ").strip()
            if (article, clause, point) in self.points:
                return ("point", article, clause, point)
        return None

    def scope_items(self) -> set[tuple[str, ...]]:
        return (
            {("article", a) for a in self.articles}
            | {("clause", a, k) for a, k in self.clauses}
            | {("point", a, k, p) for a, k, p in self.points}
            | {("quoted_clause", a, k, q) for a, k, q in self.quoted_clauses}
        )


def _parse_override(raw: dict[str, Any]) -> ProvisionOverride:
    missing = [key for key in REQUIRED_KEYS if not raw.get(key)]
    if missing:
        raise ValueError(f"provision_periods.json: bản ghi {raw.get('id')!r} thiếu {missing}")
    if raw["provision_status"] not in PROVISION_STATUSES:
        raise ValueError(
            f"provision_periods.json: {raw['id']}: provision_status {raw['provision_status']!r} "
            f"không thuộc {sorted(PROVISION_STATUSES)}"
        )
    try:
        effective_to = date.fromisoformat(raw["effective_to"]).isoformat()
    except ValueError as exc:
        raise ValueError(f"provision_periods.json: {raw['id']}: effective_to không phải ngày ISO") from exc
    articles = frozenset(str(a) for a in raw.get("articles") or [])
    clauses = frozenset((str(c["article"]), str(c["clause"])) for c in raw.get("clauses") or [])
    points = frozenset(
        (str(p["article"]), str(p["clause"]), str(p["point"])) for p in raw.get("points") or []
    )
    quoted_clauses = frozenset(
        (str(q["article"]), str(q["clause"]), str(q["quoted_clause"]))
        for q in raw.get("quoted_clauses") or []
    )
    if not articles and not clauses and not points and not quoted_clauses:
        raise ValueError(f"provision_periods.json: {raw['id']}: cần ít nhất một trong articles, clauses, points, quoted_clauses")
    overlap = {a for a, _ in clauses} & articles
    if overlap:
        raise ValueError(f"provision_periods.json: {raw['id']}: Khoản nằm trong Điều đã liệt kê: {sorted(overlap)}")
    covered = {(a, k) for a, k, _ in points if a in articles or (a, k) in clauses}
    if covered:
        raise ValueError(f"provision_periods.json: {raw['id']}: Điểm nằm trong Điều/Khoản đã liệt kê: {sorted(covered)}")
    if any(a in articles or (a, k) in clauses for a, k, _ in quoted_clauses):
        raise ValueError(f"provision_periods.json: {raw['id']}: Khoản trích dẫn nằm trong Điều/Khoản đã liệt kê")
    context_ids = raw.get("evidence_context_ids", [raw["evidence_chunk_id"]])
    if (
        not isinstance(context_ids, list) or not context_ids
        or any(not isinstance(cid, str) or not cid for cid in context_ids)
        or len(set(context_ids)) != len(context_ids)
        or raw["evidence_chunk_id"] not in context_ids
    ):
        raise ValueError(f"provision_periods.json: {raw['id']}: evidence_context_ids không hợp lệ")
    return ProvisionOverride(
        id=raw["id"],
        document_id=raw["document_id"],
        articles=articles,
        clauses=clauses,
        points=points,
        chapters=tuple(raw.get("chapters") or ()),
        provision_status=raw["provision_status"],
        effective_to=effective_to,
        changed_by=raw["changed_by"],
        provision=raw["provision"],
        evidence_chunk_id=raw["evidence_chunk_id"],
        quoted_clauses=quoted_clauses,
        evidence_context_ids=tuple(context_ids),
    )


def load_overrides(path: Path = DEFAULT_PATH) -> list[ProvisionOverride]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    overrides = [_parse_override(raw) for raw in data.get("overrides", [])]
    ids = [o.id for o in overrides]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise ValueError(f"provision_periods.json: id trùng {duplicates}")
    seen: dict[tuple[str, tuple[str, ...]], str] = {}
    for override in overrides:
        for item in override.scope_items():
            key = (override.document_id, item)
            if key in seen:
                raise ValueError(f"provision_periods.json: {item} của {override.document_id} có ở cả {seen[key]} và {override.id}")
            seen[key] = override.id
    return overrides


def split_point_clause_ids(overrides: list[ProvisionOverride]) -> set[str]:
    """clause_id của các Khoản có bản ghi cấp Điểm; chunker tách các Khoản này theo Điểm."""
    return {f"{o.document_id}_art_{a}_clause_{k}" for o in overrides for a, k, _ in o.points}


def split_quoted_clause_ids(overrides: list[ProvisionOverride]) -> set[str]:
    """Khoản sửa đổi cần chia theo các Khoản được trích dẫn bên trong."""
    return {f"{o.document_id}_art_{a}_clause_{k}" for o in overrides for a, k, _ in o.quoted_clauses}


def apply_to_chunk(record: dict[str, Any], overrides: list[ProvisionOverride]) -> tuple[ProvisionOverride, tuple[str, ...]] | None:
    """Ghi effective_to, provision_status của Điều/Khoản vào bản ghi chunk (chunks.jsonl).

    Giữ effective_to cấp văn bản nếu văn bản đã hết hiệu lực sớm hơn.
    """
    meta = record["metadata"]
    document_id = record.get("document_id") or record.get("doc_id")
    for override in overrides:
        item = override.scope_of(
            document_id, meta.get("article_number"), meta.get("clause_number"), record.get("point_ref"),
            meta.get("quoted_clause_number"),
        )
        if item is None:
            continue
        effective_from = meta.get("effective_from") or ""
        if effective_from and override.effective_to <= effective_from:
            raise ValueError(
                f"{override.id}: effective_to {override.effective_to} không sau effective_from "
                f"{effective_from} của {record.get('chunk_id')}"
            )
        current = meta.get("effective_to")
        if not current or override.effective_to < current:
            meta["effective_to"] = override.effective_to
        meta["provision_status"] = override.provision_status
        record["provision_status"] = override.provision_status
        return override, item
    return None
