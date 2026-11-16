# PR #33 - phản hồi review 08/11

Baseline tích hợp: testing `fc66642` (PR #40 đã merge trước khi thực hiện).
Không tạo nhánh mới. D1.5 dùng nhánh negative-set đang có và tách PR #41.

## Checklist

- Nhánh nền của PR #33 đã đổi từ main sang testing; tích hợp bằng merge để giữ lịch sử đã push,
  không force-push/viết lại commit của nhánh. Chạy lại kiểm tra trên cây mã đã tích hợp.
- D1.1: alias được sinh từ 28 văn bản; rà soát đọc `provision_periods`, chỉ chấp nhận khoảng
  thời gian của chunk khác cấp văn bản khi nằm bên trong và khớp giá trị ghi đè. Kiểm thử có trường hợp hợp lệ,
  thiếu giá trị ghi đè, ngày không khớp và ngày bắt đầu nằm ngoài khoảng thời gian của văn bản.
- Alias thiếu năm “Nghị định 126” trả `insufficient_context` và danh sách ứng viên, không
  tự chọn ứng viên; nếu có năm cụ thể thì có thể giải quyết mơ hồ theo dữ liệu registry.
- D1.4: hash toàn file Dev/Gold/corpus khác chỉ tạo cảnh báo; 30 query vẫn khóa,
  `selected_gold_content_hash` và Test freeze vẫn chặn nếu có sai lệch. Bổ sung fingerprint
  45 chunk Gold theo nội dung/định danh/ngày từ e0cea35, đối chiếu không đổi tới
  testing hiện tại. Không thay selection/manifest/confirmation của Dev 2/5.
- D1.5 đã được tách khỏi diff chính của PR #33; xem PR #41, v2 gồm 26 câu. Phạm vi kiểm thử mới,
  trường hợp tự nhiên và hai trường hợp ranh giới chờ Dev 2 + Tech Lead chốt.
- D1.0: thêm mục Cập nhật 08/11 vào snapshot và impact #36, SHA/hash hiện tại,
  PR25 đóng, PR35-40 merge. Giữ hồ sơ 06/11 có nhãn lịch sử.
- D1.3: issue #42 cho Tuần 10, không triển khai masker/API trong PR này.
- D1.2: ghi rõ chưa kiểm độc lập citation cấp Điểm.
- Dọn ba script/test Node .cjs khỏi PR; rút gọn JSON GitHub/kiểm tra lịch sử,
  bỏ đường dẫn máy local khỏi checks, không trình bày chúng thành kết quả mới.

## Kết quả xác thực

- Toàn bộ pytest: **1021 đạt, 1 bỏ qua**.
- `ruff check .`: 0 lỗi; `git diff --check`: 0 lỗi.
- Rà soát: 28 văn bản, 2.322 chunk, 851 dòng article, 766 alias;
  0 lỗi cấu trúc, 28 cảnh báo về giới hạn nguồn/hiệu lực cần người duyệt.
- Bàn giao Dev30: ĐẠT; 30 `source_checked`, 45 chunk Gold, 0 trùng Test;
  ghi rõ 3 cảnh báo sai khác toàn file nằm ngoài tập được chọn, không tắt kiểm tra tập con.
- Validator benchmark và freeze câu hỏi/Gold của Test: ĐẠT.
- Không sửa benchmark/corpus/registry hoặc cấu hình retrieval để làm các guard đạt.

## Review tiếp theo

D1.0: Tech Lead + Dev 4. D1.1: Dev 2 + Dev 3. D1.2: Dev 3 + Dev 5.
D1.4: Dev 2 + Tech Lead. D1.5 ở PR41: Dev 2 + Tech Lead, Dev 4/5 nhận bàn giao.
Không tự chốt nhãn ranh giới, hiệu lực pháp lý hoặc official A/B chỉ dựa trên việc kiểm thử đạt.
