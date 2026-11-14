"""
generation/prompt_builder.py
Prompt Builder & Evidence Numbering [1]...[5] for Sprint 9 (Task D3.2).
Complies with DoD-09 and DoD-11.
"""
from __future__ import annotations

import hashlib

from schemas.models import ContextPayload, EvidenceItem, MappedCitation

# 1. Phiên bản prompt. Khóa tại M1 (v1.0_*_m1); v1.1 thêm quy tắc ngôn ngữ và nguồn luật sau
#    Run B 10/11 (HN_025, HN_062 trả lời tiếng Trung, dẫn luật Trung Quốc). Cần Tech Lead duyệt (P45-10).
#    Prompt B v1.2 thu hẹp quy tắc 4 (hỏi lại) sau Run B 13/11 (HN_016 trả lời đúng nhưng đòi hỏi lại).
PROMPT_A_VERSION: str = "v1.1_zero_shot"
PROMPT_B_VERSION: str = "v1.2_controlled_rag"

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


def format_evidence_item(item: EvidenceItem) -> str:
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

    return (
        f"[{item.evidence_index}] {doc_title}{doc_number} | {breadcrumb} | "
        f"Hiệu lực: {item.validity_status} ({eff_from} -> {eff_to})\n"
        f"Nội dung: {item.content.strip()}"
    )


def build_zero_shot_prompt(
    query: str,
    as_of_date: str,
) -> str:
    """
    Xây dựng Prompt A cho Run A (Zero-Shot Qwen2.5:7b, không có ngữ cảnh RAG).
    Khóa duy nhất một biến thể nhận as_of_date rõ ràng.
    Đánh số thứ tự quy tắc 1, 2, 3, 4, 5 liên tục (quy tắc 5 = ngôn ngữ và nguồn luật, từ v1.1).
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
        f"3. Thời điểm hiệu lực áp dụng: {as_of_date_clean}. Khi trả lời câu hỏi gắn với mốc thời gian hoặc hiệu lực văn bản, câu trả lời phải nêu rõ: \"Theo quy định có hiệu lực tại ngày {as_of_date_clean}...\". Đảm bảo căn cứ vào các văn bản pháp luật có hiệu lực tại mốc thời gian trên.",
        f"4. Cuối câu trả lời luôn đính kèm câu khuyến cáo: \"{STANDARD_DISCLAIMER}\".",
        f"5. {LANGUAGE_RULE_A}",
        "",
        f"CÂU HỎI: {query.strip()}",
        "",
        "TRẢ LỜI:",
    ]

    return "\n".join(prompt_lines)


def build_controlled_rag_prompt(context_payload: ContextPayload) -> str:
    """
    Xây dựng Prompt B cho Run B (Controlled RAG với ngữ cảnh tối đa 5 EvidenceItem).
    Yêu cầu trả về đúng định dạng JSON khớp StructuredRAGOutput.
    Ném ValueError nếu context_payload.evidence_items rỗng.
    """
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
