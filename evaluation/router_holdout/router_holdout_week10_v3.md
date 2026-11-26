# Router Week 10 Holdout v3

## Trạng thái

- Bộ holdout gồm 36 câu, được tiếp nhận từ `router_holdout_v3_36_diverse.jsonl`.
- Theo xác nhận/yêu cầu của người dùng, reviewer độc lập là **Dev3** đã hoàn tất review; `reviewer_status` của 36/36 dòng được cập nhật thành `INDEPENDENT_REVIEW_COMPLETE`.
- Bộ này chưa được chạy qua Router trong bước cập nhật này.

## Phân bố nhãn

| Route | Số câu |
|---|---:|
| `LEGAL_HNGD` | 10 |
| `LEGAL_OUT_OF_SCOPE` | 8 |
| `MIXED_LEGAL_SCOPE` | 6 |
| `NON_LEGAL` | 6 |
| `LEGAL_SCOPE_UNCERTAIN` | 6 |

## Kiểm tra và provenance

- Validator kiểm tra JSONL, trường bắt buộc, route/action, ID và câu hỏi duy nhất, cùng exact-text overlap với các nguồn repository mặc định.
- Kiểm tra tự động không xác nhận semantic independence hay tính đúng đắn pháp lý của nhãn; các nội dung đó thuộc phạm vi review của reviewer.
- SHA-256 đầu vào trước chuyển trạng thái: `32a2e637031c8d01413a52974cdcd45d583018e35b4f0b4b698f696986f8b362`.
- SHA-256 JSONL sau cập nhật: `22e1460d1b3ff85112fd51e588cfa8022ca062be9d8cc7988c9c861700b6603e`.
- Ngày review không được cung cấp trong yêu cầu nên không ghi ngày để tránh suy đoán.


## Router freeze reference

- Frozen Router: `rule_router_v4_1`, commit `48a9c051dfd14ea0f78e4a708f6aec0526cf3175`.
- Router source SHA-256: `2d0ae791e2476afa33a49fc5207496a83faa17c2f22784b33ea3bb0dc8d26a5a`.
- Evaluation manifest: [`router_holdout_week10_v3_manifest.json`](router_holdout_week10_v3_manifest.json); holdout status: `CONSUMED`.


## K?t qu? ch?y holdout m?t l?n

- Run UTC: `2026-11-17T12:23:06.246852+00:00`; Router: `rule_router_v4_1`; commit ch?y: `c9aef50c54cccc776b863ad3480339146af28bab`. SHA Router v? SHA JSONL kh?p manifest.
- Exact route/action: **24/36**; **12 mismatch**: `W13RH_006`, `W13RH_011`, `W13RH_013`, `W13RH_014`, `W13RH_015`, `W13RH_016`, `W13RH_018`, `W13RH_020`, `W13RH_021`, `W13RH_022`, `W13RH_023`, `W13RH_024`.
- Safety: **0** c?u ph?p l? b? chuy?n th?nh `NON_LEGAL`/`GENERAL_CHAT`; safety gate PASS. N?m pre-freeze gate ti?p t?c PASS; gate exact route/action c?a holdout FAIL.
- Holdout ?? consumed. Kh?ng tinh ch?nh v4.1 theo c?c mismatch r?i ch?y l?i v3.
