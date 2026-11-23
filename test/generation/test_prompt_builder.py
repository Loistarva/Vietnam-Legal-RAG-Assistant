"""Regression tests for Prompt Builder, v1.2 immutability, v1.3 template, and template hash locks (D3.3)."""
from __future__ import annotations

from pathlib import Path

import pytest

from generation.prompt_builder import (
    EXPECTED_TEMPLATE_SHA256,
    EXPECTED_V1_2_PROMPTS_SHA256,
    MISSING_FACTS_TAXONOMY,
    OFFICIAL_PROMPT_A_VERSION,
    OFFICIAL_PROMPT_B_VERSION,
    PROMPT_A_VERSION,
    PROMPT_B_V1_3_VERSION,
    PROMPT_B_VERSION,
    PROMPT_TEMPLATE_FILES,
    build_controlled_rag_prompt,
    build_controlled_rag_prompt_v1_3,
    build_zero_shot_prompt,
    format_effectivity_at_as_of_date,
    get_prompt_hash,
    map_evidence_indices_to_citations,
    validate_missing_facts,
    verify_prompt_template_integrity,
)
from schemas.models import ContextPayload, EvidenceItem


def _make_evidence(
    idx: int = 1,
    *,
    effective_from: str | None = "2015-01-01",
    effective_to: str | None = None,
    validity_status: str = "Còn hiệu lực",
    point_ref: str | None = None,
) -> EvidenceItem:
    return EvidenceItem(
        evidence_index=idx,
        chunk_id=f"l_52_2014_qh13_art_8_clause_1_chunk_{idx}",
        parent_clause_id="l_52_2014_qh13_art_8_clause_1",
        document_id="l_52_2014_qh13",
        document_title="Luật Hôn nhân và gia đình 2014",
        document_number="52/2014/QH13",
        article_id="art_8",
        clause_id="clause_1",
        point_ref=point_ref,
        breadcrumb="Chương II > Điều 8 > Khoản 1",
        content="Nam từ đủ 20 tuổi trở lên, nữ từ đủ 18 tuổi trở lên.",
        validity_status=validity_status,
        effective_from=effective_from,
        effective_to=effective_to,
    )


def _canonical_v12_payload() -> ContextPayload:
    return ContextPayload(
        query_id="CANONICAL_V12",
        query="Tuổi kết hôn hợp pháp của nam và nữ?",
        as_of_date="2026-10-15",
        as_of_date_source="benchmark",
        evidence_items=[_make_evidence(1)],
    )


@pytest.mark.req("FR4.6")
@pytest.mark.req("FR4.6-AC1")
def test_official_v1_2_remains_default_and_byte_invariant():
    assert OFFICIAL_PROMPT_A_VERSION == PROMPT_A_VERSION == "v1.2_zero_shot"
    assert OFFICIAL_PROMPT_B_VERSION == PROMPT_B_VERSION == "v1.2_controlled_rag"
    assert PROMPT_B_V1_3_VERSION == "v1.3_controlled_rag"

    ctx = _canonical_v12_payload()
    prompt_a_1 = build_zero_shot_prompt(ctx.query, ctx.as_of_date)
    prompt_a_2 = build_zero_shot_prompt(ctx.query, ctx.as_of_date)
    prompt_b_1 = build_controlled_rag_prompt(ctx)
    prompt_b_2 = build_controlled_rag_prompt(ctx)

    assert prompt_a_1 == prompt_a_2
    assert prompt_b_1 == prompt_b_2
    assert get_prompt_hash(prompt_a_1) == EXPECTED_V1_2_PROMPTS_SHA256[PROMPT_A_VERSION]
    assert get_prompt_hash(prompt_b_1) == EXPECTED_V1_2_PROMPTS_SHA256[PROMPT_B_VERSION]
    assert "missing_facts" not in prompt_b_1


