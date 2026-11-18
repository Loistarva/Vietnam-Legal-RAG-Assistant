# Router Week 10 Holdout v4

## Trạng thái

- 36 câu, ID `W14RH_001`–`W14RH_036`.
- 36/36 record ghi `reviewer_status=INDEPENDENT_REVIEW_COMPLETE`, reviewer `DEV2`.
- Đã chạy Router trên bộ này một lần; trạng thái hiện tại là `CONSUMED`.

## Phân bố nhãn

| Route | Số câu |
|---|---:|
| `LEGAL_HNGD` | 10 |
| `LEGAL_OUT_OF_SCOPE` | 8 |
| `MIXED_LEGAL_SCOPE` | 6 |
| `NON_LEGAL` | 6 |
| `LEGAL_SCOPE_UNCERTAIN` | 6 |

## Kiểm tra và provenance

- Exact-text validator: PASS trên 8 nguồn đối chiếu trong repo, bao gồm holdout Week 10 v1–v3.
- Validator không xác nhận semantic independence hoặc tính đúng đắn pháp lý của nhãn; các nội dung này cần review nội dung.
- SHA-256: `1048ea99b8f05a965cc552d138046e2ee2783e956dfa3bb880939e6824eb549c`.
- Nguồn được cung cấp: `D:/router_holdout_week10_v4.jsonl`.
- Lần chạy: `2026-11-17T12:49:21.068388+00:00`; classifier `rule_router_v4_1`.
- Router source SHA-256: `2ca3f7eabde005ff1dca551dce28ff937a9c6f69af943c6dee259074b5e746bf`; Git HEAD lúc chạy: `58e70fb4250e3a5647835f2424661b5a4ab3ffff`; working tree dirty.
- Kết quả route/action: **17/36** (47.2%); **19 mismatch**: `W14RH_004`, `W14RH_007`, `W14RH_012`, `W14RH_013`, `W14RH_014`, `W14RH_016`, `W14RH_017`, `W14RH_019`–`W14RH_030`.
- Safety: **0** câu legal bị chuyển thành `GENERAL_CHAT`; safety gate PASS.
- Năm gate nền đều PASS: Official 30/30, Dev retrieval 270/270, Negative Set v2 26/26, non-legal 6/6, không có legal query bị chuyển thành non-legal/general chat.
- Không dùng lại bộ v4 để tinh chỉnh rồi báo cáo lại như holdout độc lập. Các câu đã xem có thể chuyển sang regression; đánh giá độc lập tiếp theo cần holdout mới.
- Sau lần đánh giá, Router đã được chỉnh bằng các mẫu paraphrase làm regression: source SHA hiện tại `33d80a59f021dafebab7fad9e048e5219be62aa2745aa2aea6a19fa3e33d559b`. Kết quả 17/36 phía trên vẫn chỉ áp dụng cho source SHA tại thời điểm chạy (`2ca3f7e...`), không phải code hiện tại.
- Regression sau chỉnh sửa: Router tests **55 passed, 270 subtests**; freeze gates bỏ qua holdout **5/5 PASS**; Ruff và `git diff --check` PASS.
- Không chạy lại holdout v4 sau chỉnh sửa; v4 vẫn được ghi nhận là tiêu thụ đúng một lần.
