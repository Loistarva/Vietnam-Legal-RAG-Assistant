"""Tests for externalized missing_facts taxonomy config, Active Clarification helpers, and byte-level prompt hash lock."""
from __future__ import annotations

from pathlib import Path

import pytest

from generation.prompt_builder import (
    DEFAULT_MISSING_FACTS_CONFIG_PATH,
    EXPECTED_TEMPLATE_SHA256,
    EXPECTED_V1_2_PROMPTS_SHA256,
    EXPECTED_V1_3_PROMPT_SHA256,
    GENERIC_CLARIFICATION_MESSAGE,
    MISSING_FACTS_CLARIFICATION_TEMPLATES,
    MISSING_FACTS_CONFIG,
    MISSING_FACTS_CONFIG_SHA256,
    MISSING_FACTS_DESCRIPTIONS,
    MISSING_FACTS_TAXONOMY,
    MISSING_FACTS_TAXONOMY_VERSION,
    PROMPT_A_VERSION,
    PROMPT_B_V1_3_VERSION,
    PROMPT_B_VERSION,
    REQUIRED_MISSING_FACTS_CONFIG_KEYS,
    MissingFactsConfigError,
    build_clarification_message,
    build_controlled_rag_prompt,
    build_controlled_rag_prompt_v1_3,
    build_zero_shot_prompt,
    filter_missing_facts,
    get_prompt_hash,
    load_missing_facts_config,
    validate_missing_facts,
    verify_prompt_template_integrity,
)
from schemas.models import ContextPayload, EvidenceItem


def _canonical_context() -> ContextPayload:
    ev = EvidenceItem(
        evidence_index=1,
        chunk_id="l_52_2014_qh13_art_8_clause_1_chunk_1",
        parent_clause_id="l_52_2014_qh13_art_8_clause_1",
        document_id="l_52_2014_qh13",
        document_title="Luật Hôn nhân và gia đình 2014",
        document_number="52/2014/QH13",
        article_id="art_8",
        clause_id="clause_1",
        breadcrumb="Chương II > Điều 8 > Khoản 1",
        content="Nam từ đủ 20 tuổi trở lên, nữ từ đủ 18 tuổi trở lên.",
        validity_status="Còn hiệu lực",
        effective_from="2015-01-01",
        effective_to=None,
    )
    return ContextPayload(
        query_id="CANONICAL_V12",
        query="Tuổi kết hôn hợp pháp của nam và nữ?",
        as_of_date="2026-10-15",
        as_of_date_source="benchmark",
        evidence_items=[ev],
    )


@pytest.mark.req("FR3.4")
@pytest.mark.req("FR4.4")
@pytest.mark.req("NFR4.3")
def test_missing_facts_config_loads_and_preserves_byte_identical_prompt_hashes():
    assert DEFAULT_MISSING_FACTS_CONFIG_PATH.exists()
    assert MISSING_FACTS_TAXONOMY_VERSION == "missing_facts_v1.0"
    assert len(MISSING_FACTS_CONFIG_SHA256) == 64
    assert len(MISSING_FACTS_TAXONOMY) == 10
    assert set(MISSING_FACTS_DESCRIPTIONS) == set(MISSING_FACTS_TAXONOMY)
    assert set(MISSING_FACTS_CLARIFICATION_TEMPLATES) == set(MISSING_FACTS_TAXONOMY)
    assert GENERIC_CLARIFICATION_MESSAGE == MISSING_FACTS_CONFIG.generic_clarification_message

    ctx = _canonical_context()
    prompt_a = build_zero_shot_prompt(ctx.query, ctx.as_of_date)
    prompt_b12 = build_controlled_rag_prompt(ctx, prompt_version=PROMPT_B_VERSION)
    prompt_b13 = build_controlled_rag_prompt_v1_3(ctx)

    assert get_prompt_hash(prompt_a) == EXPECTED_V1_2_PROMPTS_SHA256[PROMPT_A_VERSION]
    assert get_prompt_hash(prompt_b12) == EXPECTED_V1_2_PROMPTS_SHA256[PROMPT_B_VERSION]
    assert get_prompt_hash(prompt_b13) == EXPECTED_V1_3_PROMPT_SHA256

    integrity = verify_prompt_template_integrity()
    assert integrity[PROMPT_B_V1_3_VERSION] == EXPECTED_TEMPLATE_SHA256[PROMPT_B_V1_3_VERSION]
    assert integrity[f"{PROMPT_B_V1_3_VERSION}_rendered"] == EXPECTED_V1_3_PROMPT_SHA256