@pytest.mark.req("FR4.2")
@pytest.mark.req("FR4.5")
def test_prompt_evidence_numbering_matches_source_map_and_requires_index_only():
    items = [_make_evidence(1), _make_evidence(2), _make_evidence(3)]
    ctx = ContextPayload(
        query_id="Q_MAP_01",
        query="Điều kiện kết hôn?",
        as_of_date="2026-11-23",
        as_of_date_source="user_input",
        evidence_items=items,
    )
    prompt = build_controlled_rag_prompt(ctx)
    assert "từ [1] đến [3]" in prompt
    assert "[1] " in prompt and "[2] " in prompt and "[3] " in prompt and "[4] " not in prompt
    assert "TUYỆT ĐỐI KHÔNG chép chuỗi mã chunk_id dài" in prompt

    valid, invalid = map_evidence_indices_to_citations([3, 1, 3, 5, 0], ctx)
    assert [c.evidence_index for c in valid] == [3, 1]
    assert [c.chunk_id for c in valid] == [ctx.source_map[3]["chunk_id"], ctx.source_map[1]["chunk_id"]]
    assert invalid == [5, 0]


@pytest.mark.req("FR4.3")
@pytest.mark.req("FR4.4")
def test_prompt_v1_3_renders_as_of_effectivity_labels_and_closed_missing_facts():
    active_hist = _make_evidence(
        1,
        effective_from="2001-01-01",
        effective_to="2015-01-01",
        validity_status="Hết hiệu lực",
        point_ref="Điểm a",
    )
    future_law = _make_evidence(2, effective_from="2015-01-01", effective_to=None)
    undated = _make_evidence(3, effective_from=None, effective_to=None, validity_status="Còn hiệu lực")
    ctx = ContextPayload(
        query_id="Q_V13_01",
        query="Quy định áp dụng năm 2010 và còn thiếu dữ kiện kết hôn?",
        as_of_date="2010-06-01",
        as_of_date_source="benchmark",
        evidence_items=[active_hist, future_law, undated],
    )

    assert "Còn hiệu lực tại 2010-06-01" in format_effectivity_at_as_of_date(active_hist, "2010-06-01")
    assert "Chưa có hiệu lực tại 2010-06-01" in format_effectivity_at_as_of_date(future_law, "2010-06-01")
    assert "Hết hiệu lực tại 2015-01-01" in format_effectivity_at_as_of_date(active_hist, "2015-01-01")
    assert "Chưa đủ mốc ngày hiệu lực" in format_effectivity_at_as_of_date(undated, "2010-06-01")

    prompt_v13 = build_controlled_rag_prompt(ctx, prompt_version=PROMPT_B_V1_3_VERSION)
    assert f"Phiên bản hướng dẫn: {PROMPT_B_V1_3_VERSION}" in prompt_v13
    assert "Hiệu lực tại 2010-06-01: Còn hiệu lực tại 2010-06-01" in prompt_v13
    assert "Hiệu lực tại 2010-06-01: Chưa có hiệu lực tại 2010-06-01" in prompt_v13
    assert "Điểm a" in prompt_v13
    assert '"missing_facts"' in prompt_v13
    for code in MISSING_FACTS_TAXONOMY:
        assert f"`{code}`" in prompt_v13

    assert validate_missing_facts(["ngay_su_kien", "tuoi_cac_ben"]) == ["ngay_su_kien", "tuoi_cac_ben"]
    with pytest.raises(ValueError, match="ngoài danh mục đóng"):
        validate_missing_facts(["custom_invented_label"])

    with pytest.raises(ValueError, match="không được hỗ trợ"):
        build_controlled_rag_prompt(ctx, prompt_version="v9.9_unknown")

    with pytest.raises(ValueError, match="không được để rỗng"):
        build_controlled_rag_prompt_v1_3(ctx, missing_facts_taxonomy=[])


@pytest.mark.req("FR4.6")
@pytest.mark.req("FR4.6-AC2")
def test_prompt_template_modification_without_version_bump_fails_integrity_check(tmp_path: Path):
    actual = verify_prompt_template_integrity()
    assert actual[PROMPT_B_V1_3_VERSION] == EXPECTED_TEMPLATE_SHA256[PROMPT_B_V1_3_VERSION]

    tampered = tmp_path / "legal_rag_prompt_v1_3.md"
    original_text = PROMPT_TEMPLATE_FILES[PROMPT_B_V1_3_VERSION].read_text(encoding="utf-8")
    tampered.write_text(original_text + "\nSửa lén nội dung nhưng giữ nguyên version.\n", encoding="utf-8")

    with pytest.raises(ValueError, match="chưa nâng phiên bản"):
        verify_prompt_template_integrity(
            template_paths={PROMPT_B_V1_3_VERSION: tampered},
            expected_hashes={PROMPT_B_V1_3_VERSION: EXPECTED_TEMPLATE_SHA256[PROMPT_B_V1_3_VERSION]},
        )
