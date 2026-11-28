"""
generation/prompt_builder.py
Prompt Builder & Evidence Numbering [1]...[5] for Sprint 9 (Task D3.2).
Complies with DoD-09 and DoD-11.
"""
from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

from schemas.models import ContextPayload, EvidenceItem, MappedCitation

# 1. Phiên bản prompt. Khóa tại M1 (v1.0_*_m1); v1.1 thêm quy tắc ngôn ngữ/nguồn luật; v1.2 tăng cường khóa ngôn ngữ/nguồn luật cho A
#    Run B 10/11 (HN_025, HN_062 trả lời tiếng Trung, dẫn luật Trung Quốc). Cần Tech Lead duyệt (P45-10).
#    Prompt B v1.2 thu hẹp quy tắc 4 (hỏi lại) sau Run B 13/11 (HN_016 trả lời đúng nhưng đòi hỏi lại).
PROMPT_A_VERSION: str = "v1.2_zero_shot"
PROMPT_B_VERSION: str = "v1.2_controlled_rag"
PROMPT_B_V1_3_VERSION: str = "v1.3_controlled_rag"
OFFICIAL_PROMPT_A_VERSION: str = PROMPT_A_VERSION
OFFICIAL_PROMPT_B_VERSION: str = PROMPT_B_VERSION

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
PROMPT_TEMPLATE_FILES: dict[str, Path] = {
    "v1.0_spec": _PROMPTS_DIR / "legal_rag_prompt_v1_0.md",
    PROMPT_B_V1_3_VERSION: _PROMPTS_DIR / "legal_rag_prompt_v1_3.md",
}
EXPECTED_TEMPLATE_SHA256: dict[str, str] = {
    "v1.0_spec": "4e8e9bae20447b5b01caebeb7be0dbe994f137b52f4f4f5620b4fa6f83997669",
    PROMPT_B_V1_3_VERSION: "fca5e25399b63c8734e7d5a5be8a30d4dd18a80c9240679bbc776c82e881a211",
}
EXPECTED_V1_2_PROMPTS_SHA256: dict[str, str] = {
    PROMPT_A_VERSION: "c5c45e90894e9d58984f4c2b71a2fdaad75cf090a0323be1cde16bf2f918893b",
    PROMPT_B_VERSION: "5a19fe70f42efbb101945888d1f4cec8548f78a9a8b704bd31b68acfb4b75940",
}
EXPECTED_V1_3_PROMPT_SHA256: str = "f301d91b716354abbbf49cb95a8a2d493f648f524ae2f18dc34b18f5a49a1efb"

DEFAULT_MISSING_FACTS_CONFIG_PATH: Path = (
    Path(__file__).resolve().parents[1] / "configs" / "missing_facts_taxonomy.yaml"
)
REQUIRED_MISSING_FACTS_CONFIG_KEYS: tuple[str, ...] = (
    "taxonomy_version",
    "categories",
    "generic_clarification_message",
)


class MissingFactsConfigError(ValueError):
    """Lỗi fail-fast khi cấu hình danh mục missing_facts bị thiếu hoặc không hợp lệ (NFR5.1)."""


@dataclass(frozen=True)
class MissingFactsConfig:
    """Cấu hình danh mục đóng missing_facts và mẫu câu hỏi làm rõ cố định (FR3.4, FR3.6, NFR4.3)."""

    taxonomy_version: str
    generic_clarification_message: str
    descriptions: dict[str, str]
    clarification_templates: dict[str, str]
    taxonomy: tuple[str, ...]
    config_sha256: str


