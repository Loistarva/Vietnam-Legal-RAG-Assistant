# Legal RAG Prompt Specification (Sprint 9 - M1 Freeze, v1.1 sau Run B 10/11, Prompt B v1.2 sau Run B 13/11)

- **Prompt A Version**: `v1.1_zero_shot` (trước đó `v1.0_zero_shot_m1`)
- **Prompt B Version**: `v1.2_controlled_rag` (trước đó `v1.1_controlled_rag`, `v1.0_controlled_rag_m1`)
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
- Quy tắc 5 (từ v1.1), nguyên văn: `NGÔN NGỮ VÀ NGUỒN LUẬT: Câu trả lời phải viết hoàn toàn bằng tiếng Việt, không dùng chữ Hán hay ngôn ngữ khác. Chỉ áp dụng pháp luật nước Cộng hòa Xã hội Chủ nghĩa Việt Nam; tuyệt đối không viện dẫn pháp luật nước ngoài và không sử dụng kiến thức về pháp luật Trung Quốc (như Bộ luật Dân sự Trung Quốc, Luật Hôn nhân Trung Quốc, các cơ quan/thuật ngữ pháp lý Trung Quốc) hay bất kỳ quốc gia nào khác.`

---

## 2. Controlled RAG Prompt (Prompt B)
Dành cho Run B với ngữ cảnh tối đa 5 `EvidenceItem` được giải quyết từ Parent Resolver (Top 1..n, $1 \le n \le 5$).

### Đặc tả Evidence Numbering:
Mỗi bằng chứng được định dạng rõ ràng:
`[{item.evidence_index}] {item.document_title or item.document_id} ({item.document_number or ''}) | {item.breadcrumb or item.article_id} | Hiệu lực: {item.validity_status} ({item.effective_from or ''} -> {item.effective_to or ''})\nNội dung: {item.content}`

Dải số bằng chứng hiển thị chính xác theo số lượng thực tế: `[1] đến [{len(evidence_items)}]`.

### Ràng buộc nghiêm ngặt (Defensive Constraints):
1. **Scope Restriction**: Bổ sung quy tắc phạm vi chỉ tư vấn trong phạm vi pháp luật Hôn nhân và Gia đình Việt Nam.
2. **Strict Closed-Context (Evidence-Bounded)**: Chỉ sử dụng thông tin có thật trong các đoạn `[1]`...`[{n}]`. Mọi khẳng định pháp lý bắt buộc có căn cứ trực tiếp từ nội dung được cấp; tuyệt đối không tự suy diễn ngoài ngữ cảnh.
3. **Numeric Citation Only**: Chỉ trả về chỉ số bằng chứng `[1, 2, ...]` trong trường `evidence_indices`. Tuyệt đối không chép chuỗi mã `chunk_id` dài vào output.
4. **Abstention**: Khi bằng chứng không đề cập đến tình tiết được hỏi, không đủ căn cứ kết luận hoặc mâu thuẫn thời điểm hiệu lực, đặt `"abstained": true`, nêu rõ `"abstention_reason"`.
5. **Clarification** (v1.2, `CLARIFICATION_RULE_B`): Chỉ đặt `"needs_clarification": true` khi câu hỏi thiếu dữ kiện đến mức các đoạn bằng chứng dẫn tới những kết luận khác nhau tùy dữ kiện còn thiếu, nên không thể trả lời nếu chưa hỏi lại người dùng. Nếu bằng chứng đã trả lời được câu hỏi theo quy định chung thì trả lời, nêu kèm các ngoại lệ có trong bằng chứng, và đặt `"needs_clarification": false`. Trước v1.2: "Đặt `needs_clarification: true` nếu câu hỏi thiếu dữ kiện pháp lý thiết yếu."
6. **Structured Output**: Bắt buộc tuân thủ JSON Schema của `StructuredRAGOutput`.
7. **Empty Safety**: Ném `ValueError("Empty retrieval: không có bằng chứng để tạo prompt.")` nếu `evidence_items` rỗng.
8. **Ngôn ngữ và nguồn luật** (từ v1.1): quy tắc số 6 của mục RÀNG BUỘC NGHIÊM NGẶT, ngay trước `YÊU CẦU ĐẦU RA:`, nguyên văn: `NGÔN NGỮ VÀ NGUỒN LUẬT: Trường "answer" phải viết hoàn toàn bằng tiếng Việt, không dùng chữ Hán hay ngôn ngữ khác. Chỉ áp dụng pháp luật nước Cộng hòa Xã hội Chủ nghĩa Việt Nam được cung cấp trong các đoạn bằng chứng; tuyệt đối không viện dẫn pháp luật nước ngoài và không sử dụng kiến thức tiền huấn luyện về pháp luật Trung Quốc (như Bộ luật Dân sự Trung Quốc, Luật Hôn nhân Trung Quốc, các cơ quan/thuật ngữ pháp lý Trung Quốc) hay bất kỳ quốc gia nào khác để suy diễn, bổ sung hoặc giải thích.` Không thêm system message: khi thử, system message tiếng Việt không giúp thêm (HN_062 vẫn lỗi).

