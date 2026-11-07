# Tuần 9 — Yêu cầu và tiêu chí nghiệm thu Dev 1

Nguồn: Kế hoạch Tuần 9 V3 do người dùng cung cấp, thời gian 03–09/11/2026; ưu tiên quyết định tại phụ lục G khi có câu chữ mâu thuẫn. Đây là phân tích yêu cầu và đề xuất giao tiếp, chưa phải biên bản M0 hay contract đã được nhóm duyệt.

Baseline phân tích: origin/testing tại f89ef83. Nhánh công việc: feature/week09-dev1-planning. Không dùng nhánh PR #25 làm nền Tuần 9 vì corpus của PR này đang chờ quyết định. Trạng thái PR và hash cần xác nhận lại tại M0; không coi snapshot trong kế hoạch là trạng thái hiện hành.

## 1. Phạm vi và ownership

Dev 1 sở hữu dữ liệu/metadata, deterministic citation validator, leakage guard và tập câu âm. Dev 3 sở hữu schemas/models.py (Pydantic canonical) và JSON Schema được generate; Dev 1 cung cấp yêu cầu, không tạo contracts/ hoặc schema song song. Dev 5 sở hữu evidence mapper và Grounding Gate trong orchestration/rag_pipeline.py. Validator không kết luận Legal Correctness hay Context Faithfulness.

## 2. Checklist công việc và nghiệm thu

| Task | Artifact canonical | Điều kiện nghiệm thu | Phụ thuộc / reviewer |
| --- | --- | --- | --- |
| D1.0 P0 — baseline và impact PR #25 | reports/baseline/m0_repo_snapshot.md; reports/data/corpus_change_impact.md | Ghi remote SHA sau handoff; working tree; quyết định PR #25–#28; corpus hash/version và số chunks; Test questions/Gold hash; retrieval/rerank config và hash. Phân biệt dữ kiện đã kiểm tra và quyết định đang chờ. Mô tả thay đổi corpus, tác động index/Gold/freeze nếu nhận PR #25. Không tự quyết merge. | Dev 5 push handoff; Tech Lead + Dev 4 review |
| D1.1 P0 — audit và aliases | data/reference/document_versions.json; data/reference/document_aliases.json; reports/data/metadata_audit_20261103.md | Kiểm tra ID duy nhất, number/year/title, liên kết corpus, effective_from/effective_to. Alias tên/số hiệu/năm truy về document_id canonical; alias mơ hồ không được âm thầm chọn một văn bản. Có sample, lệnh chạy và test. Chỉ sửa registry khi có bằng chứng. | Corpus M0; Dev 2 + Dev 3 review |
| D1.2 P0 — citation validator | grounding/citation_validator.py; test/grounding/test_citation_validator.py | Nhận ContextPayload và mapped citations; evidence index hợp lệ, mapping đúng selected evidence, chunk thuộc context đã cấp LLM, document/article/clause IDs khớp nguồn. Ngoài context hoặc sai mapping không PASS. Có reason xác định cho FAIL. | Schema Dev 3 + mapper Dev 5; Dev 3 + Dev 5 review |
| D1.4 P0 — leakage guard | test/evaluation/test_dev30_no_test_leakage.py | Manifest đủ đúng 30 ID duy nhất; mỗi ID thuộc Dev source_checked; không giao Test IDs hay gold_clause_ids; thiếu artifact không được báo đạt giả. | Dev 2 tạo IDs/manifest; Dev 2 + Tech Lead review |
| D1.5 P0 — tập câu âm | evaluation/negative_set/dev_negative_queries_v1.jsonl; evaluation/negative_set/README.md | 20–30 câu mới cho Dev, đủ bốn nhóm: non-legal; pháp lý ngoài HNGĐ; văn bản/điều khoản không có corpus; thiếu dữ kiện. Mỗi câu có ID, label, reason, expected route/abstention. Kiểm tra không sao chép Test. Bàn giao Dev 4/5 trước 04/11 theo phụ lục D.6; ngày 04/11 là hạn ghi tại D1.5/G.2, cần chốt giờ cụ thể. | Dev 2 + Tech Lead review |
| D1.3 P1 — mask/logger | monitoring/pii_masker.py; monitoring/structured_logger.py; test/monitoring/test_pii_masker.py | Chỉ triển khai khi Run C/API được kích hoạt; mask trước gửi external model và trước log; không log secrets/headers. | Dev 3 + Tech Lead; Dev 2 review |

