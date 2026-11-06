"""Khoảng hiệu lực cấp Điều/Khoản (data/reference/provision_periods.json, D1).

Mỗi bản ghi phải có căn cứ trong corpus (chunk của văn bản bãi bỏ/sửa đổi nêu đúng số hiệu
văn bản bị sửa), effective_to bằng ngày văn bản đó có hiệu lực, và corpus trong repo phải
mang đúng effective_to, provision_status ở mọi chunk thuộc phạm vi.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "chunking"))
sys.path.insert(0, str(ROOT))

from provision_periods import apply_to_chunk, load_overrides  # noqa: E402
from retrieval.temporal import is_effective_at  # noqa: E402

PERIODS = ROOT / "data" / "reference" / "provision_periods.json"
REGISTRY = {r["document_id"]: r for r in json.loads((ROOT / "data/reference/document_versions.json").read_text(encoding="utf-8"))}
CHUNKS = [json.loads(line) for line in (ROOT / "data/chunking_output/chunks.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
BY_ID = {c["chunk_id"]: c for c in CHUNKS}
OVERRIDES = load_overrides(PERIODS)


def _number_pattern(document_number: str) -> re.Pattern[str]:
    return re.compile(re.escape(document_number).replace(r"\-", "[-‐–]"), re.IGNORECASE)


@pytest.mark.parametrize("override", OVERRIDES, ids=lambda o: o.id)
def test_override_has_evidence_in_corpus(override):
    assert override.document_id in REGISTRY
    assert override.changed_by in REGISTRY
    assert override.effective_to == REGISTRY[override.changed_by]["effective_date"], (
        "effective_to phải bằng ngày văn bản bãi bỏ/sửa đổi có hiệu lực"
    )
    evidence = BY_ID.get(override.evidence_chunk_id)
    assert evidence is not None, f"Không có chunk {override.evidence_chunk_id} trong corpus"
    assert evidence["document_id"] == override.changed_by
    number = REGISTRY[override.document_id]["document_number"]
    assert _number_pattern(number).search(evidence["chunk_text"]), f"{override.evidence_chunk_id} không nêu {number}"


@pytest.mark.parametrize("override", [o for o in OVERRIDES if o.chapters], ids=lambda o: o.id)
def test_chapter_override_lists_exactly_the_articles_of_those_chapters(override):
    parsed = json.loads((ROOT / "parser/parsed_jsons" / f"{override.document_id}.json").read_text(encoding="utf-8"))
    chapter_re = re.compile(r"Chương\s+(" + "|".join(override.chapters) + r")\b")
    expected = {str(a["article_number"]) for a in parsed["articles"] if chapter_re.match(a.get("chapter") or "")}
    assert override.articles == frozenset(expected)


def test_corpus_carries_provision_periods():
    covered = 0
    for chunk in CHUNKS:
        meta = chunk["metadata"]
        doc_expiry = REGISTRY[chunk["document_id"]].get("expiry_date") or None
        match = None
        for override in OVERRIDES:
            if override.scope_of(chunk["document_id"], meta.get("article_number"), meta.get("clause_number")):
                match = override
        if match is None:
            assert meta["effective_to"] == doc_expiry, chunk["chunk_id"]
            continue
        covered += 1
        expected = min(d for d in (doc_expiry, match.effective_to) if d)
        assert meta["effective_to"] == expected, chunk["chunk_id"]
        assert meta["provision_status"] == chunk["provision_status"] == match.provision_status, chunk["chunk_id"]
    assert covered > 0


def test_repealed_nd_126_articles_are_filtered_after_nd_123_takes_effect():
    chunk = BY_ID["nd_126_2014_nd_cp_art_20_clause_1_chunk_1"]
    assert is_effective_at(chunk, "2015-12-31")
    assert not is_effective_at(chunk, "2016-01-01")
    assert is_effective_at(BY_ID["nd_126_2014_nd_cp_art_18_clause_1_chunk_1"], "2026-10-15")


def _record(article, clause, effective_to=None, effective_from="2015-02-15"):
    return {
        "chunk_id": "x",
        "document_id": "nd_126_2014_nd_cp",
        "provision_status": "requires_review",
        "metadata": {
            "article_number": article,
            "clause_number": clause,
            "effective_from": effective_from,
            "effective_to": effective_to,
            "provision_status": "requires_review",
        },
    }


def test_apply_to_chunk_sets_period_and_status():
    record = _record("20", "1")
    override, item = apply_to_chunk(record, OVERRIDES)
    assert item == ("article", "20")
    assert record["metadata"]["effective_to"] == "2016-01-01"
    assert record["provision_status"] == record["metadata"]["provision_status"] == "repealed"
    untouched = _record("63", "1")
    assert apply_to_chunk(untouched, OVERRIDES) is None
    assert untouched["metadata"]["effective_to"] is None


def test_apply_to_chunk_keeps_earlier_document_expiry():
    record = _record("20", "1", effective_to="2015-12-01")
    apply_to_chunk(record, OVERRIDES)
    assert record["metadata"]["effective_to"] == "2015-12-01"


def test_apply_to_chunk_rejects_period_ending_before_it_starts():
    with pytest.raises(ValueError, match="không sau effective_from"):
        apply_to_chunk(_record("20", "1", effective_from="2016-06-01"), OVERRIDES)


def test_load_overrides_rejects_overlapping_scope(tmp_path):
    base = {
        "document_id": "d", "provision_status": "repealed", "effective_to": "2020-01-01",
        "changed_by": "e", "provision": "p", "evidence_chunk_id": "c",
    }
    path = tmp_path / "periods.json"
    path.write_text(json.dumps({"overrides": [
        {**base, "id": "a", "articles": ["1"]},
        {**base, "id": "b", "articles": ["1", "2"]},
    ]}), encoding="utf-8")
    with pytest.raises(ValueError, match="có ở cả"):
        load_overrides(path)


def test_load_overrides_rejects_unknown_status(tmp_path):
    path = tmp_path / "periods.json"
    path.write_text(json.dumps({"overrides": [{
        "id": "a", "document_id": "d", "articles": ["1"], "provision_status": "expired",
        "effective_to": "2020-01-01", "changed_by": "e", "provision": "p", "evidence_chunk_id": "c",
    }]}), encoding="utf-8")
    with pytest.raises(ValueError, match="provision_status"):
        load_overrides(path)