def _normalized_file_sha256(path: Path) -> str:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _require_non_empty_str(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MissingFactsConfigError(f"Cấu hình missing_facts thiếu hoặc rỗng trường bắt buộc '{label}'.")
    return value.strip()


def load_missing_facts_config(config_path: str | Path | None = None) -> MissingFactsConfig:
    """Nạp và kiểm tra nghiêm ngặt file YAML danh mục missing_facts (NFR5.1, NFR4.3)."""
    if config_path is None:
        path = DEFAULT_MISSING_FACTS_CONFIG_PATH
    elif isinstance(config_path, (str, Path)):
        path = Path(config_path)
    else:
        raise MissingFactsConfigError(
            f"config_path phải là str, Path hoặc None, nhận được {type(config_path).__name__}."
        )

    if not path.exists() or not path.is_file():
        raise MissingFactsConfigError(f"Thiếu file cấu hình danh mục missing_facts tại '{path}'.")

    try:
        raw_text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise MissingFactsConfigError(
            f"Không đọc được file cấu hình missing_facts '{path}' theo chuẩn UTF-8: {exc}"
        ) from exc

    try:
        loaded = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise MissingFactsConfigError(
            f"File cấu hình missing_facts '{path}' có cú pháp YAML không hợp lệ: {exc}"
        ) from exc

    if not isinstance(loaded, Mapping):
        raise MissingFactsConfigError(
            f"Cấu hình missing_facts '{path}' phải có root là mapping YAML."
        )

    missing_keys = [key for key in REQUIRED_MISSING_FACTS_CONFIG_KEYS if key not in loaded]
    if missing_keys:
        raise MissingFactsConfigError(
            f"Cấu hình missing_facts '{path}' thiếu khóa bắt buộc: {missing_keys}."
        )

    taxonomy_version = _require_non_empty_str(loaded["taxonomy_version"], label="taxonomy_version")
    generic_message = _require_non_empty_str(
        loaded["generic_clarification_message"], label="generic_clarification_message"
    )

    raw_categories = loaded["categories"]
    if not isinstance(raw_categories, Mapping) or not raw_categories:
        raise MissingFactsConfigError(
            f"Khóa 'categories' trong '{path}' phải là mapping khác rỗng."
        )

    descriptions: dict[str, str] = {}
    clarification_templates: dict[str, str] = {}
    for raw_code, raw_entry in raw_categories.items():
        code = _require_non_empty_str(raw_code, label="categories.<code_key>")
        if code != raw_code or any(ch.isspace() for ch in code):
            raise MissingFactsConfigError(
                f"Mã nhóm missing_facts '{raw_code}' trong '{path}' không được chứa khoảng trắng."
            )
        if not isinstance(raw_entry, Mapping):
            raise MissingFactsConfigError(
                f"Nhóm '{code}' trong '{path}' phải là mapping chứa 'description' và 'clarification_template'."
            )
        descriptions[code] = _require_non_empty_str(
            raw_entry.get("description"), label=f"categories.{code}.description"
        )
        clarification_templates[code] = _require_non_empty_str(
            raw_entry.get("clarification_template"), label=f"categories.{code}.clarification_template"
        )

    return MissingFactsConfig(
        taxonomy_version=taxonomy_version,
        generic_clarification_message=generic_message,
        descriptions=descriptions,
        clarification_templates=clarification_templates,
        taxonomy=tuple(descriptions.keys()),
        config_sha256=_normalized_file_sha256(path),
    )


MISSING_FACTS_CONFIG: MissingFactsConfig = load_missing_facts_config()
MISSING_FACTS_TAXONOMY_VERSION: str = MISSING_FACTS_CONFIG.taxonomy_version
MISSING_FACTS_CONFIG_SHA256: str = MISSING_FACTS_CONFIG.config_sha256
# Danh mục đóng (closed taxonomy) và mẫu câu hỏi làm rõ cho trường missing_facts (FR3.4, FR3.6, FR4.4, D-11).
MISSING_FACTS_DESCRIPTIONS: dict[str, str] = dict(MISSING_FACTS_CONFIG.descriptions)
MISSING_FACTS_CLARIFICATION_TEMPLATES: dict[str, str] = dict(
    MISSING_FACTS_CONFIG.clarification_templates
)
GENERIC_CLARIFICATION_MESSAGE: str = MISSING_FACTS_CONFIG.generic_clarification_message
MISSING_FACTS_TAXONOMY: tuple[str, ...] = MISSING_FACTS_CONFIG.taxonomy
_TEMPLATE_BLOCK_RE = re.compile(r"```text\r?\n(.*?)\r?\n```", re.DOTALL)

# Quy tắc ngôn ngữ và nguồn luật (P45-1): Prompt B là quy tắc 6, Prompt A là quy tắc 5
LANGUAGE_RULE_B: str = (
    "NGÔN NGỮ VÀ NGUỒN LUẬT: Trường \"answer\" phải viết hoàn toàn bằng tiếng Việt, không dùng chữ Hán "
    "hay ngôn ngữ khác. Chỉ áp dụng pháp luật nước Cộng hòa Xã hội Chủ nghĩa Việt Nam được cung cấp trong "
    "các đoạn bằng chứng; tuyệt đối không viện dẫn pháp luật nước ngoài và không sử dụng kiến thức tiền huấn "
    "luyện về pháp luật Trung Quốc (như Bộ luật Dân sự Trung Quốc, Luật Hôn nhân Trung Quốc, các cơ quan/"
    "thuật ngữ pháp lý Trung Quốc) hay bất kỳ quốc gia nào khác để suy diễn, bổ sung hoặc giải thích."
)
LANGUAGE_RULE_A: str = (
    "NGÔN NGỮ VÀ NGUỒN LUẬT: Câu trả lời phải viết hoàn toàn bằng tiếng Việt, không dùng chữ Hán "
    "hay ngôn ngữ khác. Chỉ áp dụng pháp luật nước Cộng hòa Xã hội Chủ nghĩa Việt Nam; tuyệt đối không "
    "viện dẫn pháp luật nước ngoài và không sử dụng kiến thức về pháp luật Trung Quốc (như Bộ luật Dân sự "
    "Trung Quốc, Luật Hôn nhân Trung Quốc, các cơ quan/thuật ngữ pháp lý Trung Quốc) hay bất kỳ quốc gia nào khác."
)

# Quy tắc 4 của Prompt B (v1.2): chỉ hỏi lại khi bằng chứng dẫn tới kết luận khác nhau tùy dữ kiện còn thiếu
CLARIFICATION_RULE_B: str = (
    "   - Chỉ đặt \"needs_clarification\": true khi câu hỏi thiếu dữ kiện đến mức các đoạn bằng chứng dẫn tới "
    "những kết luận khác nhau tùy dữ kiện còn thiếu, nên không thể trả lời nếu chưa hỏi lại người dùng.\n"
    "   - Nếu bằng chứng đã trả lời được câu hỏi theo quy định chung, hãy trả lời, nêu kèm các ngoại lệ có trong "
    "bằng chứng, và đặt \"needs_clarification\": false."
)

# Cố định câu Disclaimer chuẩn theo yêu cầu Sprint 9
STANDARD_DISCLAIMER: str = "Thông tin chỉ mang tính tham khảo, không thay thế tư vấn pháp lý chuyên nghiệp."


def get_prompt_hash(prompt_text: str) -> str:
    """Trả về mã băm SHA-256 của nội dung prompt để kiểm toán provenance."""
    return hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()


def format_effectivity_at_as_of_date(item: EvidenceItem, as_of_date: str) -> str:
    """Xác định nhãn hiệu lực tại ``as_of_date`` theo khoảng nửa mở ``[effective_from, effective_to)``."""
    target = date.fromisoformat(as_of_date.strip())
    eff_from = date.fromisoformat(item.effective_from) if item.effective_from else None
    eff_to = date.fromisoformat(item.effective_to) if item.effective_to else None

    if eff_from is not None and target < eff_from:
        return f"Chưa có hiệu lực tại {target.isoformat()} (hiệu lực từ {eff_from.isoformat()})"
    if eff_to is not None and target >= eff_to:
        return f"Hết hiệu lực tại {target.isoformat()} (hết hiệu lực từ {eff_to.isoformat()})"
    if eff_from is not None or eff_to is not None:
        return (
            f"Còn hiệu lực tại {target.isoformat()} "
            f"([{item.effective_from or '...'}, {item.effective_to or 'chưa hết hiệu lực'}))"
        )
    return f"Chưa đủ mốc ngày hiệu lực tại {target.isoformat()} (nhãn nguồn: {item.validity_status})"


def format_evidence_item(item: EvidenceItem, *, as_of_date: str | None = None) -> str:
    """
    Format từng mảnh bằng chứng theo định dạng chuẩn:
    [{item.evidence_index}] {item.document_title or item.document_id} ({item.document_number or ''}) | {item.breadcrumb or item.article_id} | Hiệu lực: {item.validity_status} ({item.effective_from or ''} -> {item.effective_to or ''})
    Nội dung: {item.content}
    """
    doc_title = item.document_title or item.document_id
    doc_number = f" ({item.document_number})" if item.document_number else ""
    breadcrumb = item.breadcrumb or item.article_id
    eff_from = item.effective_from or ""
    eff_to = item.effective_to or ""

    if as_of_date is None:
        return (
            f"[{item.evidence_index}] {doc_title}{doc_number} | {breadcrumb} | "
            f"Hiệu lực: {item.validity_status} ({eff_from} -> {eff_to})\n"
            f"Nội dung: {item.content.strip()}"
        )

    eff_label = format_effectivity_at_as_of_date(item, as_of_date)
    point_suffix = f" > {item.point_ref}" if item.point_ref and item.point_ref not in breadcrumb else ""
    return (
        f"[{item.evidence_index}] {doc_title}{doc_number} | {breadcrumb}{point_suffix} | "
        f"Hiệu lực tại {as_of_date.strip()}: {eff_label} | Nhãn nguồn: {item.validity_status} ({eff_from} -> {eff_to})\n"
        f"Nội dung: {item.content.strip()}"
    )


def build_zero_shot_prompt(
    query: str,
    as_of_date: str,
) -> str:
    """
    Xây dựng Prompt A cho Run A (Zero-Shot Qwen2.5:7b, không có ngữ cảnh RAG).
    Khóa duy nhất một biến thể nhận as_of_date rõ ràng.
    Đánh số thứ tự quy tắc 1, 2, 3, 4, 5 liên tục; v1.2 khóa nguồn pháp luật Việt Nam, giữ tiếng Việt,
    không chuyển luật nước ngoài thành luật Việt Nam và phân biệt điều chưa nhớ với trường hợp luật không quy định.
    """
    as_of_date_clean = as_of_date.strip()
    prompt_lines = [
        "Bạn là trợ lý tư vấn pháp luật chuyên sâu về lĩnh vực Hôn nhân và Gia đình Việt Nam.",
        f"Phiên bản hướng dẫn: {PROMPT_A_VERSION}",
        f"LƯU Ý QUAN TRỌNG: {STANDARD_DISCLAIMER}",
        "",
        "QUY TẮC TRẢ LỜI:",
        "1. Chỉ trả lời các câu hỏi trong phạm vi pháp luật Hôn nhân và Gia đình Việt Nam.",
        "2. Nếu câu hỏi nằm ngoài phạm vi này hoặc không đủ thông tin để xác định bản chất pháp lý, hãy từ chối lịch sự và nêu rõ lý do.",
        f"3. Mốc kiểm tra hiệu lực pháp luật là {as_of_date_clean}; đây chỉ là mốc để xác định văn bản nào đang có hiệu lực, không hàm ý quy định đã thay đổi. Với câu hỏi thông thường về nội dung của một luật Việt Nam được nêu rõ, hãy trả lời trực tiếp theo quy định đó; không tự thêm lời dẫn về ngày và không suy đoán có sửa đổi nếu không chắc. Chỉ nêu \"Theo quy định có hiệu lực tại ngày {as_of_date_clean}...\" khi câu hỏi hỏi về thời điểm, lịch sử hoặc hiệu lực pháp luật, hoặc khi mốc ngày thực sự làm thay đổi câu trả lời.",
        f"4. Cuối câu trả lời luôn đính kèm câu khuyến cáo: \"{STANDARD_DISCLAIMER}\".",
        f"5. {LANGUAGE_RULE_A}",
        "",
        f"CÂU HỎI: {query.strip()}",
        "",
        "YÊU CẦU ĐẦU RA ƯU TIÊN CAO NHẤT: Chỉ trả lời theo pháp luật Việt Nam; không lấy hoặc dịch quy định nước ngoài thành câu trả lời về pháp luật Việt Nam. Nếu không nhớ chắc, nêu rõ điểm chưa chắc; không biến việc không nhớ thành khẳng định rằng luật không quy định. Khi biết quy tắc được hỏi, trả lời trực tiếp. Viết toàn bộ câu trả lời bằng tiếng Việt, dùng chữ Quốc ngữ từ đầu đến cuối.",
        "TRẢ LỜI:",
    ]

    return "\n".join(prompt_lines)


def validate_missing_facts(
    missing_facts: Sequence[str],
    *,
    allowed: Sequence[str] = MISSING_FACTS_TAXONOMY,
) -> list[str]:
    """Kiểm tra ``missing_facts`` chỉ dùng mã thuộc danh mục đóng (closed taxonomy)."""
    allowed_set = set(allowed)
    invalid = [code for code in missing_facts if code not in allowed_set]
    if invalid:
        raise ValueError(
            f"missing_facts chứa mã ngoài danh mục đóng {sorted(allowed_set)}: {invalid}"
        )
    return list(missing_facts)


def filter_missing_facts(
    missing_facts: Sequence[str] | None,
    *,
    allowed: Sequence[str] | None = None,
    config: MissingFactsConfig | None = None,
) -> tuple[list[str], list[str]]:
    """Lọc ``missing_facts`` thô từ model: giữ mã hợp lệ theo thứ tự (khử trùng), bỏ giá trị lạ (FR3.4-AC4)."""
    if missing_facts is None:
        return [], []
    if isinstance(missing_facts, (str, bytes)) or not isinstance(missing_facts, Sequence):
        raise TypeError(
            f"missing_facts phải là Sequence[str] hoặc None, nhận được {type(missing_facts).__name__}."
        )

    cfg = config or MISSING_FACTS_CONFIG
    allowed_set = set(allowed) if allowed is not None else set(cfg.taxonomy)
    accepted: list[str] = []
    dropped: list[str] = []
    seen: set[str] = set()
    for raw_item in missing_facts:
        if not isinstance(raw_item, str):
            dropped.append(repr(raw_item))
            continue
        code = raw_item.strip()
        if code in allowed_set:
            if code not in seen:
                seen.add(code)
                accepted.append(code)
        else:
            dropped.append(raw_item)
    return accepted, dropped


def build_clarification_message(
    missing_facts: Sequence[str] | None,
    *,
    config: MissingFactsConfig | None = None,
) -> str:
    """Dựng câu hỏi làm rõ cố định từ cấu hình ``missing_facts`` hoặc rơi về thông báo chung FR3.6."""
    cfg = config or MISSING_FACTS_CONFIG
    valid_codes, _ = filter_missing_facts(missing_facts, config=cfg)
    if not valid_codes:
        return cfg.generic_clarification_message
    if len(valid_codes) == 1:
        return (
            "Để tra cứu chính xác quy định pháp luật Hôn nhân và gia đình Việt Nam, "
            f"vui lòng làm rõ thêm: {cfg.clarification_templates[valid_codes[0]]}"
        )
    lines = "\n".join(f"- {cfg.clarification_templates[code]}" for code in valid_codes)
    return (
        "Để tra cứu chính xác quy định pháp luật Hôn nhân và gia đình Việt Nam, "
        f"vui lòng cung cấp thêm các dữ kiện sau:\n{lines}"
    )


def verify_prompt_template_integrity(
    template_paths: dict[str, Path] | None = None,
    expected_hashes: dict[str, str] | None = None,
) -> dict[str, str]:
    """Đảm bảo nội dung template không bị sửa mà chưa nâng hằng phiên bản (FR4.6-AC2)."""
    paths = template_paths or PROMPT_TEMPLATE_FILES
    expected = expected_hashes or EXPECTED_TEMPLATE_SHA256
    actual: dict[str, str] = {}
    for version_key, path in paths.items():
        if not path.exists():
            raise FileNotFoundError(f"Thiếu file template prompt cho {version_key}: {path}")
        digest = _normalized_file_sha256(path)
        actual[version_key] = digest
        exp_digest = expected.get(version_key)
        if exp_digest is not None and digest != exp_digest:
            raise ValueError(
                f"Template prompt {version_key} ({path.name}) đã bị thay đổi "
                f"(expected={exp_digest}, actual={digest}) nhưng chưa nâng phiên bản."
            )

    if template_paths is None and expected_hashes is None:
        # Khóa bất biến SHA-256 cho prompt official v1.2 và prompt v1.3 dựng từ cấu hình
        sample_ev = EvidenceItem(
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
        sample_ctx = ContextPayload(
            query_id="CANONICAL_V12",
            query="Tuổi kết hôn hợp pháp của nam và nữ?",
            as_of_date="2026-10-15",
            as_of_date_source="benchmark",
            evidence_items=[sample_ev],
        )
        hash_a = get_prompt_hash(build_zero_shot_prompt(sample_ctx.query, sample_ctx.as_of_date))
        hash_b = get_prompt_hash(_build_controlled_rag_prompt_v1_2(sample_ctx))
        hash_b13 = get_prompt_hash(build_controlled_rag_prompt_v1_3(sample_ctx))
        if hash_a != EXPECTED_V1_2_PROMPTS_SHA256[PROMPT_A_VERSION]:
            raise ValueError(
                f"Nội dung official {PROMPT_A_VERSION} đã bị thay đổi nhưng chưa nâng phiên bản."
            )
        if hash_b != EXPECTED_V1_2_PROMPTS_SHA256[PROMPT_B_VERSION]:
            raise ValueError(
                f"Nội dung official {PROMPT_B_VERSION} đã bị thay đổi nhưng chưa nâng phiên bản."
            )
        if hash_b13 != EXPECTED_V1_3_PROMPT_SHA256:
            raise ValueError(
                f"Nội dung {PROMPT_B_V1_3_VERSION} đã bị thay đổi nhưng chưa nâng phiên bản."
            )
        actual[PROMPT_A_VERSION] = hash_a
        actual[PROMPT_B_VERSION] = hash_b
        actual[f"{PROMPT_B_V1_3_VERSION}_rendered"] = hash_b13
    return actual


def _load_v1_3_template(template_path: Path | None = None) -> str:
    path = template_path or PROMPT_TEMPLATE_FILES[PROMPT_B_V1_3_VERSION]
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    match = _TEMPLATE_BLOCK_RE.search(text)
    if not match:
        raise ValueError(f"Không tìm thấy block ```text trong template {path}")
    return match.group(1)


def _build_controlled_rag_prompt_v1_2(context_payload: ContextPayload) -> str:
    if not context_payload.evidence_items:
        raise ValueError("Empty retrieval: không có bằng chứng để tạo prompt.")

    query = context_payload.query.strip()
    as_of_date = context_payload.as_of_date.strip()
    evidence_count = len(context_payload.evidence_items)

    evidence_blocks = [format_evidence_item(item) for item in context_payload.evidence_items]
    context_str = "\n\n".join(evidence_blocks)

    prompt = f"""Bạn là trợ lý pháp lý phân tích chuyên sâu tuân thủ nghiêm ngặt bằng chứng (Controlled Legal RAG).
Phiên bản hướng dẫn: {PROMPT_B_VERSION}
Khuyến cáo bắt buộc: {STANDARD_DISCLAIMER}

QUY TẮC PHẠM VI:
Chỉ tư vấn trong phạm vi pháp luật Hôn nhân và Gia đình Việt Nam.

MỐC THỜI GIAN TRA CỨU: {as_of_date}
Khi trả lời câu hỏi gắn với mốc thời gian/hiệu lực, câu trả lời phải nêu rõ: "Theo quy định có hiệu lực tại ngày {as_of_date}...".

DANH SÁCH BẰNG CHỨNG PHÁP LÝ ĐƯỢC CẤP (Được đánh số từ [1] đến [{evidence_count}]):
{context_str}

RÀNG BUỘC NGHIÊM NGẶT (DEFENSIVE CONSTRAINTS):
1. NGUYÊN TẮC ĐÓNG NGỮ CẢNH (STRICT CLOSED-CONTEXT): CHỈ sử dụng thông tin có thật trong các đoạn bằng chứng [1]...[{evidence_count}] ở trên để trả lời. Mọi khẳng định pháp lý trong câu trả lời bắt buộc phải có căn cứ trực tiếp từ nội dung [1]...[{evidence_count}]; TUYỆT ĐỐI KHÔNG tự suy diễn hoặc dùng kiến thức ngoài các đoạn bằng chứng này.
2. VỀ TRÍCH DẪN: Chỉ trả về chỉ số bằng chứng dưới dạng mảng các số nguyên trong trường "evidence_indices" (ví dụ: [1, 2]). TUYỆT ĐỐI KHÔNG chép chuỗi mã chunk_id dài vào câu trả lời hay mảng trích dẫn.
3. VỀ TỪ CHỐI TRẢ LỜI (ABSTENTION):
   - Nếu các đoạn bằng chứng trên không đề cập đến tình tiết được hỏi, không đủ thông tin/căn cứ để kết luận, hoặc chứa mâu thuẫn về hiệu lực/thứ bậc không thể giải quyết tại mốc {as_of_date}, bạn BẮT BUỘC phải đặt "abstained": true và từ chối trả lời (thay vì tự bổ sung kiến thức ngoài), nêu rõ lý do trong "abstention_reason", và giải thích ngắn gọn trong "answer".
4. VỀ CÂU HỎI MƠ HỒ:
{CLARIFICATION_RULE_B}
5. Luôn đính kèm khuyến cáo pháp lý: "{STANDARD_DISCLAIMER}".
6. {LANGUAGE_RULE_B}

YÊU CẦU ĐẦU RA:
Bạn PHẢI trả về duy nhất một đối tượng JSON hợp lệ (không kèm markdown code block bên ngoài nếu dùng format JSON) tuân thủ đúng cấu trúc sau:
{{
  "answer": "Nội dung câu trả lời pháp lý chi tiết kèm khuyến cáo hoặc thông báo từ chối.",
  "evidence_indices": [1, 2],
  "abstained": false,
  "abstention_reason": null,
  "needs_clarification": false
}}

CÂU HỎI CẦN GIẢI QUYẾT:
{query}
"""
    return prompt.strip()


def build_controlled_rag_prompt_v1_3(
    context_payload: ContextPayload,
    *,
    missing_facts_taxonomy: Sequence[str] | None = None,
    template_path: Path | None = None,
    config: MissingFactsConfig | None = None,
) -> str:
    """Xây dựng Prompt B phiên bản thử nghiệm v1.3 có nhãn hiệu lực tại as_of_date và danh mục đóng missing_facts."""
    if not context_payload.evidence_items:
        raise ValueError("Empty retrieval: không có bằng chứng để tạo prompt.")
    cfg = config or MISSING_FACTS_CONFIG
    allowed_facts = list(cfg.taxonomy if missing_facts_taxonomy is None else missing_facts_taxonomy)
    if not allowed_facts:
        raise ValueError("Danh mục đóng missing_facts không được để rỗng.")
    validate_missing_facts(allowed_facts, allowed=allowed_facts)

    as_of_date = context_payload.as_of_date.strip()
    evidence_blocks = [
        format_evidence_item(item, as_of_date=as_of_date) for item in context_payload.evidence_items
    ]
    descriptions = cfg.descriptions if config is not None else MISSING_FACTS_DESCRIPTIONS
    catalog_lines = [
        f"     * `{code}`: {descriptions.get(code, code)}"
        for code in allowed_facts
    ]
    template = _load_v1_3_template(template_path)
    return template.format(
        prompt_version=PROMPT_B_V1_3_VERSION,
        disclaimer=STANDARD_DISCLAIMER,
        as_of_date=as_of_date,
        evidence_count=len(context_payload.evidence_items),
        context_str="\n\n".join(evidence_blocks),
        clarification_rule=CLARIFICATION_RULE_B,
        missing_facts_catalog="\n".join(catalog_lines),
        language_rule=LANGUAGE_RULE_B,
        query=context_payload.query.strip(),
    ).strip()


def build_controlled_rag_prompt(
    context_payload: ContextPayload,
    *,
    prompt_version: str = OFFICIAL_PROMPT_B_VERSION,
    missing_facts_taxonomy: Sequence[str] = MISSING_FACTS_TAXONOMY,
) -> str:
    """
    Xây dựng Prompt B cho Run B (Controlled RAG với ngữ cảnh tối đa 5 EvidenceItem).
    Mặc định dùng bản official v1.2 bất biến; truyền ``prompt_version=PROMPT_B_V1_3_VERSION``
    để dựng prompt thử nghiệm v1.3.
    """
    if prompt_version == PROMPT_B_VERSION:
        return _build_controlled_rag_prompt_v1_2(context_payload)
    if prompt_version == PROMPT_B_V1_3_VERSION:
        return build_controlled_rag_prompt_v1_3(
            context_payload, missing_facts_taxonomy=missing_facts_taxonomy
        )
    raise ValueError(f"Phiên bản Prompt B không được hỗ trợ: {prompt_version!r}")


def map_evidence_indices_to_citations(
    evidence_indices: list[int],
    context_payload: ContextPayload,
) -> tuple[list[MappedCitation], list[int]]:
    """
    Ánh xạ ngược các chỉ số [1]...[5] mà LLM trả về thành danh sách MappedCitation đầy đủ.
    Khử trùng lặp chỉ số nhưng giữ nguyên thứ tự xuất hiện ban đầu.
    Trả về:
      - valid_citations: Danh sách MappedCitation khớp với source_map
      - invalid_indices: Danh sách các chỉ số không hợp lệ (ngoài 1..n hoặc không nằm trong source_map)
    """
    valid_citations: list[MappedCitation] = []
    invalid_indices: list[int] = []

    # Khử trùng lặp chỉ số giữ nguyên thứ tự
    seen: set[int] = set()
    deduped_indices: list[int] = []
    for idx in evidence_indices:
        if idx not in seen:
            seen.add(idx)
            deduped_indices.append(idx)

    source_map = context_payload.source_map

    for idx in deduped_indices:
        # Kiểm tra chỉ số số nguyên và phạm vi hợp lệ
        if not isinstance(idx, int) or isinstance(idx, bool) or idx < 1 or idx > 5:
            invalid_indices.append(idx)
            continue

        if idx not in source_map:
            invalid_indices.append(idx)
            continue

        info = source_map[idx]
        citation = MappedCitation(
            evidence_index=idx,
            chunk_id=str(info.get("chunk_id", "")),
            document_id=str(info.get("document_id", "")),
            article_id=str(info.get("article_id", "")),
            clause_id=str(info.get("clause_id", "")),
            parent_clause_id=info.get("parent_clause_id"),
        )
        valid_citations.append(citation)

    return valid_citations, invalid_indices