P0 ước lượng theo các task: 17–18 giờ (3 + 4 + 5 + 2 + 3–4), chưa gồm P1 2–3 giờ. Kế hoạch ghi tổng 14–18 giờ; cần xác nhận năng lực tại Kickoff.

## 3. Yêu cầu giao tiếp gửi Dev 3 và Dev 5

Đây là yêu cầu ngữ nghĩa để thống nhất schema, không phải tên field đã được duyệt.

- ContextPayload cần định danh query, ngày áp dụng, danh sách selected evidence theo thứ tự đã cấp cho LLM và source mapping. Mỗi evidence cần evidence_index, chunk_id, document_id, article_id, clause_id cùng nội dung/nguồn để truy nguyên. Phải phân biệt candidate Top-50 với selected context Top-5 và phần parent context được mở rộng.
- LLM chỉ trả evidence_index trong structured output. Dev 5 ánh xạ index về nguồn bằng code; không tin chunk_id do model tự sinh. Index bắt đầu từ 1, giới hạn theo evidence thực tế (tối đa 5), không mặc định luôn có đủ 5 evidence.
- Validator đối chiếu mapped citations với context thực tế đã cấp LLM và metadata nguồn đáng tin cậy. Không chỉ kiểm tra chunk_id có mặt rồi bỏ qua sai document/article/clause. Không chấp nhận index ngoài khoảng, sai kiểu, mapping thiếu/mơ hồ hoặc mapping sang candidate không được chọn.
- Kết quả validator cần trạng thái PASS/FAIL và danh sách reason có thể kiểm thử. Đề xuất phân loại: index không hợp lệ, mapping thiếu, chunk ngoài context, metadata không khớp. Dev 3 chốt GroundingResult canonical; Dev 5 quyết định abstain/clarify và chỉ phát answer sau Gate.
- Thiếu citation, answer không có claim pháp lý, context rỗng và parent mở rộng cần chính sách riêng được Dev 3/5 thống nhất trước implementation; không cho PASS mặc định chỉ vì danh sách citation rỗng.
- Dùng effective_from/effective_to trong giao tiếp. Registry hiện có effective_date/expiry_date: cần mapping có tài liệu và kiểm tra, không đổi tên hàng loạt trước khi kiểm tra consumer. Không suy diễn hiệu lực cấp Khoản chỉ từ trạng thái cấp văn bản.
- Alias map cần hỗ trợ tên đầy đủ, tên viết tắt, số hiệu/năm và khả năng nhiều văn bản cùng alias; Dev 1/2 thống nhất cấu trúc và normalization trước khi parser tiêu thụ. Không coi alias match là xác nhận citation hợp lệ.

## 4. Ma trận test tối thiểu

| Nhóm | Ca đạt | Ca phải bị chặn/ghi lỗi |
| --- | --- | --- |
| Evidence mapping | Index trỏ đúng selected chunk và metadata | Index 0, vượt số evidence, sai kiểu; mapping nhầm chunk; chunk chỉ có trong candidate |
| Metadata | document/article/clause khớp nguồn | Chunk đúng nhưng document/article/clause sai; thiếu định danh bắt buộc |
| Context | Evidence đúng payload của query | Citation ngoài payload; mapping lẫn query; parent context chưa có quy tắc ánh xạ |
| Leakage | 30 Dev source_checked, không giao Test | ID lặp, thiếu ID, draft, ID Test hoặc clause giao Test |
| Aliases | Số hiệu/tên chuẩn truy đúng canonical ID | Alias mơ hồ, không tồn tại; xung đột normalization |
| Negative set | 20–30 ID duy nhất, labels/reasons/expected behavior đầy đủ | Trùng Test, thiếu nhóm/nhãn, kỳ vọng router và abstention mâu thuẫn |

