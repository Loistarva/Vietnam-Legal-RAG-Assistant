# D1.5 v2 - coverage review sau PR #35-#40

Ngày rà: 08/11/2026. Baseline là `testing` fc66642 (full SHA trong manifest).
Registry 28 văn bản, corpus 2.322 chunk. V1 giữ nguyên như hồ sơ lịch sử; v2 là
bản bàn giao hiện tại. Validator mặc định dùng v2, không đổi dữ liệu Test.

## Coverage, không chỉ hash

- Đọc lại registry và document_number của mọi chunk: ba nguồn sơ cấp
  52/2010/QH12, 60/2014/QH13, 326/2016/UBTVQH14 vẫn chưa có trong corpus.
- Bốn văn bản mới (NĐ87/2020, NĐ07/2025, NĐ18/2026, TT04/2024) có nội dung
  liên quan hộ tịch nhưng không thay thế yêu cầu dẫn chính nguồn sơ cấp ở các
  case missing_corpus_evidence. Nhãn này không có nghĩa toàn bộ chủ đề thiếu căn cứ.
- Việc tách Khoản trích dẫn của NĐ07/2025 và ngày hỏi lịch sử của 26 draft không
  thêm ba nguồn trên. Validator kiểm cả snapshot pinned và checkout hiện tại,
  cùng đối chiếu trùng ID/câu hỏi với Dev/Test hiện tại và các snapshot cũ.
- Viết lại 3 case thiếu nguồn theo tình huống tự nhiên nhưng vẫn chỉ rõ nguồn
  cần đối chiếu; giữ 3 case yêu cầu nguồn trực tiếp làm control.
- Viết lại 6 case thiếu dữ kiện theo cách hỏi tự nhiên, không tự nêu toàn bộ
  phần thiếu. Clarification fields vẫn ghi riêng cho evaluator/router.
- Thêm hai case ranh giới (thừa kế và hình phạt bạo lực gia đình). Nhãn đề xuất
  legal_out_of_scope chỉ áp dụng câu cụ thể, chưa phải quyết định phạm vi cho
  toàn bộ chủ đề. Tech Lead cần chốt NEG_DEV_025/026; trạng thái pending_peer_review.

## Bàn giao

26 câu: 6 non_legal, 8 legal_out_of_scope, 6 missing_corpus_evidence,
6 insufficient_facts. Manifest pin baseline, hashes và nguồn kiểm trùng mới.
Dev 4 nhận JSONL cho router; Dev 5 nhận để calibration; Dev 2 + Tech Lead duyệt.
Chưa có số đo threshold, chưa khẳng định router đạt yêu cầu và không dùng làm Test.

```powershell
python scripts/validate_negative_set.py --fetch-sources
python -m pytest test/test_negative_set.py -q
```

Kết quả: validator 0 issues; 61 test PASS. Corpus, benchmark, config và Test
freeze không thay đổi trong phần D1.5.
