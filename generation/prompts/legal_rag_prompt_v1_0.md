# Legal RAG Prompt Specification (Sprint 9 - M1 Freeze, v1.1 sau Run B 10/11)

- **Prompt A Version**: `v1.1_zero_shot` (trước đó `v1.0_zero_shot_m1`)
- **Prompt B Version**: `v1.1_controlled_rag` (trước đó `v1.0_controlled_rag_m1`)
- **Model**: `qwen2.5:7b`
- **Standard Disclaimer**: `Thông tin chỉ mang tính tham khảo, không thay thế tư vấn pháp lý chuyên nghiệp.`

---

## 1. Zero-Shot Prompt (Prompt A)
Dành cho Run A để đo lường năng lực pháp lý gốc (zero-shot capability) của mô hình `qwen2.5:7b` trong lĩnh vực Hôn nhân và Gia đình Việt Nam, không được cấp ngữ cảnh RAG.

### Đặc tả:
- Giới hạn phạm vi: Pháp luật Hôn nhân & Gia đình Việt Nam.
- Quản lý mốc thời gian: Nhận tham số bắt buộc `as_of_date` từ benchmark (ví dụ `2024-01-01`).
- Hướng dẫn hiệu lực: Yêu cầu mô hình nêu rõ `"Theo quy định có hiệu lực tại ngày {as_of_date}..."`.
- Không đòi hỏi mô hình trích dẫn chunk ID.
- Đánh số quy tắc 1, 2, 3, 4, 5 liên tục, kết thúc luôn có disclaimer chuẩn.
- Quy tắc 5 (từ v1.1), nguyên văn: `NGÔN NGỮ VÀ NGUỒN LUẬT: Câu trả lời phải viết hoàn toàn bằng tiếng Việt, không dùng chữ Hán hay ngôn ngữ khác. Chỉ căn cứ pháp luật Việt Nam; tuyệt đối không viện dẫn pháp luật nước ngoài (ví dụ luật Trung Quốc).`

---

## 2. Controlled RAG Prompt (Prompt B)
Dành cho Run B với ngữ cảnh tối đa 5 `EvidenceItem` được giải quyết từ Parent Resolver (Top 1..n, $1 \le n \le 5$).

### Đặc tả Evidence Numbering:
Mỗi bằng chứng được định dạng rõ ràng:
`[{item.evidence_index}] {item.document_title or item.document_id} ({item.document_number or ''}) | {item.breadcrumb or item.article_id} | Hiệu lực: {item.validity_status} ({item.effective_from or ''} -> {item.effective_to or ''})\nNội dung: {item.content}`

Dải số bằng chứng hiển thị chính xác theo số lượng thực tế: `[1] đến [{len(evidence_items)}]`.

### Ràng buộc nghiêm ngặt (Defensive Constraints):
1. **Scope Restriction**: Bổ sung quy tắc phạm vi chỉ tư vấn trong phạm vi pháp luật Hôn nhân và Gia đình Việt Nam.
2. **Evidence-Bounded**: Chỉ sử dụng thông tin trong các đoạn `[1]`...`[{n}]`. Tuyệt đối không tự suy diễn ngoài ngữ cảnh.
3. **Numeric Citation Only**: Chỉ trả về chỉ số bằng chứng `[1, 2, ...]` trong trường `evidence_indices`. Tuyệt đối không chép chuỗi mã `chunk_id` dài vào output.
4. **Abstention**: Khi bằng chứng không đủ hoặc mâu thuẫn thời điểm hiệu lực, đặt `"abstained": true`, nêu rõ `"abstention_reason"`.
5. **Clarification**: Đặt `"needs_clarification": true` nếu câu hỏi thiếu dữ kiện pháp lý thiết yếu.
6. **Structured Output**: Bắt buộc tuân thủ JSON Schema của `StructuredRAGOutput`.
7. **Empty Safety**: Ném `ValueError("Empty retrieval: không có bằng chứng để tạo prompt.")` nếu `evidence_items` rỗng.
8. **Ngôn ngữ và nguồn luật** (từ v1.1): quy tắc số 6 của mục RÀNG BUỘC NGHIÊM NGẶT, ngay trước `YÊU CẦU ĐẦU RA:`, nguyên văn: `NGÔN NGỮ VÀ NGUỒN LUẬT: Trường "answer" phải viết hoàn toàn bằng tiếng Việt, không dùng chữ Hán hay ngôn ngữ khác. Chỉ căn cứ pháp luật Việt Nam có trong bằng chứng; tuyệt đối không viện dẫn pháp luật nước ngoài (ví dụ luật Trung Quốc).` Không thêm system message: khi thử, system message tiếng Việt không giúp thêm (HN_062 vẫn lỗi).

---

## 3. Change log

| Ngày | Phiên bản | Thay đổi | Lý do |
| --- | --- | --- | --- |
| 2026-11-13 | `v1.1_zero_shot`, `v1.1_controlled_rag` | Thêm quy tắc ngôn ngữ và nguồn luật (Prompt A quy tắc 5, Prompt B quy tắc 6); `repeat_penalty` 1.15 → 1.0 trong `model_gateway/config/local_qwen.yaml` | Run B 10/11: HN_025 trả lời gần như toàn bộ bằng tiếng Trung, dẫn Luật Hôn nhân CHND Trung Hoa; HN_062 chuyển sang tiếng Trung ở ý 5. Thử lại 2 câu: chỉ thêm quy tắc vẫn lỗi, quy tắc + `repeat_penalty` 1.0 thì cả hai PASS sạch. Thay đổi sau Freeze, cần Tech Lead duyệt (P45-10). |
| M1 | `v1.0_zero_shot_m1`, `v1.0_controlled_rag_m1` | Bản khóa đầu tiên | — |
