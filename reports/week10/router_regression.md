# D4.1 – Rule Router và regression

## Đầu vào
- SRS và canonical route/action contract trong `schemas/models.py`.
- Dev Gold (30 câu), Dev benchmark (270 câu), Negative Set v2 (26 câu), holdout Week 10 (36 câu).
- Mã Router `agent/router/rule_router.py`, classifier `rule_router_v3`.

## Đầu ra
- Router và regression tests tại `agent/router/rule_router.py`, `test/agent/test_rule_router.py`.
- Kết quả đánh giá tổng hợp trong báo cáo này.

## Kết quả
- Dev Gold: 30/30 `LEGAL_HNGD`; Dev benchmark: 270/270 `LEGAL_RETRIEVAL`.
- Negative Set v2: 26/26 route/action khớp theo nhãn hiện có; 6/6 non-legal được route `NON_LEGAL`; không có câu legal nào thành `GENERAL_CHAT`.
- Bộ Week 10: 22/36 route/action khớp, 14 mismatch. Holdout đã được chạy nên được xem là đã tiêu thụ, không dùng để tinh chỉnh tiếp.
- Router **chưa freeze**: còn mismatch holdout và `NEG_DEV_026` cần Tech Lead chốt; cần review độc lập và khóa code/config trước khi freeze.
- Phiên bản `rule_router_v3`; corpus SHA-256 chuẩn hóa: `7105c484061399010b0f087c6c0d457cd688030b8184b0071f1291a036b6b023`.

## Công nghệ đã dùng
Python rule-based classifier, Pydantic canonical route contract, pytest/subtests, JSONL benchmark/holdout, SHA-256 provenance.
