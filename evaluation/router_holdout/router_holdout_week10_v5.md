# Router Week 10 Holdout v5

## Trạng thái

- 36 câu, ID `W15RH_001`–`W15RH_036`.
- 36/36 record ghi `reviewer_status=INDEPENDENT_REVIEW_COMPLETE`, reviewer `DEV2`.
- Đã chạy Router một lần; bộ holdout hiện ở trạng thái `CONSUMED`.

## Phân bố nhãn

| Route | Số câu |
|---|---:|
| `LEGAL_HNGD` | 10 |
| `LEGAL_OUT_OF_SCOPE` | 8 |
| `MIXED_LEGAL_SCOPE` | 6 |
| `NON_LEGAL` | 6 |
| `LEGAL_SCOPE_UNCERTAIN` | 6 |

## Kiểm tra và provenance

- Exact-text validator: PASS trên 9 nguồn đối chiếu trong repo, gồm holdout Week 10 v1–v4.
- Không phát hiện câu hỏi trùng nguyên văn; kiểm tra tự động không xác nhận semantic independence hoặc tính đúng đắn pháp lý của nhãn.
- SHA-256: `e15b154336cf45b3a836a6521a44c9ea4ab8d3f7066a4676384c6f7f54fd33e3`.
- Nguồn được cung cấp: `D:/router_holdout_week10_v5.jsonl`.
- Lần chạy: `2026-11-17T13:08:54.509247+00:00`; classifier `rule_router_v4_1`.
- Router source SHA-256: `33d80a59f021dafebab7fad9e048e5219be62aa2745aa2aea6a19fa3e33d559b`; Git HEAD lúc chạy: `58e70fb4250e3a5647835f2424661b5a4ab3ffff`; working tree dirty.
- Kết quả route/action: **14/36** (38.9%); **22 mismatch**: `W15RH_008`, `W15RH_010`–`W15RH_030`.
- Safety: **0** câu legal bị chuyển thành `GENERAL_CHAT`; safety gate PASS.
- Năm gate nền đều PASS: Official 30/30, Dev retrieval 270/270, Negative Set v2 26/26, non-legal 6/6, không có legal query bị chuyển thành non-legal/general chat.
- Không tinh chỉnh rồi chạy lại v5 như thể đây vẫn là đánh giá độc lập. Các lỗi có thể chuyển sang regression; đánh giá độc lập tiếp theo cần holdout mới.
