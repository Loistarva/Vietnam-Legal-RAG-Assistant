# Sửa CI shallow checkout — 06/11/2026

Job báo lỗi: https://github.com/Loistarva/Vietnam-Legal-RAG-Assistant/actions/runs/42233659737/job/127945608309, commit `73b6677`. GitHub metadata xác nhận lỗi ở pytest; endpoint tải log không cho phép đọc không xác thực. Diagnosis được tái hiện bằng clone local `--no-local --depth 1`, tương đương điều kiện Git history của actions/checkout mặc định.

Trước sửa: test Dev30 có 6 passed/26 errors tại setup vì `git show <pinned SHA>:...` không tìm được commit baseline/nhánh chưa merge. Local worktree trước đó có toàn bộ object nên không tái hiện được lỗi CI này.

Sửa: thêm bước `python scripts/fetch_dev30_sources.py` sau setup-python, trước dependency/tests. Helper kiểm tra và chỉ fetch SHA còn thiếu, pin đúng ba phiên bản nguồn theo policy, không đổi HEAD, không merge và không thay dữ liệu. `prepare_dev30.py` báo rõ lệnh khắc phục khi thiếu commit. Không skip test hoặc thay nguồn pin bằng HEAD hiện hành.

Kiểm tra sau sửa:

- Trên shallow clone thật: helper fetch 3 commit thiếu, 32 test Dev30 passed.
- Test selection + fetch helper: 37 passed. Test hồi quy tạo một Git repo/clone mỏng tạm, kiểm source cũ được phục hồi, HEAD và working tree giữ nguyên, lần chạy sau không fetch lại, từ chối SHA không pin/option-like input.
- Full suite local: **679 passed, 1 skipped**.
- `prepare_dev30.py`: PASS; query canonical SHA-256 vẫn `7f413e19934b6b216c71c90482c27cd9a29e8556842a10fa7c22b505c1340421`.

Báo cáo/check logs v1 trước đó vẫn mô tả lần chạy local tại thời điểm chuẩn bị, không coi chúng là kết quả CI hoặc ghi đè lịch sử. Run GitHub mới cần kiểm tra sau khi push; báo cáo này không tự tuyên bố CI remote đã xanh.
