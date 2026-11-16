# D4.2 – Holdout độc lập cho Router

## Đầu vào
- Yêu cầu kiểm thử năm route/action của Router.
- Các nguồn đối chiếu trùng lặp: holdout R4IH v1, Dev270, Negative Set v2, regression data và test Router.
- Bộ câu hỏi ứng viên Week 10.

## Đầu ra
- Dataset: `evaluation/router_holdout/router_holdout_week10_v1.jsonl` (36 câu).
- Metadata, phạm vi và giới hạn review: `evaluation/router_holdout/router_holdout_week10_v1.md`.
- Validator: `scripts/validate_router_holdout.py`.

## Kết quả
- JSONL hợp lệ; 36 ID/câu hỏi duy nhất; đủ 5 route; mapping route/action hợp lệ.
- Validator đối chiếu 5 nguồn và không phát hiện trùng nguyên văn.
- Dev4 đã rà soát nhãn (`reviewer_status=DEV4`); chưa có reviewer độc lập, vì vậy chưa xác nhận độc lập.
- Smoke Router đã chạy trên bộ này: 22/36 khớp, 14 mismatch. Kết quả đã tiêu thụ; không dùng lại để tinh chỉnh. Bộ hiện tại không được gọi là holdout chưa dùng.

## Công nghệ đã dùng
JSONL, Python validation script, Unicode/text normalization, exact duplicate checks, route/action contract.