@pytest.mark.req("NFR5.1")
def test_missing_facts_config_fail_fast_on_missing_corrupt_or_incomplete_yaml(tmp_path: Path):
    # 1. File không tồn tại hoặc là thư mục
    with pytest.raises(MissingFactsConfigError, match="Thiếu file cấu hình"):
        load_missing_facts_config(tmp_path / "does_not_exist.yaml")

    cfg_dir = tmp_path / "cfg_dir"
    cfg_dir.mkdir()
    with pytest.raises(MissingFactsConfigError, match="Thiếu file cấu hình"):
        load_missing_facts_config(cfg_dir)

    # 2. Sai UTF-8 / hỏng cú pháp YAML
    bad_utf8 = tmp_path / "bad_utf8.yaml"
    bad_utf8.write_bytes(b"\xff\xfe\xfd")
    with pytest.raises(MissingFactsConfigError, match="UTF-8"):
        load_missing_facts_config(bad_utf8)

    bad_yaml = tmp_path / "bad_yaml.yaml"
    bad_yaml.write_text("taxonomy_version: [unclosed", encoding="utf-8")
    with pytest.raises(MissingFactsConfigError, match="YAML"):
        load_missing_facts_config(bad_yaml)

    # 3. Thiếu từng khóa bắt buộc
    base_yaml = (
        'taxonomy_version: "missing_facts_v1.0"\n'
        'generic_clarification_message: "Vui lòng bổ sung thêm dữ kiện."\n'
        "categories:\n"
        "  ngay_su_kien:\n"
        '    description: "Mốc thời gian"\n'
        '    clarification_template: "Sự kiện xảy ra vào ngày nào?"\n'
    )
    for key in REQUIRED_MISSING_FACTS_CONFIG_KEYS:
        lines = [line for line in base_yaml.splitlines() if not line.startswith(f"{key}:") and (key != "categories" or not line.startswith("  "))]
        incomplete_path = tmp_path / f"missing_{key}.yaml"
        incomplete_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        with pytest.raises(MissingFactsConfigError, match=key):
            load_missing_facts_config(incomplete_path)

    # 4. Thiếu clarification_template hoặc categories rỗng
    missing_tmpl = tmp_path / "missing_tmpl.yaml"
    missing_tmpl.write_text(
        'taxonomy_version: "missing_facts_v1.0"\n'
        'generic_clarification_message: "Vui lòng bổ sung."\n'
        "categories:\n"
        "  ngay_su_kien:\n"
        '    description: "Mốc thời gian"\n',
        encoding="utf-8",
    )
    with pytest.raises(MissingFactsConfigError, match="clarification_template"):
        load_missing_facts_config(missing_tmpl)

    empty_cats = tmp_path / "empty_cats.yaml"
    empty_cats.write_text(
        'taxonomy_version: "missing_facts_v1.0"\n'
        'generic_clarification_message: "Vui lòng bổ sung."\n'
        "categories: {}\n",
        encoding="utf-8",
    )
    with pytest.raises(MissingFactsConfigError, match="categories"):
        load_missing_facts_config(empty_cats)


@pytest.mark.req("FR3.4")
@pytest.mark.req("FR3.6")
def test_active_clarification_filters_unknown_codes_and_falls_back_to_generic():
    accepted, dropped = filter_missing_facts(
        ["ngay_su_kien", "nhan_la_ngoai_danh_muc", "ngay_su_kien", "tuoi_cac_ben"]
    )
    assert accepted == ["ngay_su_kien", "tuoi_cac_ben"]
    assert dropped == ["nhan_la_ngoai_danh_muc"]

    single_msg = build_clarification_message(["ngay_su_kien"])
    assert MISSING_FACTS_CLARIFICATION_TEMPLATES["ngay_su_kien"] in single_msg

    multi_msg = build_clarification_message(["ngay_su_kien", "nhan_la", "tinh_trang_dang_ky_ket_hon"])
    assert MISSING_FACTS_CLARIFICATION_TEMPLATES["ngay_su_kien"] in multi_msg
    assert MISSING_FACTS_CLARIFICATION_TEMPLATES["tinh_trang_dang_ky_ket_hon"] in multi_msg
    assert "nhan_la" not in multi_msg

    # Rơi về thông báo chung FR3.6 khi đầu vào rỗng hoặc toàn giá trị ngoài danh mục (FR3.4-AC4)
    assert build_clarification_message(["unknown_only", "also_invalid"]) == GENERIC_CLARIFICATION_MESSAGE
    assert build_clarification_message([]) == GENERIC_CLARIFICATION_MESSAGE
    assert build_clarification_message(None) == GENERIC_CLARIFICATION_MESSAGE

    # Backward compatibility: validate_missing_facts vẫn ném ValueError khi gặp mã lạ
    assert validate_missing_facts(["ngay_su_kien"]) == ["ngay_su_kien"]
    with pytest.raises(ValueError, match="ngoài danh mục đóng"):
        validate_missing_facts(["unknown_only"])
