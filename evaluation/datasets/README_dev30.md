# File 30 câu Dev để bàn giao zero-shot

**File gửi người chạy:** `evaluation/datasets/dev_gold_30_queries_v1.json`.

Đây là JSON array 30 query giữ nguyên trường/nội dung từ `queries_dev.json`; không có đáp án, explanation, citation hay Gold trong model input. Khóa `id`, `question`, `split=dev`, `as_of_date` tương thích loader zero-shot của nhánh metrics mới. Không sửa lại câu hỏi cho dễ hoặc chọn theo kết quả model.

**File bạn kiểm tra trước:** `evaluation/review/dev_gold_30_selection_review_v1.md` — có đủ câu hỏi, đáp án tham chiếu và chunk chứng cứ của từng câu. Chỉ file query JSON được dùng cho inference; không đưa review Markdown vào prompt.

## Các ID đã chọn

HN_001, HN_002, HN_004, HN_007, HN_009, HN_010, HN_013, HN_016, HN_017, HN_018,
HN_020, HN_021, HN_023, HN_025, HN_028, HN_029, HN_030, HN_031, HN_032, HN_033,
HN_035, HN_061, HN_062, HN_067, HN_087, HN_104, HN_155, HN_297, HN_299, HN_300.

## Tiêu chí và giới hạn lựa chọn

- Loại đúng 195 ID trong danh sách người dùng, lưu nguyên các khoảng ID trong `evaluation/manifests/dev_gold_30_selection_policy_v1.json`.
- Chỉ lấy Dev đã `source_checked`, `full_text_checked`, `reviewed_answer`, production mapping confirmed; ID, câu hỏi chuẩn hóa và Gold clause không giao Test ở cả baseline lẫn nhánh D1 mới.
- Loại HN_078 có lỗi gõ; không chọn câu có query hoặc nội dung Gold đang được chỉnh so với baseline. Điều này không tuyên bố mọi câu bị sửa là sai hoặc mọi draft đều có đáp án sai.
- Baseline mới nhất lúc chuẩn bị: `0f8a6a7b019a593a1f4d29cea850ec7fbd6465cc` (đã có PR #29). So nội dung với D1 `c36fe416ac0e665789a131f1f5228fc6c01207a4`; loại chunk/document mới của PR #25 `54c0e37f5f913f179628d152297b126c1fda2189`.
- “Không dùng dữ liệu bổ sung” ở đây nghĩa là không dùng 9 chunk/4 document mới của PR #25. Cả 30 câu chỉ dùng Gold từ Luật 52/2014 đã có sẵn trong corpus cũ, không trộn draft mapping mới vào Gold.
- Phân bố: 8 chủ đề; 13 fact, 14 situation, 3 multi-hop; 13 easy, 12 medium, 5 hard. Có 29 current_law và 1 outdated_law_trap. Không lấy historical_law hoặc partially_expired trong đề xuất bảo thủ này.
- Đây là mẫu tiện dụng theo yêu cầu chất lượng/nguồn, không đại diện đầy đủ 75 Dev Gold hay tất cả văn bản. Một số câu khác nhau dùng chung Khoản; không tuyên bố 30 câu là 30 bằng chứng độc lập.
- Đã rà nội dung hỏi/đáp với local chunks và kiểm hiệu lực theo metadata tại `as_of_date`; không tự gán thêm tên/ngày người duyệt. Đọc luật độc lập, hiệu lực cấp quy định, và review ngữ nghĩa cuối vẫn cần người duyệt. Định dạng URL citation được kiểm nhưng không kiểm HTTP/redirect mọi URL cũ.

Trang nguồn chính thức để người duyệt đối chiếu thêm: [Luật 52/2014/QH13](https://vanban.chinhphu.vn/default.aspx?docid=175351&pageid=27160). Link này phục vụ review, không thay citation/Gold trong benchmark gốc.

## Manifest và lệnh kiểm tra

- `evaluation/manifests/dev_gold_30_manifest.json`: **proposed_pending_user_and_dev2_review**, chứa ID/hash, input SHAs, phân bố và danh sách dữ liệu bị loại; chưa là quyết định khóa official của nhóm.
- `evaluation/rubrics/dev_gold_30_ids_v1.txt`: cùng 30 ID, cùng thứ tự. Đây là ID list, không phải rubric guide hoặc score sheet.
- `remaining_reviewed_dev_ids` trong manifest chỉ là phép trừ 30 ID khỏi 75 Dev source_checked. Không mặc định cả 45 câu còn lại đều đạt màn lọc nguồn/ổn định; Dev 2/5 phải rà các câu đang sửa trước calibration.

```powershell
python scripts/prepare_dev30.py
python -m pytest test/test_dev30_selection.py -q
```

Lệnh mặc định chỉ kiểm tra; `--write` sinh các file proposal sau khi checks đạt. Nếu nội dung manifest v1 khác phiên bản đã sinh, script dừng yêu cầu review/v2 thay vì ghi đè. Không chỉnh canonical benchmark, corpus hoặc freeze manifest.

Loader compatibility với code `evaluation/zero_shot.py` tại metrics SHA `aadb20420cecada28a5a03e0c31a11b88bd7cc84` đã kiểm: đọc đủ 30 ID, không gọi Ollama/model; log tại `evaluation/review/dev30_loader_compatibility_v1.json`. Bàn giao file JSON cho đối số `--queries` của runner phù hợp; không tự chạy official A/B ở bước chuẩn bị. Dev 2 phải xác nhận ID/manifest, rubric guide, prompt/date policy, generation params và Freeze trước khi dùng cùng file cho A/B.

Không sửa danh sách câu sau khi đã xem output để cải thiện điểm. Chưa có điểm rubric, threshold hoặc kết quả inference trong đợt chuẩn bị này.