Citation Validity là kiểm tra thuộc context; Citation Precision/Recall đối chiếu Gold thuộc evaluator Dev 2. Validator PASS không chứng minh mọi claim được context hỗ trợ hoặc luật còn đúng tại as_of_date.

## 5. Việc làm ngay và điểm cần chờ

Làm ngay: soạn audit read-only và impact PR #25; thống kê metadata/alias candidates; tạo tập câu âm (ưu tiên hạn 04/11); thống nhất validator interface và test cases với Dev 3/5. Có thể viết leakage guard theo interface manifest đã thống nhất, nhưng chỉ nghiệm thu khi manifest thật được cung cấp.

Chờ đúng đầu vào liên quan: chốt hash M0 sau handoff/PR decisions; chốt alias/corpus audit sau baseline corpus; tích hợp validator sau schemas/models.py và evidence mapper; chạy leakage test với manifest Dev 2. Không cần chờ mọi nhánh hết lỗi để làm các phần độc lập.

Không chạy official A/B ở bước này. M0 cần 30-ID manifest và rubric guide đã commit, không cần score sheet. Chỉ chạy official sau M0/M1 và Code/Prompt/Config Freeze; benchmark as_of_date lấy theo query ID từ queries_dev.json. Không chỉnh Test hay re-freeze để hoàn thành checklist Dev 1.

## 6. Các quyết định còn mở tại Kickoff

- Tech Lead quyết định PR #25/#27/#29/#32 và baseline corpus; #26 đã squash-merge, #28 đóng chưa merge và metrics hiện ở #32 (xác minh 06/11). Xác nhận remote SHAs và handoff G3; không yêu cầu tạo lại nhánh fix/rerank-runs đã xóa sau merge.
- Dev 2 chốt 30 ID/manifest/rubric guide. Tập calibration phải tính bằng phép loại ID thật, không mặc định luôn là 75−30.
- Dev 3/5 chốt ContextPayload, GroundingResult, selected evidence/parent mapping và chính sách citation rỗng; Dev 1 review.
- Dev 1/2 chốt alias-map format và xử lý alias mơ hồ.
- Chốt hạn/giờ bàn giao negative set và reviewer; xác nhận tổng effort P0.
- Mục 2.1 có câu yêu cầu rubric CSV tại M0 nhưng G.2 và M0 EXIT quy định chưa có điểm. Áp dụng G.2: chỉ manifest/ID list và rubric guide; score CSV sau blind A/B.

## 7. Handoff và trạng thái

Mỗi handoff phải có artifact/PR, contract version, sample payload, lệnh chạy và test evidence. Cập nhật 06/11/2026: D1.0 đã có reports/baseline/m0_repo_snapshot.md và reports/data/corpus_change_impact.md, kèm m0_audit_evidence.json, m0_validation_results.md và script audit tái chạy. Đã xác minh PR/CI bằng GitHub API; #26 squash-merge tại f89ef83, #28 đóng và metrics hiện theo #32. Validator/freeze PASS ở testing và các PR #25/#27/#32; full pytest lần lượt 642/644/642/658 passed, mỗi bản 1 skipped. Xem m0_validation_results.md cho khoảng thiếu Tuần 9 và raw logs checks_*.json. D1.0 chờ reviewer Tech Lead + Dev 4; M0 vẫn chờ quyết định PR/handoff/Dev30/M1. Cập nhật 07/11/2026: D1.5 đã được tích hợp cùng nhánh feature/week09-dev1-planning, có 24 câu âm, manifest, README, validator và tests trong evaluation/negative_set/, scripts/validate_negative_set.py và test/test_negative_set.py; nhãn đang pending_peer_review bởi Dev 2 + Tech Lead. D1.1 đã có audit 24 văn bản/2164 chunks, document_aliases.json, resolver/loader và tests; bàn giao pending_peer_review bởi Dev 2 + Dev 3, xem docs/document_aliases.md và reports/data/metadata_audit_20261103.md (audit thực hiện 07/11). D1.2, D1.3 và D1.4 chưa triển khai trong nhánh này. Chưa có thay đổi benchmark/corpus/schema runtime.