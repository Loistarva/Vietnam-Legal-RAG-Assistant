# PR #33 - phản hồi review 08/11

Baseline tích hợp: testing `fc66642` (PR #40 đã merge trước khi thực hiện).
Không tạo nhánh mới. D1.5 dùng nhánh negative-set đang có và tách PR #41.

## Checklist

- Base PR #33 đã đổi main -> testing; tích hợp bằng merge để giữ lịch sử đã push,
  không force-push/rewrite commit của nhánh. Chạy lại kiểm tra trên cây mã tích hợp.
- D1.1: aliases sinh từ 28 văn bản; audit đọc provision_periods, chỉ cho khoảng
  chunk khác cấp văn bản khi nằm bên trong và khớp override. Tests có case hợp lệ,
  thiếu override, ngày không khớp và ngày bắt đầu ngoài khoảng văn bản.
- Alias thiếu năm “Nghị định 126” trả insufficient_context và candidates, không
  tự chọn ứng viên; explicit year có thể giải mơ hồ theo dữ liệu registry.
- D1.4: hash toàn file Dev/Gold/corpus khác chỉ cảnh báo; 30 query vẫn khóa,
  selected_gold_content_hash và Test freeze vẫn chặn khi sai. Bổ sung fingerprint
  45 chunk gold theo nội dung/identity/dates từ e0cea35, đối chiếu không đổi tới
  testing hiện tại. Không thay selection/manifest/confirmation của Dev 2/5.
- D1.5 đã loại khỏi diff chính PR #33; xem PR #41, v2 gồm 26 câu. Coverage mới,
  trường hợp tự nhiên và hai case ranh giới chờ Dev 2 + Tech Lead chốt.
- D1.0: thêm mục Cập nhật 08/11 vào snapshot và impact #36, SHA/hash hiện tại,
  PR25 đóng, PR35-40 merge. Giữ hồ sơ 06/11 có nhãn lịch sử.
- D1.3: issue #42 cho Tuần 10, không triển khai masker/API trong PR này.
- D1.2: ghi rõ chưa kiểm độc lập citation cấp Điểm.
- Dọn ba script/test Node .cjs khỏi PR; rút gọn JSON GitHub/checks lịch sử,
  bỏ đường dẫn máy local khỏi checks, không trình bày chúng thành kết quả mới.

## Validation

- Full pytest: **1021 passed, 1 skipped**.
- Ruff check .: 0 lỗi; git diff --check: 0 lỗi.
- Audit: 28 documents, 2322 chunks, 851 article rows, 766 aliases;
  0 structural errors, 28 warning về giới hạn nguồn/hiệu lực cần người duyệt.
- Dev30 handoff: PASS; 30 source_checked, 45 Gold chunks, 0 Test overlap;
  3 whole-file drift warnings ngoài tập chọn được ghi rõ, không tắt kiểm tập con.
- Benchmark validator và Test question/Gold freezes: PASS.
- Không sửa benchmark/corpus/registry hoặc config retrieval để làm các guard pass.

## Review tiếp theo

D1.0: Tech Lead + Dev 4. D1.1: Dev 2 + Dev 3. D1.2: Dev 3 + Dev 5.
D1.4: Dev 2 + Tech Lead. D1.5 ở PR41: Dev 2 + Tech Lead, Dev 4/5 nhận bàn giao.
Không tự chốt nhãn biên, hiệu lực pháp lý hoặc official A/B chỉ từ test PASS.
