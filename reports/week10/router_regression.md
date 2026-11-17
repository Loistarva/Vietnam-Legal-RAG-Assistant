# D4.1 — Router: freeze record và bằng chứng regression

## Đầu vào

- Contract route/action canonical trong `schemas/models.py`.
- Official Dev Gold: 30 ID; Dev benchmark: 270 câu; Negative Set v2: 26 câu.
- Regression holdout nội bộ: `test/agent/data/router_holdout.jsonl` (40 câu).
- Router `rule_router_v3` tại commit nền `f0c7c295f4804dc4a8e37f7a03b60c1519578af7`.
- Holdout Week 10 v1 (36 câu) đã tiêu thụ; không dùng để chỉnh Router. Holdout v2 được Dev3 review độc lập và đã chạy đúng một lần trên `rule_router_v3`; kết quả chi tiết ở [router_holdout_report.md](router_holdout_report.md).

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

- Week 10 holdout v1: kết quả lịch sử 22/36 route/action, 14 mismatch. Metadata lần chạy ngày 2026-11-16 không ghi Git SHA hoặc classifier version, nên không thể xác nhận điểm 22/36 thuộc `rule_router_v3` đã freeze. Không dùng mismatch để tối ưu Router và không gọi đây là holdout độc lập sau freeze.
- Week 10 v2: 36/36 câu đã được Dev3 review độc lập, validator exact-text pass trên sáu nguồn. Đã chạy đúng một lần trên Router SHA frozen; 17/36 route/action khớp, 19 mismatch, có 1 legal-to-GENERAL_CHAT safety violation. V2 đã tiêu thụ, không dùng để chỉnh v3.

## Freeze record

`rule_router_v3` được project owner ủy quyền freeze ngày 2026-11-17 sau khi policy `NEG_DEV_026` được xác nhận, Dev5 xác nhận contract và các pre-freeze gate đạt. Negative Set v2 hiện đã được Dev2 review độc lập và Tech Lead sign-off theo SHA canonical `5584795887e876f15febc05e7f04107b67862492d8a3d027840c01514d75223f`; trạng thái manifest là `peer_reviewed`. Kết quả Negative Set 26/26 vẫn chỉ là smoke evidence theo phần route/action thuộc Router, không phải đánh giá độc lập trên holdout.

- Router source commit: `f0c7c295f4804dc4a8e37f7a03b60c1519578af7`.
- Commit ghi nhận pre-freeze harness, policy và bằng chứng: `10daaad7`.
- Router source SHA-256: `41b25945b8111ca38bbc3fa2aef302e3c924f23eb4d952eaf37e526073dd107d`.
- Corpus SHA-256: `7105c484061399010b0f087c6c0d457cd688030b8184b0071f1291a036b6b023`.
- Canonical schema: `week10_v1.1`.
- Lệnh freeze smoke: `python scripts/smoke_rule_router.py --skip-holdout` (5/5 gates PASS; không đọc holdout).
- Kiểm thử tập trung: 127 passed, 84 subtests; Ruff all checks passed.

Manifest Negative Set hiện để `review_status=peer_reviewed`; Dev2 và Tech Lead sign-off đúng SHA canonical nêu trên. Holdout v2 đã tiêu thụ và không đạt acceptance gate về safety/classification. Giữ nguyên kết quả; nếu muốn sửa Router, dùng regression/Dev, tăng version, rồi tạo holdout độc lập mới.

## Công nghệ đã dùng

Python rule-based classifier, canonical Pydantic route contract, JSONL, pytest/subtests, Ruff và SHA-256 provenance.

## Ứng viên `rule_router_v4` sau review (2026-11-17)

Đây là thay đổi phiên bản mới sau freeze v3, dựa trên các lỗi thiết kế đã phân tích ở trên và các paraphrase regression mới; **không dùng mismatch holdout để tiếp tục tinh chỉnh hoặc thay thế kết quả holdout v2**.

- Sửa precedence lời chào: chỉ nhận diện greeting đầy đủ hoặc câu chào kèm ý định trò chuyện trên văn bản gốc; không bỏ dấu cụm greeting để tránh va chạm `chào bạn`/`chào bán`.
- Thêm nhóm tín hiệu có ngữ cảnh cho quan hệ/chủ đề HNGĐ và các nhóm luật ngoài phạm vi; cụm doanh nghiệp/đất đai/di trú trong câu HNGĐ được giữ là mixed khi thực sự có tín hiệu phạm vi thứ hai.
- Thêm nhận diện một số ý định phi pháp lý đời thường (lập trình, lịch tham quan, hiện tượng tự nhiên, chăm sóc cây); giữ fallback an toàn cho câu hỏi chưa rõ.
- Bổ sung 20 paraphrase regression gồm HNGĐ, ngoài phạm vi, mixed, non-legal và cặp đối kháng greeting/corporate sale.
- Phiên bản classifier: `rule_router_v4`; SHA-256 file Router: `44466e654e4536b840707003040d7b668ea726db1e6199e123d2144616fffc94`.
- `python scripts/smoke_rule_router.py --skip-holdout`: **5/5 gate PASS** — Official 30/30, Dev 270/270 retrieval, Negative Set v2 26/26, non-legal 6/6, không có legal query sang chat. Không đánh giá holdout.
- Test tập trung: `130 passed, 105 subtests passed`; `ruff check` trên Router và test: pass; `git diff --check`: pass.
- Trạng thái: **ứng viên v4, chưa freeze**. V2 đã consumed; cần review thay đổi và dùng một holdout mới độc lập (ví dụ v3) nếu cần đánh giá chất lượng ngoài Dev/regression. Không gọi các gate Dev/Negative là bằng chứng holdout.

## Freeze Router `rule_router_v4_1` — 2026-11-17

- Trạng thái: **FROZEN**; commit chứa source Router và test: `48a9c051dfd14ea0f78e4a708f6aec0526cf3175`.
- `CLASSIFIER_VERSION`: `rule_router_v4_1`.
- SHA-256 source `agent/router/rule_router.py`: `2d0ae791e2476afa33a49fc5207496a83faa17c2f22784b33ea3bb0dc8d26a5a`.
- Pre-freeze smoke `--skip-holdout`: 5/5 gates PASS; Official 30/30, Dev retrieval 270/270, Negative Set v2 26/26, non-legal 6/6, legal-to-chat 0.
- Kiểm thử: Router 53 passed/239 subtests; Negative Set 65 passed; Ruff và `git diff --check` pass.
- Holdout Week 10 v3 đã được review độc lập bởi Dev3 và **chưa chạy**. Manifest SHA của code, holdout và bằng chứng freeze: [router_holdout_week10_v3_manifest.json](../evaluation/router_holdout/router_holdout_week10_v3_manifest.json).
- Các thay đổi cục bộ khác trong working tree không nằm trong commit freeze Router.
- SHA-256 dùng trong manifest là hash source đã chuẩn hóa LF; hash byte thô của checkout Windows cũng được lưu riêng để đối chiếu smoke output. Hai giá trị hiện cùng là `2d0ae791e2476afa33a49fc5207496a83faa17c2f22784b33ea3bb0dc8d26a5a`.
