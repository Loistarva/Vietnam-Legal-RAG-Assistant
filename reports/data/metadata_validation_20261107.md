# D1.1 — Kết quả kiểm tra ngày 07/11/2026

Bàn giao kỹ thuật: `pending_peer_review` (Dev 2 + Dev 3).

| Command | Result |
| --- | --- |
| `python scripts/audit_document_metadata.py` | PASS: errors=0; warnings=24; ambiguous_aliases=24 |
| `python -m pytest test/test_document_aliases.py -q` | 58 kiểm thử đạt trong 2,46 giây |
| `python scripts/validate_benchmark.py` | PASS. Handoff check chỉ chứng minh cấu trúc, chưa phải xác nhận gold pháp lý/production. |
| `python scripts/freeze_test.py --verify` | PASS: 30 câu Test chưa bị thay đổi |
| `python scripts/freeze_gold.py --verify` | PASS: Test Gold (30 câu) không đổi |
| `python -m pytest -q` | 761 passed, 1 skipped in 58.17s |

Kiểm tra dữ liệu bổ sung: 72 lượt chuyển đổi hai chiều canonical ID/number/file_code đạt; mọi dạng alias gốc đã khai báo đều chuẩn hóa về đúng khóa tương ứng.

stdout/stderr gốc, mã thoát và hash trước/sau: `metadata_validation_20261107.json`. Registry, corpus, Dev/Test/Gold và manifest freeze được bảo vệ không thay đổi. Full pytest chạy bằng fixture offline; một kiểm thử bị bỏ qua kế thừa từ trước không được tính là đạt.

Bản đồ alias: 24 văn bản; 562 khóa; 24 khóa có nhiều ứng viên; 62 khóa năm/năm-kèm-loại yếu cần ngữ cảnh định danh.

Phạm vi hồi quy gồm: biến thể số hiệu/tiêu đề/loại/năm, dấu tiếng Việt/dấu câu Unicode, số hiệu ngắn đã biết, tiêu đề dùng chung, gợi ý xung đột, năm đơn lẻ yếu, tên cơ quan đầy đủ chưa biết, bản đồ cũ/bị sửa, định danh/ngày registry sai, thiếu corpus/index, metadata không khớp và audit nông/một nhánh khi thiếu ref `origin/testing`.

Lỗi cấu trúc: 0. Có 24 cảnh báo về giới hạn hiện hữu trong cách biểu diễn hiệu lực cấp văn bản/điều khoản; đây không phải lỗi pháp lý mới được xác lập. Cờ `requires_review` vẫn áp dụng cho ND126, TT04/2020, TT57/2015 và ND123. Không tự động sửa dữ liệu hoặc suy ra đã xác minh nguồn mới.

Báo cáo kế hoạch chuẩn: `metadata_audit_20261103.md`; ngày audit thực tế trong báo cáo đó là 07/11/2026. Phần triển khai mã nguồn vẫn ở máy local/chưa commit tại thời điểm bàn giao này. Không gọi model bên ngoài, index đang chạy, quét URL HTTP hoặc official evaluation.
