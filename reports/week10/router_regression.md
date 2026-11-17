# D4.1 — Router: kết quả pre-freeze

## Đầu vào

- Contract route/action canonical trong `schemas/models.py`.
- Official Dev Gold: 30 ID; Dev benchmark: 270 câu; Negative Set v2: 26 câu.
- Regression holdout nội bộ: `test/agent/data/router_holdout.jsonl` (40 câu).
- Router `rule_router_v3` tại commit nền `f0c7c295f4804dc4a8e37f7a03b60c1519578af7`.
- Holdout Week 10 v1 (36 câu) là dữ liệu đã tiêu thụ; không dùng để chỉnh Router. Holdout v2 đã được Dev3 review độc lập nhưng chưa chạy.

## Đầu ra

- Router: `agent/router/rule_router.py`.
- Freeze smoke có chế độ không đọc holdout: `scripts/smoke_rule_router.py --skip-holdout`.
- Regression tests: `test/agent/test_rule_router.py`, `test/test_smoke_rule_router.py`, `test/test_validate_router_holdout.py`, `test/test_negative_set.py`.
- Quy trình freeze và mở holdout: `docs/router_freeze_holdout_verification.md`.

## Kết quả kiểm tra ngày 2026-11-17

Lệnh pre-freeze `python scripts/smoke_rule_router.py --skip-holdout` **PASS**. Lệnh không đọc hoặc chấm holdout nào.

| Gate | Kết quả |
|---|---:|
| Official Dev Gold route/action `LEGAL_HNGD` + `LEGAL_RETRIEVAL` | 30/30 — PASS |
| Dev benchmark action `LEGAL_RETRIEVAL` | 270/270 (100%) — PASS |
| Negative Set route và action thuộc Router | 26/26 — PASS |
| Negative Set non-legal route/action `NON_LEGAL` + `GENERAL_CHAT` (no RAG) | 6/6 — PASS |
| Legal query thành `NON_LEGAL` hoặc `GENERAL_CHAT` | 0 — PASS |
| Regression holdout nội bộ hiện hành | 40/40 — PASS |
| Kiểm thử tập trung Router/holdout/Negative Set | 127 passed, 84 subtests passed — PASS |
| Ruff trên các file liên quan | All checks passed |

`INSUFFICIENT_EVIDENCE_ABSTENTION` và `CLARIFICATION` trong Negative Set là action downstream của Orchestrator; Router chỉ chịu trách nhiệm route `LEGAL_HNGD` và action `LEGAL_RETRIEVAL` cho các câu in-scope. Báo cáo 26/26 vì vậy đánh giá route trên toàn bộ tập và action đúng phạm vi sở hữu của Router.

## Holdout đã tiêu thụ và giới hạn

- Week 10 v1: kết quả lịch sử 22/36 route/action, 14 mismatch. Không dùng các mismatch này để tối ưu Router và không gọi đây là holdout độc lập sau freeze.
- Week 10 v2: 36/36 câu đã được Dev3 review độc lập; validator exact-text pass trên sáu nguồn. **Chưa chạy** để giữ nguyên vai trò holdout chưa thấy.

## Freeze record

`rule_router_v3` được project owner ủy quyền freeze ngày 2026-11-17 sau khi policy `NEG_DEV_026` được xác nhận và owner báo Dev2 đã review độc lập, Dev5 đã xác nhận contract. Không có thay đổi hành vi trong `agent/router/rule_router.py`, nên giữ nguyên version `rule_router_v3`. Xác nhận Dev2 chưa được gắn với SHA cụ thể của Negative Set; không dùng kết quả 26/26 này làm chứng nhận calibration cho đến khi đối chiếu SHA review.

- Router source commit: `f0c7c295f4804dc4a8e37f7a03b60c1519578af7`.
- Commit ghi nhận pre-freeze harness, policy và bằng chứng: `10daaad7`.
- Router source SHA-256: `41b25945b8111ca38bbc3fa2aef302e3c924f23eb4d952eaf37e526073dd107d`.
- Corpus SHA-256: `7105c484061399010b0f087c6c0d457cd688030b8184b0071f1291a036b6b023`.
- Canonical schema: `week10_v1.1`.
- Lệnh freeze smoke: `python scripts/smoke_rule_router.py --skip-holdout` (5/5 gates PASS; không đọc holdout).
- Kiểm thử tập trung: 127 passed, 84 subtests; Ruff all checks passed.

Manifest Negative Set vẫn để `review_status=pending_peer_review`: project owner báo Dev2 đã review nhưng chưa có SHA bản review; Tech Lead review đầy đủ dataset chưa được ghi nhận. Vì vậy 26/26 chỉ là smoke evidence cho Router, không chứng nhận dataset đã được duyệt để calibration. Holdout v2 vẫn chưa chạy; giữ riêng cho evaluation sau freeze và không chỉnh Router theo kết quả của nó.

## Công nghệ đã dùng

Python rule-based classifier, canonical Pydantic route contract, JSONL, pytest/subtests, Ruff và SHA-256 provenance.
