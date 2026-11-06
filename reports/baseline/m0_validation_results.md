# D1.0 — Kiểm tra bản sửa mới và vấn đề còn lại

Audit 06/11/2026. So sánh code trên từng head riêng; không merge mọi nhánh vào planning. GitHub API và CI được lưu tại github_state_20261106.json; raw local logs tại checks_*.json.

## 1. Kết quả chạy độc lập

| Checkout | SHA | Validator/freeze | pytest toàn bộ cấu hình repo |
| --- | --- | --- | --- |
| testing | f89ef83 | PASS cả 3 | 642 passed, 1 skipped in 29.74s |
| pr25 | 54c0e37 | PASS cả 3 | 644 passed, 1 skipped in 30.03s |
| pr27 | 6288e8c | PASS cả 3 | 642 passed, 1 skipped in 29.20s |
| pr32 | 1700f91 | PASS cả 3 | 658 passed, 1 skipped in 29.64s |

Mỗi checkout chạy scripts/validate_benchmark.py, scripts/freeze_test.py --verify, scripts/freeze_gold.py --verify và python -m pytest -q; HF_HUB_OFFLINE=1, TRANSFORMERS_OFFLINE=1. Python/runtime cụ thể có trong JSON. Không chạy model thật hoặc official A/B/Test retrieval. Một test skipped được giữ đúng trạng thái; không chứng minh nguồn luật đã được duyệt hết.

Raw logs lưu exit_code riêng của từng lệnh; tất cả validator/freeze/pytest trong bảng đều exit 0.

## 2. Phần đã sửa — không mở lại lỗi cũ

- PR #25: placeholder, validator và draft clause-overlap đã được sửa trong phạm vi PR; confirmed mapping không tương đương source_checked. Không kết luận 195 draft là lỗi mới.
- PR #26: đã squash-merge tại f89ef83; không còn “chờ merge #26”.
- PR #27: xác nhận Dev 3/Dev 5, sửa answer/citation/reviewer và re-freeze Test đã push; CI #134/#133 success. Chênh hash giữa PR và testing là có giải thích, không tự gọi là corruption.
- PR #32: CI mới #130/#129 success. Run lỗi cũ #125 thuộc deda63d không phải trạng thái head hiện hành. #28 đã đóng chưa merge, không dùng CI đỏ #28 để kết luận metrics mới đang lỗi.

## 3. Khoảng thiếu Tuần 9 đã nhìn thấy trong code hiện tại

| ID | Kết luận có phạm vi | Bằng chứng / hành động |
| --- | --- | --- |
| W9-01 | Zero-shot chưa sẵn sàng official Tuần 9, dù CI metrics xanh | PR #32 scripts/run_zero_shot_dev.py nhận --queries tùy ý và gọi run_benchmark; evaluation/zero_shot.py::load_questions kiểm ID/question nhưng chưa kiểm Dev-only/source_checked/30-ID manifest. Cần guard và chọn đúng official IDs trước gọi model. |
| W9-02 | Đường Zero-shot Test còn thiếu holdout guard | PR #32 scripts/run_zero_shot_test.py mặc định queries_test.json và gọi generation không kiểm freeze/approval. evaluation/test_run_freeze.py có guard cho retrieval Test nhưng không tự bảo vệ entry point này. Chưa chạy script; Dev 2 cần khóa/tách đường này trước bàn giao. |
| W9-03 | Generation config/output chưa theo V3 | PR #32 evaluation/zero_shot.py::answer_question dùng num_predict=512; chỉ truyền question, chưa truyền benchmark as_of_date và chưa lưu done_reason/truncation. Kế hoạch đề xuất 1024 hoặc giá trị M1; Dev 3/2 cần chốt và đồng bộ A/B. Không retune trên 30 official IDs. |
| W9-04 | Artifacts M0/M1 còn thiếu ở các head khảo sát | Không có evaluation/manifests/dev_gold_30_manifest.json/rubric guide ở testing hoặc PR heads khảo sát. Cần Dev 2 bàn giao, Dev 1 D1.4 kiểm leakage; score sheet chỉ sau blind scoring. |
| W9-05 | G3/index identity chưa xác minh đủ | Cần owner chỉ artifact đã push/version/hash và ES/Qdrant identity. Không có tên nhánh results/rerank không đủ để kết luận artifact không tồn tại. |

Probe tái lập: Python scripts/probe_week09_zero_shot.py <PR32 checkout> <result.json>. zero_shot_probe_pr32.json xác nhận loader nhận câu synthetic split=test, mock generation dùng num_predict=512 và trả str làm mất done_reason. Không đọc Test thật và không gọi model thật.

Đây là khoảng thiếu so với yêu cầu Tuần 9 và các điều kiện tích hợp, không phải lý do tuyên bố toàn bộ sửa Sprint 6 thất bại. Không sửa code thuộc Dev 2/3/4/5 trong D1.0; report chỉ nêu bằng chứng và consumer requirement.

## 4. Kiểm tra công cụ audit trước commit

Evidence guard đã kiểm bằng node --test test/test_week09_evidence_guard.cjs: chặn log thiếu command, exit lỗi/timeout, SHA cũ, thiếu bằng chứng clean checkout, checkout bị sửa, PR metadata trùng, freeze mismatch và probe cũ. Node/Python/PowerShell syntax đã kiểm riêng. Không lấy PASS từ câu chữ cố định: generator chỉ sinh báo cáo sau khi validateEvidence chấp nhận đầy đủ bằng chứng đúng SHA và exit 0.

## 5. Kết luận

Không thấy failure trong full pytest của bốn checkout đã chạy. Các sửa mới đã được tính vào snapshot, kể cả squash merge #26 và PR #32 thay #28. D1.0 có đủ báo cáo/hash/config/impact/test evidence để review. M0 vẫn cần Tech Lead ghi accept/defer các PR mở, chốt corpus/Test sau tích hợp và xác nhận handoff/Dev30/M1; CI xanh không thay thế các quyết định đó.
