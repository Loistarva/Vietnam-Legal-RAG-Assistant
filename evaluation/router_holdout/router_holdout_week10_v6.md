# Router Week 10 Holdout v6

## Trạng thái

- 36 câu mới hoàn toàn, ID `W16RH_001`–`W16RH_036`, dùng để đánh giá một lần sau khi chốt kiến trúc `rule_router_v5`.
- Cả 36/36 bản ghi mang `reviewer_status=DEV4` (do kỹ sư soạn độc lập với code `v5` sau khi khóa `rule_router_v5`; chưa có xác nhận độc lập từ Dev2/Dev3).
- Đã chạy đánh giá một lần duy nhất trên `rule_router_v5`; trạng thái hiện tại là `CONSUMED` (không dùng để tinh chỉnh `rule_router_v5`).

## Phân bố nhãn

| Route | Số câu |
|---|---:|
| `LEGAL_HNGD` | 10 |
| `LEGAL_OUT_OF_SCOPE` | 8 |
| `MIXED_LEGAL_SCOPE` | 6 |
| `NON_LEGAL` | 6 |
| `LEGAL_SCOPE_UNCERTAIN` | 6 |

## Kiểm tra và provenance

- Exact-text validator: **PASS** trên 10 nguồn đối chiếu trong repo (bao gồm `router_holdout.jsonl`, `router_holdout_independent_v1.jsonl`, `router_holdout_week10_v1`–`v5`, `queries_dev.json`, `dev_negative_queries_v2.jsonl`, `test_rule_router.py`).
- SHA-256 JSONL (LF): `c1db665fd29e75ec6ef287642e5391a8401ef9167991e442c552f330f3a5127c`.
- Lần chạy: UTC `2026-11-17T13:49:31.520502+00:00`; classifier `rule_router_v5`.
- SHA-256 source `agent/router/rule_router.py`: `996bd6a0894aeaf964f188f032961329ec6cdecfe1575bcf80df685aa068f2f7` (LF; raw Windows CRLF checkout bytes tại lúc chạy: `c65025165323212e0e13aa050342a3613dd8b27fbdd4688ae44cb1f886432a43`).

## Kết quả chạy một lần

- Exact route/action: **34/36 (94.4%)** (`10/10` `LEGAL_HNGD`, `7/8` `LEGAL_OUT_OF_SCOPE`, `6/6` `MIXED_LEGAL_SCOPE`, `5/6` `NON_LEGAL`, `6/6` `LEGAL_SCOPE_UNCERTAIN`).
- Mismatch (`2` câu): `W16RH_012` (`LEGAL_OUT_OF_SCOPE` -> `LEGAL_SCOPE_UNCERTAIN / LEGAL_RETRIEVAL`), `W16RH_029` (`NON_LEGAL` -> `LEGAL_SCOPE_UNCERTAIN / LEGAL_RETRIEVAL`).
- Safety: **0** câu pháp lý bị chuyển thành `NON_LEGAL / GENERAL_CHAT` (Safety gate PASS).
- Các gate nền (`--skip-holdout`): Official Dev Gold `30/30` PASS, Dev benchmark `270/270` PASS, Negative Set v2 `26/26` PASS, non-legal `6/6` PASS, legal-to-chat `0` PASS.
- `rule_router_v5` không bị chỉnh sửa sau khi chạy `v6`.