---

## 3. Change log

| Ngày | Phiên bản | Thay đổi | Lý do |
| --- | --- | --- | --- |
| 2026-11-14 | `v1.2_controlled_rag` (Prompt A giữ `v1.1_zero_shot`) | Prompt B quy tắc 4 (hỏi lại): chỉ đặt `needs_clarification` khi bằng chứng dẫn tới kết luận khác nhau tùy dữ kiện còn thiếu; nếu bằng chứng trả lời được theo quy định chung thì trả lời, nêu ngoại lệ và đặt `false`. | Run B 13/11 (v1.1): HN_016 trả lời đúng khoản 1 Điều 33 nhưng đặt `needs_clarification: true`, lặp lại ở hai máy. Quy tắc 4 cũ quá rộng, nên model đòi hỏi lại chỉ vì câu hỏi có chữ "thường" và Điều 33 có ngoại lệ (khoản 1 Điều 40). Chạy lại cả 30 câu Dev official để kiểm tra không có câu nào khác bị ảnh hưởng. Đổi sau Freeze, cần Tech Lead duyệt cùng P45-10. |
| 2026-11-13 (d7b0d1b) | `v1.1_zero_shot`, `v1.1_controlled_rag` (giữ tên) | Sửa lời văn v1.1, không đổi tên version. **Prompt B:** quy tắc 1 thành "đóng ngữ cảnh", mọi khẳng định pháp lý phải có căn cứ trực tiếp trong bằng chứng. Quy tắc 3 thêm "bằng chứng không đề cập đến tình tiết được hỏi" vào điều kiện từ chối. **Cả A và B:** quy tắc ngôn ngữ cấm thêm việc dùng kiến thức về pháp luật Trung Quốc. | Siết đóng ngữ cảnh sau review PR #45. Run B chính thức (`20261113_controlled_rag_qwen25_dev30_post_fix`) và report DoD-10 chạy trên lời văn này, nhận ra bằng `retrieval_trace.prompt_sha256`. Lỗi đã biết: HN_016 chuyển từ PASS sang `NEEDS_CLARIFICATION`, nhiều khả năng do quy tắc mới. Nếu sửa tiếp thì đổi tên version thành v1.2. |
| 2026-11-13 | `v1.1_zero_shot`, `v1.1_controlled_rag` | Thêm quy tắc ngôn ngữ và nguồn luật (Prompt A quy tắc 5, Prompt B quy tắc 6); `repeat_penalty` 1.15 → 1.0 trong `model_gateway/config/local_qwen.yaml` | Run B 10/11: HN_025 trả lời gần như toàn bộ bằng tiếng Trung, dẫn Luật Hôn nhân CHND Trung Hoa; HN_062 chuyển sang tiếng Trung ở ý 5. Thử lại 2 câu: chỉ thêm quy tắc vẫn lỗi, quy tắc + `repeat_penalty` 1.0 thì cả hai PASS sạch. Thay đổi sau Freeze, cần Tech Lead duyệt (P45-10). |
| M1 | `v1.0_zero_shot_m1`, `v1.0_controlled_rag_m1` | Bản khóa đầu tiên | — |
