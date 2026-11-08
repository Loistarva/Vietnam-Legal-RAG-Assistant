# D1.5 v1 — Kết quả kiểm tra bàn giao

Ngày: 06/11/2026 (Asia/Saigon). Nhánh: `feature/week09-dev1-negative-set`. Baseline: `f89ef8372a06102802349bb9ea0cf04fcc0a4646` (`testing`). Trạng thái nội dung: **pending_peer_review**, reviewer Dev 2 + Tech Lead.

## Kết quả thực chạy

Python môi trường dự án có sẵn: `Vietnam-Legal-RAG-Assistant-benchmark/.venv-gold/Scripts/python.exe`, chạy từ root worktree D1.5.

| Lệnh | Kết quả |
| --- | --- |
| `python scripts/validate_negative_set.py` | 24 câu, 6 câu mỗi nhóm, `issues=[]` |
| `python -m pytest test/test_negative_set.py -q` | 59 passed |
| `python scripts/validate_benchmark.py` | Handoff PASS, 270 Dev/30 Test, issues=0 |
| `python scripts/freeze_test.py --verify` | PASS, 30 câu Test không đổi |
| `python scripts/freeze_gold.py --verify` | PASS, Test Gold không đổi |
| `python -m pytest -q` | 701 passed, 1 skipped |

Test skipped thuộc bộ test kế thừa; không tính skipped thành pass. Full suite chạy offline/fixtures, không gọi model thật hay chạy official Test retrieval.

Log stdout/stderr và exit code của từng lệnh được lưu tại `validation_checks_v1.json`, kèm SHA baseline và hash dataset để đối chiếu.

Tests bảo vệ ID/câu hỏi trùng (kể cả bỏ dấu, khác hoa/thường/dấu câu), trùng benchmark, split sai, thiếu lý do, ngày sai, nhãn-route-action lệch, thiếu thông tin cần hỏi, nguồn đã được nạp, thiếu nhóm/sai số lượng và CLI từ chối manifest bị sửa hash. Đợt kiểm tra bổ sung chặn: bỏ snapshot kiểm tra trùng; root che nguồn trong metadata; ngày câu hỏi lệch manifest; JSON trùng khóa/NaN/Infinity hoặc số overflow; input sai kiểu gây traceback; ID dùng chữ số ngoài ASCII; câu hỏi không khớp nguồn khai báo; và collision mới trong benchmark đang checkout. BOM/CRLF hợp lệ vẫn PASS, validator không ghi lại input. Chỉ dùng fixture cho các ca gây lỗi; không chỉnh dữ liệu thật để chạy test.

## Fingerprint

- Dataset canonical SHA-256: `d859ba230231adf4e212a5de3b499c13a35e47744f60a712029a6ce9821b4bb5`.
- Corpus Git-blob SHA-256: `710350f1d0f9b66cb419d89fe7eabd655eba3330c8416534d475e43ce5048d9d`.
- Registry Git-blob SHA-256: `b33f6daf907c4570530ed29844c5b409451dff4a7524eb0177de122a571a4a32`.
- So khớp ID/câu hỏi chuẩn hóa với 270 Dev + 30 Test baseline, cộng 30 Test ở PR D1 SHA `6288e8c7868c198d4c12c9b8e0f7a49d445facd2`: không có collision. Có kiểm tra thêm cả Dev/Test đang checkout. Hai snapshot Test có nhiều câu chung, không coi là 60 câu Test độc lập.

Nguồn văn bản thiếu được kiểm ở cả document registry, trường số hiệu root và metadata của chunk. Đây là kiểm tra phạm vi nguồn nạp, không phải kết luận văn bản không tồn tại ngoài hệ thống. Các câu không có đáp án pháp luật và không gắn nhãn đã kiểm duyệt nguồn luật.

## Việc còn chờ reviewer/consumer

1. Dev 2 + Tech Lead duyệt nhãn và kiểm trùng ngữ nghĩa. Kiểm tra chuẩn hóa không thay thế được review semantic.
2. Tech Lead/Dev 4 xác nhận ba nhóm liên quan gia đình (nuôi con nuôi, hộ tịch gia đình, án phí ly hôn) thuộc route in-scope cho các ca yêu cầu nguồn sơ cấp. Điều chỉnh version trước calibration nếu phạm vi router khác.
3. Dev 4 ánh xạ vocabulary dataset vào router contract; Dev 5 tách calibration/evaluation theo hành vi. Không gán toàn bộ 24 câu thành relevance=0 hoặc kỳ vọng cùng một abstention.
4. Đối chiếu manifest 30 official IDs khi Dev 2 bàn giao. Các ID negative dùng namespace riêng; chưa có manifest official để xác nhận phép loại ID của tập calibration thực tế.
5. Nếu code/prompt/config Freeze đã diễn ra, calibration mới phải theo quyết định nhóm và ghi run/version riêng; không thay kết quả official đã khóa. Chưa chọn threshold hoặc chạy inference trong D1.5 này.

Không đổi benchmark, corpus, canonical runtime schema hoặc freeze manifest. Đây là tập synthetic nhỏ phục vụ kiểm tra hành vi ban đầu, không chứng minh độ bao phủ tình huống thực tế. Không thể suy ra đã thử mọi lỗi có thể tồn tại. Tập negative và công cụ chỉ phục vụ Dev; chưa chứng minh router, model hay Gate đã hoạt động đúng. Chưa commit/push ở thời điểm lập báo cáo.

## Cập nhật trước push — 07/11/2026

Giữ nguyên 24 câu, nhãn và hash canonical. Bổ sung cờ opt-in `--fetch-sources` và bước CI tải đúng SHA còn thiếu trước pytest, do checkout của GitHub Actions mặc định là shallow. Không checkout/merge hoặc thay nguồn pin bằng branch HEAD mới.

Test hồi quy tạo Git repo/clone mỏng tạm, xác nhận commit thiếu được tải, không đổi HEAD/working tree, không tải lại commit đã có và không nhận ref chưa pin/option-like. Kết quả thực chạy sau bổ sung: **61 test D1.5 passed; full suite 703 passed, 1 skipped**. Các raw logs v1 phía trên giữ nguyên kết quả lần kiểm tra 06/11, không được mô tả là log CI của lần push mới.
