"""Deterministically extract legal citation mentions from generated answers.

This module identifies citation text only. It does not decide whether a citation
is legally correct, supported, in force, or present in the supplied context.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from evaluation.document_aliases import (
    ROOT,
    load_alias_map,
    resolve_document_alias,
    validate_alias_map,
)

DEFAULT_ALIAS_MAP_PATH = ROOT / "data" / "reference" / "document_aliases.json"


def _normalized_with_offsets(text: str) -> tuple[str, list[tuple[int, int]]]:
    """Normalize like document_aliases while retaining source character spans."""
    chars: list[str] = []
    offsets: list[tuple[int, int]] = []
    pending_space: tuple[int, int] | None = None
    for index, original in enumerate(text):
        folded = unicodedata.normalize("NFKD", original.casefold().replace("đ", "d"))
        folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
        for char in folded:
            if char.isalnum():
                if pending_space is not None and chars:
                    chars.append(" ")
                    offsets.append(pending_space)
                pending_space = None
                chars.append(char)
                offsets.append((index, index + 1))
            elif chars:
                pending_space = (index, index + 1)
    return "".join(chars), offsets


def _alias_mentions(text: str, alias_map: dict[str, Any]) -> list[dict[str, Any]]:
    normalized, offsets = _normalized_with_offsets(text)
    found: dict[tuple[int, int, str], dict[str, Any]] = {}
    for key, entry in alias_map["aliases"].items():
        if not key or entry.get("requires_identity_context"):
            # Bare years and type+year aliases are too weak to identify a law.
            continue
        start = 0
        while True:
            pos = normalized.find(key, start)
            if pos < 0:
                break
            end = pos + len(key)
            left_ok = pos == 0 or normalized[pos - 1] == " "
            right_ok = end == len(normalized) or normalized[end] == " "
            if left_ok and right_ok and pos < len(offsets) and end <= len(offsets):
                source_start = offsets[pos][0]
                source_end = offsets[end - 1][1]
                mention = {
                    "start": source_start,
                    "end": source_end,
                    "text": text[source_start:source_end],
                    "normalized_alias": key,
                    "resolution": resolve_document_alias(
                        text[source_start:source_end], alias_map
                    ),
                }
                found[(source_start, source_end, key)] = mention
            start = pos + 1
    # Keep the longest exact alias when aliases overlap at the same location.
    mentions = sorted(found.values(), key=lambda item: (item["start"], -(item["end"] - item["start"])))
    selected: list[dict[str, Any]] = []
    for mention in mentions:
        if selected and mention["start"] < selected[-1]["end"]:
            if mention["end"] - mention["start"] > selected[-1]["end"] - selected[-1]["start"]:
                selected[-1] = mention
            continue
        selected.append(mention)
    return selected


_PROVISION_RE = re.compile(
    r"(?i)\b(?P<kind>điều|khoản|điểm)\s+(?P<num>\d+[a-z]?|[a-zđ])"
    r"(?:\s*\(\s*(?P<paren>\d+[a-z]?)\s*\))?"
)
_PAREN_POINT_RE = re.compile(r"\(\s*(?P<point>[a-zđ])\s*\)", re.IGNORECASE)


def _sentence_bounds(text: str, position: int) -> tuple[int, int]:
    left = max((text.rfind(mark, 0, position) for mark in ".!?\n;"), default=-1) + 1
    ends = [text.find(mark, position) for mark in ".!?\n;"]
    ends = [end for end in ends if end >= 0]
    return left, min(ends) if ends else len(text)


def _parse_provisions(text: str) -> list[dict[str, Any]]:
    """Read Điều/Khoản/Điểm references; article numbers alone are not inferred."""
    provisions: list[dict[str, Any]] = []
    for match in _PROVISION_RE.finditer(text):
        kind = match.group("kind").casefold()
        if kind == "điều":
            provision = {
                "article_number": match.group("num"),
                "clause_number": None,
                "point": None,
                "start": match.start(),
                "end": match.end(),
                "text": match.group(0),
            }
        elif kind == "khoản":
            # A clause number is emitted only when an article is explicit in
            # the same sentence; clause-to-article inference is intentionally avoided.
            provision = {
                "article_number": None,
                "clause_number": match.group("num"),
                "point": None,
                "start": match.start(),
                "end": match.end(),
                "text": match.group(0),
            }
        else:
            provision = {
                "article_number": None,
                "clause_number": match.group("paren"),
                "point": match.group("num"),
                "start": match.start(),
                "end": match.end(),
                "text": match.group(0),
            }
        provisions.append(provision)

    # Capture the common compact form "Điều 8(1)(a)" where the generic
    # provision expression has already read only the first parenthesized part.
    for article in [p for p in provisions if p["article_number"] is not None]:
        tail = text[article["end"] : article["end"] + 20]
        compact = re.match(r"\s*\(\s*\d+[a-z]?\s*\)\s*\(\s*([a-zđ])\s*\)", tail, re.I)
        if compact:
            article["point"] = compact.group(1).casefold()
            if article["clause_number"] is None:
                clause = re.match(r"\s*\(\s*(\d+[a-z]?)", tail, re.I)
                if clause:
                    article["clause_number"] = clause.group(1)

    # Attach a nearby explicitly stated clause/point to its article mention.
    for article in [p for p in provisions if p["article_number"] is not None]:
        left, right = _sentence_bounds(text, article["start"])
        local = [p for p in provisions if p is not article and left <= p["start"] < right]
        before = [p for p in local if p["start"] < article["start"] and p["clause_number"]]
        after = [p for p in local if p["start"] > article["start"] and p["clause_number"]]
        clause = (before or after)
        if clause:
            closest = min(clause, key=lambda p: abs(p["start"] - article["start"]))
            article["clause_number"] = closest["clause_number"]
            # A separate "điểm a" immediately adjacent to "khoản 1" belongs
            # to the same pinpoint citation.
            point_mentions = [
                p for p in local
                if p["point"] is not None
                and abs(p["start"] - closest["start"]) <= 60
            ]
            if point_mentions:
                article["point"] = min(
                    point_mentions,
                    key=lambda p: abs(p["start"] - closest["start"]),
                )["point"]
    return [p for p in provisions if p["article_number"] is not None]


def parse_citations(
    answer: str,
    alias_map: dict[str, Any] | None = None,
    *,
    alias_map_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Extract document and provision references from a Zero-shot answer.

    Each returned item has ``document_id`` only when the exact alias resolves
    unambiguously. When a document is named without an article, it is returned
    as a document-level citation. Unresolved/ambiguous text remains visible in
    the result with its resolution status; it is never guessed.
    """
    if not isinstance(answer, str):
        raise TypeError("answer must be a string")
    if alias_map is None:
        alias_map = (
            load_alias_map(alias_map_path)
            if alias_map_path is not None
            else load_alias_map()
        )
    else:
        validate_alias_map(alias_map)

    aliases = _alias_mentions(answer, alias_map)
    provisions = _parse_provisions(answer)
    citations: list[dict[str, Any]] = []
    used_aliases: set[int] = set()
    for provision in provisions:
        left, right = _sentence_bounds(answer, provision["start"])
        candidates = [
            (idx, alias)
            for idx, alias in enumerate(aliases)
            if left <= alias["start"] < right
        ]
        if not candidates and len(aliases) == 1:
            candidates = [(0, aliases[0])]
        alias_idx, alias = min(
            candidates,
            key=lambda pair: abs(pair[1]["start"] - provision["start"]),
            default=(None, None),
        )
        resolution = alias["resolution"] if alias else {"status": "document_not_found", "document_id": None, "candidates": []}
        document_id = resolution.get("document_id")
        article = provision["article_number"]
        citation_aliases = [alias] if alias else []
        if alias_idx is not None:
            used_aliases.add(alias_idx)
        if document_id:
            citation_aliases = [
                candidate
                for idx, candidate in candidates
                if candidate["resolution"].get("document_id") == document_id
                and abs(candidate["start"] - provision["start"]) <= 100
            ] or citation_aliases
            used_aliases.update(
                idx
                for idx, candidate in candidates
                if candidate["resolution"].get("document_id") == document_id
                and abs(candidate["start"] - provision["start"]) <= 100
            )
        citation_start = min(
            [provision["start"], *(item["start"] for item in citation_aliases)]
        )
        citation_end = max(
            [provision["end"], *(item["end"] for item in citation_aliases)]
        )
        citation = {
            "raw_text": answer[citation_start:citation_end],
            "document_alias": alias["text"] if alias else None,
            "document_id": document_id,
            "document_resolution": resolution["status"],
            "candidate_document_ids": resolution.get("candidates", []),
            "article_number": article,
            "clause_number": provision["clause_number"],
            "point": provision["point"],
            "article_id": f"{document_id}_art_{article}" if document_id and article else None,
            "clause_id": (
                f"{document_id}_art_{article}_clause_{provision['clause_number']}"
                if document_id and article and provision["clause_number"]
                else None
            ),
            "start": citation_start,
            "end": citation_end,
        }
        citations.append(citation)

    for idx, alias in enumerate(aliases):
        if idx in used_aliases:
            continue
        resolution = alias["resolution"]
        citations.append({
            "raw_text": alias["text"],
            "document_alias": alias["text"],
            "document_id": resolution.get("document_id"),
            "document_resolution": resolution["status"],
            "candidate_document_ids": resolution.get("candidates", []),
            "article_number": None,
            "clause_number": None,
            "point": None,
            "article_id": None,
            "clause_id": None,
            "start": alias["start"],
            "end": alias["end"],
        })
    return sorted(citations, key=lambda item: (item["start"], item["end"]))


