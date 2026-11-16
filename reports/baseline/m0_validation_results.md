# D1.0 — Kiểm tra bản sửa mới và vấn đề còn lại

Rà soát ngày 06/11/2026. So sánh mã nguồn trên từng head riêng; không merge mọi nhánh vào planning. GitHub API và CI được lưu tại `github_state_20261106.json`; log local gốc tại `checks_*.json`.

## 1. Kết quả chạy độc lập

| Bản checkout | SHA | Validator/freeze | pytest toàn bộ cấu hình repo |
| --- | --- | --- | --- |
| testing | f89ef83 | Cả 3 đều đạt | 642 đạt, 1 bỏ qua trong 29,74 giây |
| pr25 | 54c0e37 | Cả 3 đều đạt | 644 đạt, 1 bỏ qua trong 30,03 giây |
| pr27 | 6288e8c | Cả 3 đều đạt | 642 đạt, 1 bỏ qua trong 29,20 giây |
| pr32 | 1700f91 | Cả 3 đều đạt | 658 đạt, 1 bỏ qua trong 29,64 giây |

Mỗi bản checkout chạy `scripts/validate_benchmark.py`, `scripts/freeze_test.py --verify`, `scripts/freeze_gold.py --verify` và `python -m pytest -q`; `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`. Phiên bản Python/môi trường chạy cụ thể có trong JSON. Không chạy model thật hoặc truy xuất official A/B/Test. Một kiểm thử bị bỏ qua được giữ đúng trạng thái; kết quả này không chứng minh mọi nguồn luật đã được duyệt.

Log gốc lưu `exit_code` riêng của từng lệnh; mọi validator/freeze/pytest trong bảng đều kết thúc với mã 0.

## 2. Phần đã sửa — không mở lại lỗi cũ

- PR #25: placeholder, validator và bản nháp trùng điều khoản đã được sửa trong phạm vi PR; mapping đã xác nhận không đồng nghĩa với `source_checked`. Không kết luận 195 bản nháp là lỗi mới.
- PR #26: đã squash-merge tại f89ef83; không còn “chờ merge #26”.
- PR #27: xác nhận Dev 3/Dev 5, sửa câu trả lời/trích dẫn/reviewer và freeze lại Test đã được push; CI #134/#133 thành công. Chênh lệch hash giữa PR và testing đã có giải thích, không tự kết luận là hỏng dữ liệu.
- PR #32: CI mới #130/#129 thành công. Lần chạy lỗi cũ #125 thuộc `deda63d`, không phải trạng thái head hiện hành. #28 đã đóng, chưa merge; không dùng CI đỏ #28 để kết luận metric mới đang lỗi.

## 3. Hạng mục Tuần 9 còn thiếu trong mã nguồn hiện tại

| ID | Kết luận có phạm vi | Bằng chứng / hành động |
| --- | --- | --- |
| W9-01 | Zero-shot chưa sẵn sàng official Tuần 9, dù CI metrics xanh | PR #32 scripts/run_zero_shot_dev.py nhận --queries tùy ý và gọi run_benchmark; evaluation/zero_shot.py::load_questions kiểm ID/question nhưng chưa kiểm Dev-only/source_checked/30-ID manifest. Cần guard và chọn đúng official IDs trước gọi model. |
| W9-02 | Đường Zero-shot Test còn thiếu holdout guard | PR #32 scripts/run_zero_shot_test.py mặc định queries_test.json và gọi generation không kiểm freeze/approval. evaluation/test_run_freeze.py có guard cho retrieval Test nhưng không tự bảo vệ entry point này. Chưa chạy script; Dev 2 cần khóa/tách đường này trước bàn giao. |
| W9-03 | Generation config/output chưa theo V3 | PR #32 evaluation/zero_shot.py::answer_question dùng num_predict=512; chỉ truyền question, chưa truyền benchmark as_of_date và chưa lưu done_reason/truncation. Kế hoạch đề xuất 1024 hoặc giá trị M1; Dev 3/2 cần chốt và đồng bộ A/B. Không retune trên 30 official IDs. |
| W9-04 | Artifacts M0/M1 còn thiếu ở các head khảo sát | Không có evaluation/manifests/dev_gold_30_manifest.json/rubric guide ở testing hoặc PR heads khảo sát. Cần Dev 2 bàn giao, Dev 1 D1.4 kiểm leakage; score sheet chỉ sau blind scoring. |
| W9-05 | G3/index identity chưa xác minh đủ | Cần owner chỉ artifact đã push/version/hash và ES/Qdrant identity. Không có tên nhánh results/rerank không đủ để kết luận artifact không tồn tại. |

Probe tái lập: Python scripts/probe_week09_zero_shot.py <PR32 checkout> <result.json>. zero_shot_probe_pr32.json xác nhận loader nhận câu synthetic split=test, mock generation dùng num_predict=512 và trả str làm mất done_reason. Không đọc Test thật và không gọi model thật.

Đây là khoảng thiếu so với yêu cầu Tuần 9 và các điều kiện tích hợp, không phải lý do tuyên bố toàn bộ sửa Sprint 6 thất bại. Không sửa code thuộc Dev 2/3/4/5 trong D1.0; report chỉ nêu bằng chứng và consumer requirement.

## 4. Kiểm tra công cụ rà soát trước commit

Cơ chế kiểm soát bằng chứng đã được kiểm bằng `node --test test/test_week09_evidence_guard.cjs`: chặn log thiếu lệnh, lỗi/timeout, SHA cũ, thiếu bằng chứng checkout sạch, checkout bị sửa, metadata PR trùng, freeze không khớp và probe cũ. Cú pháp Node/Python/PowerShell đã được kiểm riêng. Không lấy trạng thái đạt từ câu chữ cố định: bộ sinh chỉ tạo báo cáo sau khi `validateEvidence` xác nhận đủ bằng chứng đúng SHA và mã thoát 0.

## 5. Kết luận

Không thấy lỗi trong toàn bộ pytest của bốn bản checkout đã chạy. Các sửa mới đã được tính vào ảnh chụp, gồm squash merge #26 và PR #32 thay #28. D1.0 có đủ báo cáo/hash/config/tác động/bằng chứng kiểm thử để review. M0 vẫn cần Tech Lead ghi nhận chấp nhận/hoãn các PR đang mở, chốt corpus/Test sau tích hợp và xác nhận handoff/Dev30/M1; CI xanh không thay thế các quyết định đó.
