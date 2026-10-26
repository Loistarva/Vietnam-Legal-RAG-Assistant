# Rà soát dữ liệu Test theo `gold_id_proposals_300.json`

## Phạm vi

Rà soát 15 câu trong `data/benchmark/queries_test.json` và proposal tương ứng trong `data/benchmark/gold_id_proposals_300.json`. File proposal là nguồn nhãn duy nhất cho báo cáo này. Không dùng nhãn từ nguồn khác để xác nhận hoặc bác bỏ proposal.

Corpus chunk hiện tại là `data/chunking_output/chunks.jsonl` với 2.011 chunk. Vì kết quả retrieval được chấm ở cấp chunk, cần phân biệt `gold_context_ids` là ID chunk có trong corpus hay ID tài liệu/phiên bản ở cấp khác.

## Phát hiện

1. **Đủ hàng theo query:** proposal có 15 hàng tương ứng với 15 query Test.
2. **Trạng thái review chưa đáng tin cậy:** HN_004 và HN_008 ghi `mapping_status=production_verified`, `gold_context_ids_confirmed=true`, `review_status=source_checked`, nhưng `verified_by=TEST_REVIEWER` là placeholder. 13 hàng còn lại chưa được xác nhận. Cần thay bằng người review thực và ghi nhận quy trình xác minh trước khi coi trạng thái này là hoàn tất.
3. **ID gold và candidate bị giao nhau:** HN_012, HN_016, HN_020, HN_024, HN_028, HN_032 và HN_036 có ID xuất hiện đồng thời trong `gold_context_ids` và `candidate_context_ids`. Cần rà soát lại phân loại để tránh cùng một ID vừa được tính là nhãn đúng vừa là ứng viên chưa xác nhận.
4. **Trộn cấp ID:** HN_040, HN_044, HN_048, HN_052, HN_056 và HN_060 chỉ có `version_*` trong `gold_context_ids`. Những mã này thuộc metadata phiên bản văn bản, không phải ID chunk trong `chunks.jsonl`; chúng không thể được so khớp trực tiếp với kết quả retrieval cấp chunk. HN_036 trộn một chunk ID với một version ID. Tổng cộng 9 hàng có ít nhất một chunk ID hiện diện trong corpus.
5. **Trường hợp HN_036 thiếu evidence trực tiếp:** proposal nêu điều 131 và điều 132 là điều luật liên quan nhưng `gold_context_ids` không có chunk điều 132. ID chunk điều 132 có trong corpus là `l_52_2014_qh13_art_132_clause_1_chunk_1`. Gold hiện có một chunk điều 131(3) về giám đốc thẩm/tái thẩm và một version ID, nên cần bổ sung/đổi evidence nếu muốn nhãn phản ánh trực tiếp nội dung câu hỏi về áp dụng luật cho quan hệ phát sinh mới.
6. **Proposal về hiệu lực văn bản ở cấp version:** các hàng HN_040, HN_052, HN_056 và HN_060 có thể phù hợp với đánh giá truy xuất metadata cấp văn bản, nhưng không dùng được cho metric đối chiếu chunk nếu evaluator không ánh xạ version ID sang chunk/evidence cụ thể. HN_060 cũng chỉ gắn nhãn cấp văn bản; nếu cần đánh giá theo điều khoản thì proposal cần chỉ rõ điều khoản bị sửa đổi/bãi bỏ.
7. **HN_044 có thể cần evidence cho cả hai văn bản:** proposal gắn nhãn version ID cho Nghị định 207/2025/NĐ-CP và Thông tư 38/2025/TT-BYT. Khi chấm ở cấp chunk, cần chỉ rõ chunk hỗ trợ từng văn bản thay vì để version ID không ánh xạ.
8. **HN_048 chỉ gắn nhãn văn bản hết hiệu lực:** proposal có version ID của Thông tư 07/2002/TT-BTC. Nếu câu hỏi cần hướng dẫn hiện hành thay thế, proposal hiện chưa chọn evidence hiện hành cho phần đó.

## Ảnh hưởng đến metric

Các metric trong `retrieval/results/test_run/test_report.md` là so khớp trực tiếp với proposal hiện có, không khẳng định proposal đã được xác minh. Metric trên đủ 15 câu tính cả version ID trong mẫu số, dù retrieval trả về chunk ID. Metric trên 9 câu chỉ gồm các query có ít nhất một chunk ID trong corpus; HN_036 vẫn có nhãn chunk cần rà soát nội dung. Vì vậy nên xem cả hai bảng là kết quả thăm dò, và không dùng chúng như một điểm đánh giá chunk-level đã được xác nhận.

## Việc cần sửa trong proposal

- Thay `TEST_REVIEWER` bằng danh tính người rà soát thực và xác minh lại hai hàng HN_004, HN_008.
- Loại trùng/ghi rõ ý nghĩa của ID giao nhau giữa gold và candidate ở bảy hàng.
- Chọn một đơn vị đánh giá nhất quán: chunk ID cho retrieval chunk-level; hoặc version/document ID cho benchmark metadata-level. Nếu cần cả hai, lưu thành hai nhãn riêng và metric riêng.
- Bổ sung ID chunk evidence cho các proposal version-level nếu muốn dùng để chấm retrieval chunk-level.
- Rà soát HN_036, nhất là chunk điều 132; xác định lại vai trò của chunk điều 131(3) và version ID.
- Với câu hỏi yêu cầu văn bản hiện hành hoặc tình trạng hiệu lực theo điều khoản, bổ sung evidence hiện hành/điều khoản cụ thể khi đó là nội dung cần được truy xuất.

## Giới hạn

Đây là rà soát tính nhất quán và khả năng dùng của proposal, không phải xác nhận tính đúng pháp lý của toàn bộ câu trả lời. Kết quả retrieval mock reranker cũng không đại diện cho Cross-Encoder production.
