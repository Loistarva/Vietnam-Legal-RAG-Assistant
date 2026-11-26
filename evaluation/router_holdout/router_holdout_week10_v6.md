# Router Week 10 Holdout v6

## Trạng thái

- **Bản chốt holdout độc lập chính thức: v6**, được project owner chấp thuận ngày 23/11/2026 sau xác nhận Dev3 đã review. Đây là quyết định nghiệm thu của project owner, không phải một lần kiểm chứng thực nghiệm bổ sung.

- 36 câu, ID `W16RH_001`–`W16RH_036`, đã dùng để đánh giá một lần trên `rule_router_v5`. Không tiếp tục gọi là bộ câu hỏi mới chưa tiêu thụ.
- Dev3 đã review nhãn theo xác nhận của project owner. Đồng bộ ngày 23/11/2026: 36/36 bản ghi có `reviewer_id=Dev3`, `reviewer_status=INDEPENDENT_REVIEW_COMPLETE`, `approval_status=APPROVED`.
- `review_date=null` và `review_before_prediction=null`: chưa có ngày review thực tế hoặc bằng chứng review trước lần chạy. `review_confirmation_recorded_at=2026-11-23` là ngày ghi nhận vào metadata, không phải ngày Dev3 thực hiện review.
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
- SHA-256 JSONL (LF) **tại lần chạy gốc**, trước cập nhật metadata: `c1db665fd29e75ec6ef287642e5391a8401ef9167991e442c552f330f3a5127c`.
- SHA-256 JSONL (LF) **sau đồng bộ review**: `b9eeb081552b0eaf87326fd86f9426818aee615c8e70b5fd96857c8effd670b8`. SHA đổi do metadata; 36 câu hỏi, nhãn, category và reason giữ nguyên.
- SHA-256 nội dung cốt lõi: `88ba5571cbfd2bda5d1a926a6da4df4ea98b7d74df209230ecf90f1a21a91fe4`. Chọn `id/query/expected_route/expected_action/category/reason`, giữ thứ tự 36 dòng; serialize cả array với `ensure_ascii=False`, `sort_keys=True`, `separators=(',', ':')`, thêm LF cuối rồi băm UTF-8. Hash này giống nhau trước/sau cập nhật.
- Lần chạy: UTC `2026-11-17T13:49:31.520502+00:00`; classifier `rule_router_v5`.
- SHA-256 source `agent/router/rule_router.py`: `996bd6a0894aeaf964f188f032961329ec6cdecfe1575bcf80df685aa068f2f7` (LF; raw Windows CRLF checkout bytes tại lúc chạy: `c65025165323212e0e13aa050342a3613dd8b27fbdd4688ae44cb1f886432a43`).
- Source tại commit `48956492b63238b4d1df323cad06d8547e1cc4b7` tái lập đúng SHA LF trên. Chưa có Git HEAD/ảnh chụp toàn bộ config và dấu thời gian sign-off gốc trong hồ sơ v6 để chứng minh đầy đủ thứ tự freeze → review → prediction.

## Kết quả chạy một lần

- Exact route/action: **34/36 (94.4%)** (`10/10` `LEGAL_HNGD`, `7/8` `LEGAL_OUT_OF_SCOPE`, `6/6` `MIXED_LEGAL_SCOPE`, `5/6` `NON_LEGAL`, `6/6` `LEGAL_SCOPE_UNCERTAIN`).
- Mismatch (`2` câu): `W16RH_012` (`LEGAL_OUT_OF_SCOPE` -> `LEGAL_SCOPE_UNCERTAIN / LEGAL_RETRIEVAL`), `W16RH_029` (`NON_LEGAL` -> `LEGAL_SCOPE_UNCERTAIN / LEGAL_RETRIEVAL`).
- Safety: **0** câu pháp lý bị chuyển thành `NON_LEGAL / GENERAL_CHAT` (Safety gate PASS).
- Các gate nền (`--skip-holdout`): Official Dev Gold `30/30` PASS, Dev benchmark `270/270` PASS, Negative Set v2 `26/26` PASS, non-legal `6/6` PASS, legal-to-chat `0` PASS.
- Ngày 23/11/2026 có refactor explanation/adapter/cấu hình xã giao, không đổi luật phân loại. Snapshot bàn giao mới là `d76244d8`, source LF SHA `081152e3e71795454b702c57092987703bd281f943cdfc3b740076a393780067`; không gán kết quả v6 lịch sử cho SHA mới này.

## Chốt holdout chính thức cho Sprint 11

Theo quyết định của project owner ngày 23/11/2026, chấp thuận v6 làm holdout độc lập chính thức và chốt kết quả **34/36 (94,44%)**, safety **0/30** legal → non-legal. Các nhận xét audit trước đó không còn được dùng làm blocker nghiệm thu D4.2 theo quyết định này; việc chấp thuận không bổ sung bằng chứng về zero semantic overlap hoặc các mốc thời gian chưa được ghi nhận.

Giữ nguyên dữ liệu, kết quả, ngày chạy và SHA lịch sử; không chạy lại hoặc tinh chỉnh theo v6. Trạng thái `CONSUMED` biểu thị bộ đã được đánh giá, không làm mất trạng thái bản chính thức đã chốt. Báo cáo nghiệm thu, ma trận nhầm lẫn và các mẫu số nằm tại [báo cáo D4.2 Sprint 11](router_holdout_report.md).
