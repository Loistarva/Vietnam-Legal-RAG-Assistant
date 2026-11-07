# D1.0 — Tác động PR #25 sau các commit đã sửa

So sánh trực tiếp testing f89ef8372a06102802349bb9ea0cf04fcc0a4646 với PR #25 54c0e37f5f913f179628d152297b126c1fda2189. PR đang mở; Trạng thái CI head ghi tại m0_repo_snapshot.md theo GitHub snapshot 2026-11-06T11:56:05.4605034Z. Không gộp “đã sửa” với “đã merge”.

## 1. Những gì đã được xử lý

07d365d thay sáu mapping placeholder bằng nguồn/chunk production; 08bcb52 sửa validation/tests cho mapping hoàn chỉnh; 54c0e37 sửa câu Dev draft để tránh giao Khoản Test. Full pytest trên đúng PR head: 644 passed, 1 skipped in 30.03s; validator và hai freeze checks PASS.

195 câu vẫn draft/other; gold_context_ids_confirmed=true được docs/benchmark_label_provenance.md giải thích là xác nhận mapping tồn tại/khớp corpus. Không gọi đây là lỗi nâng 195 câu thành Gold pháp lý. Metric official tiếp tục chỉ dùng source_checked.

## 2. Delta định lượng

| Chỉ tiêu | Baseline | PR #25 |
| --- | --- | --- |
| Corpus chunks | 2164 | 2173 |
| Gold source_checked | 105 | 105 |
| Draft/other | 195 | 195 |
| Draft confirmed mapping | 0 | 195 |
| Gold context không tồn tại | 0 | 0 |
| Reviewed Dev giao clause với Test (số câu) | 0 | 0 |
| Mọi record dùng ID Điều 19–50 NĐ126 | 0 | 26 |
| Source_checked trong nhóm đó | 0 | 0 |

26 record trong nhóm NĐ126 là draft; đây là danh sách cần source review khi chuyển Gold, không phải 26 câu đã duyệt mới bị phát hiện sai. Audit ID không kết luận hiệu lực pháp luật; không sửa luật/dữ liệu theo suy đoán.

Corpus thêm 9, xóa 0, sửa chunk cũ 0. 195 record ground_truth thay đổi; xóa record 0; source_checked thay đổi 0; Test thay đổi 0.

Corpus hash baseline: 710350f1d0f9b66cb419d89fe7eabd655eba3330c8416534d475e43ce5048d9d; PR: d7b1154d83ece7b8cf0aa38e53d8f609a296dc99c1ec9e6e201fa2d587dd468e. Test questions/Gold của PR vẫn khớp manifest và bằng baseline.

Các trường Gold thay đổi:

- answer: 20
- explanation: 20
- gold_context_ids: 195
- citations: 38
- temporal_note: 20
- gold_article_ids: 30
- evidence_level: 195
- candidate_context_ids: 176
- mapping_status: 195
- context_id_provenance: 19
- gold_context_ids_confirmed: 195
- answer_kind: 19
- gold_clause_ids: 195

Chín chunk mới:

- nd_24_2013_nd_cp_art_45_clause_1_chunk_1
- nd_24_2013_nd_cp_art_45_clause_2_chunk_1
- tt_01_2018_tt_btp_art_1_clause_2_chunk_1
- tt_01_2018_tt_btp_art_3_clause_1_chunk_1
- tt_04_2024_tt_btp_art_2_clause_3_chunk_1
- tt_04_2024_tt_btp_art_4_clause_1_chunk_1
- nd_07_2025_nd_cp_art_2_clause_1_chunk_1
- nd_07_2025_nd_cp_art_2_clause_1_chunk_2
- nd_07_2025_nd_cp_art_5_clause_1_chunk_1

## 3. Việc tích hợp cần làm nếu nhận PR

1. Owner review nguồn/provenance 9 chunk và quyết định accept/defer; report D1.0 không tự quyết.
2. Rebuild hoặc migration có kiểm soát ES/Qdrant cho corpus 2173; ghi hash/index/version mới. Không dùng artifact corpus 2164 như thể là bản 2173.
3. Kiểm tra kết quả tích hợp với #27 và #32: giữ các sửa đáp án/reviewer/freeze mới, bảo đảm evaluator chỉ chấm nhãn được duyệt. Không kết luận có conflict chỉ vì cùng file; cần thử tích hợp trước.
4. Chạy validator, leakage, freeze và tests sau tích hợp. Chỉ re-freeze khi payload Test thực sự đổi và được phép; thay corpus một mình không bắt buộc đổi hash Test.

## 4. Phần còn là giới hạn tài liệu

docs/benchmark_label_provenance.md giải thích phần 294/300 và 6 placeholder là lịch sử, nhưng vẫn có số liệu cũ/mệnh đề cũ về confirmed ở phần sau. Đây là điểm làm rõ tài liệu khi bàn giao, không phủ nhận các commit mapping đã sửa. Bằng chứng machine-readable: ../baseline/m0_audit_evidence.json.
