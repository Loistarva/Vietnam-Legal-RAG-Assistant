# -*- coding: utf-8 -*-
"""
generation/prompt_builder.py
Prompt Builder & Evidence Numbering [1]...[5] for Sprint 9 (Task D3.2).
Complies with DoD-09 and DoD-11.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from schemas.models import ContextPayload, EvidenceItem, MappedCitation

# 1. Khóa phiên bản prompt tại M1
PROMPT_A_VERSION: str = "v1.0_zero_shot_m1"
PROMPT_B_VERSION: str = "v1.0_controlled_rag_m1"

# Cố định câu Disclaimer chuẩn theo yêu cầu Sprint 9
STANDARD_DISCLAIMER: str = (
    "Thông tin chỉ mang tính tham khảo, không thay thế tư vấn pháp lý chuyên nghiệp."
)


def format_evidence_item(item: EvidenceItem) -> str:
    """
    Format từng mảnh bằng chứng theo định dạng chuẩn:
    [1] Văn bản: ... | Điều/Khoản: ... | Hiệu lực: effective_from -> effective_to | Nội dung: ...
    """
    eff_from = item.effective_from if item.effective_from else "Không xác định"
    eff_to = item.effective_to if item.effective_to else "hiện tại"

    clause_info = f"{item.article_id} / {item.clause_id}"
    if item.parent_clause_id:
        clause_info = item.parent_clause_id

    return (
        f"[{item.evidence_index}] Văn bản: {item.document_id} | "
        f"Điều/Khoản: {clause_info} | "
        f"Hiệu lực: {eff_from} -> {eff_to} | "
        f"Nội dung: {item.content.strip()}"
    )


def build_zero_shot_prompt(
    query: str,
    as_of_date: Optional[str] = None,
    include_as_of_date: bool = True,
) -> str:
    """
    Xây dựng Prompt A cho Run A (Zero-Shot Qwen2.5:7b, không có ngữ cảnh RAG).
    Giới hạn phạm vi Hôn nhân & Gia đình Việt Nam; kèm quy tắc từ chối và disclaimer.
    """
    prompt_lines = [
        "Bạn là trợ lý tư vấn pháp luật chuyên sâu về lĩnh vực Hôn nhân và Gia đình Việt Nam.",
        f"Phiên bản hướng dẫn: {PROMPT_A_VERSION}",
        f"LƯU Ý QUAN TRỌNG: {STANDARD_DISCLAIMER}",
        "",
        "QUY TẮC TRẢ LỜI:",
        "1. Chỉ trả lời các câu hỏi trong phạm vi pháp luật Hôn nhân và Gia đình Việt Nam.",
        "2. Nếu câu hỏi nằm ngoài phạm vi này hoặc không đủ thông tin để xác định bản chất pháp lý, hãy từ chối lịch sự và nêu rõ lý do.",
    ]

    if include_as_of_date and as_of_date:
        prompt_lines.extend(
            [
                f"3. Thời điểm hiệu lực áp dụng: {as_of_date}.",
                f'   Khi trả lời câu hỏi gắn với mốc thời gian hoặc hiệu lực văn bản, câu trả lời phải nêu rõ: "Theo quy định có hiệu lực tại ngày {as_of_date}...".',
                "4. Đảm bảo căn cứ vào các văn bản pháp luật có hiệu lực tại mốc thời gian trên.",
            ]
        )
    else:
        prompt_lines.append(
            "3. Đảm bảo viện dẫn chính xác các văn bản quy phạm pháp luật liên quan."
        )

    prompt_lines.extend(
        [
            f'5. Cuối câu trả lời luôn đính kèm câu khuyến cáo: "{STANDARD_DISCLAIMER}".',
            "",
            f"CÂU HỎI: {query.strip()}",
            "",
            "TRẢ LỜI:",
        ]
    )

    return "\n".join(prompt_lines)


def build_controlled_rag_prompt(context_payload: ContextPayload) -> str:
    """
    Xây dựng Prompt B cho Run B (Controlled RAG với ngữ cảnh tối đa 5 EvidenceItem).
    Yêu cầu trả về đúng định dạng JSON khớp StructuredRAGOutput.
    """
    query = context_payload.query.strip()
    as_of_date = context_payload.as_of_date.strip()

    # Định dạng tối đa 5 bằng chứng [1]...[5]
    evidence_blocks: List[str] = []
    for item in context_payload.evidence_items[:5]:
        evidence_blocks.append(format_evidence_item(item))

    context_str = (
        "\n".join(evidence_blocks)
        if evidence_blocks
        else "Không có bằng chứng được cung cấp."
    )

    prompt = f"""Bạn là trợ lý pháp lý phân tích chuyên sâu tuân thủ nghiêm ngặt bằng chứng (Controlled Legal RAG).
Phiên bản hướng dẫn: {PROMPT_B_VERSION}
Khuyến cáo bắt buộc: {STANDARD_DISCLAIMER}

MỐC THỜI GIAN TRA CỨU: {as_of_date}
Khi trả lời câu hỏi gắn với mốc thời gian/hiệu lực, câu trả lời phải nêu rõ: "Theo quy định có hiệu lực tại ngày {as_of_date}...".

DANH SÁCH BẰNG CHỨNG PHÁP LÝ ĐƯỢC CẤP (Được đánh số từ [1] đến [{min(len(context_payload.evidence_items), 5)}]):
{context_str}

RÀNG BUỘC NGHIÊM NGẶT (DEFENSIVE CONSTRAINTS):
1. CHỈ sử dụng thông tin có thật trong các đoạn bằng chứng [1]...[{min(len(context_payload.evidence_items), 5)}] ở trên để trả lời. TUYỆT ĐỐI KHÔNG tự suy diễn hoặc dùng kiến thức ngoài các đoạn bằng chứng này.
2. VỀ TRÍCH DẪN: Chỉ trả về chỉ số bằng chứng dưới dạng mảng các số nguyên trong trường "evidence_indices" (ví dụ: [1, 3]). TUYỆT ĐỐI KHÔNG chép chuỗi mã chunk_id dài vào câu trả lời hay mảng trích dẫn.
3. VỀ TỪ CHỐI TRẢ LỜI (ABSTENTION):
   - Nếu các đoạn bằng chứng trên không đủ thông tin để trả lời câu hỏi, hoặc chứa mâu thuẫn về hiệu lực/thứ bậc không thể giải quyết tại mốc {as_of_date}, bạn BẮT BUỘC phải đặt "abstained": true, nêu rõ lý do trong "abstention_reason", và giải thích ngắn gọn trong "answer".
4. VỀ CÂU HỎI MƠ HỒ:
   - Nếu câu hỏi thiếu dữ kiện quan trọng cần làm rõ, đặt "needs_clarification": true.
5. Luôn đính kèm khuyến cáo pháp lý: "{STANDARD_DISCLAIMER}".

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


def map_evidence_indices_to_citations(
    evidence_indices: List[int],
    context_payload: ContextPayload,
) -> Tuple[List[MappedCitation], List[int]]:
    """
    Ánh xạ ngược các chỉ số [1]...[5] mà LLM trả về thành danh sách MappedCitation đầy đủ.
    Trả về:
      - valid_citations: Danh sách MappedCitation khớp với source_map
      - invalid_indices: Danh sách các chỉ số không hợp lệ (ngoài 1..5 hoặc không nằm trong source_map)
    """
    valid_citations: List[MappedCitation] = []
    invalid_indices: List[int] = []

    source_map = context_payload.source_map

    for idx in evidence_indices:
        # Kiểm tra chỉ số số nguyên và phạm vi [1, 5]
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