def parse_zero_shot_records(
    records: list[dict[str, Any]], alias_map: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """Return copied prediction records enriched with parsed ``citations``."""
    if not isinstance(records, list):
        raise TypeError("records must be a list")
    output = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"record at index {index} must be an object")
        query_id = record.get("query_id", record.get("id"))
        if not isinstance(query_id, str) or not query_id.strip():
            raise ValueError(f"record at index {index} is missing query_id/id")
        result = dict(record)
        result["query_id"] = query_id
        if "question" in result and "query" not in result:
            result["query"] = result.pop("question")
        if result.get("as_of_date"):
            result.setdefault("as_of_date_source", "benchmark")
        result["citations"] = parse_citations(
            record.get("answer") or "", alias_map=alias_map
        )
        as_of_date = result.get("as_of_date")
        output.append({
            "status": "ERROR" if result.get("error") or result.get("answer") is None else "SUCCESS",
            "query_id": query_id,
            "as_of_date": as_of_date,
            "result": result,
        })
    return output


def parse_zero_shot_file(
    input_path: str | Path,
    output_path: str | Path,
    *,
    alias_map_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Parse a Zero-shot result JSON array into a citation-enriched JSON artifact."""
    input_path, output_path = Path(input_path), Path(output_path)
    records = json.loads(input_path.read_text(encoding="utf-8-sig"))
    if not isinstance(records, list):
        raise ValueError("Zero-shot results file must contain a JSON array")
    aliases = load_alias_map(alias_map_path) if alias_map_path else load_alias_map()
    parsed = parse_zero_shot_records(records, alias_map=aliases)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(parsed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return parsed
