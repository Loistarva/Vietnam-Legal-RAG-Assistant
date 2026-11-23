# D4.2 — Đồng bộ review và nghiệm thu holdout v6

Cập nhật hồ sơ: **23/11/2026**. **V6 là bản chốt holdout độc lập chính thức theo quyết định nghiệm thu của project owner**, sau xác nhận Dev3 đã review nhãn. Chốt kết quả **34/36 (94,44%)**, legal → non-legal **0/30**. Không sửa Router, câu hỏi, nhãn hoặc chạy lại prediction trong lần đồng bộ này.

## Đầu vào, đầu ra và công nghệ

- Đầu vào: [JSONL v6](router_holdout_week10_v6.jsonl), [metadata v6](router_holdout_week10_v6.md), [kết quả lịch sử Week 10](../../reports/week10/router_holdout_report.md), source Router v5 tại `4895649`, validator và 10 nguồn đối chiếu.
- Đầu ra: metadata review đồng bộ cho 36 bản ghi, bảng truy vết SHA/thời điểm, quyết định chốt holdout chính thức, ma trận nhầm lẫn và kết luận nghiệm thu trong tài liệu này. Giữ đường dẫn v6 gốc, không tạo JSONL Sprint 11 hoặc bản dự đoán mới.
- Công nghệ: Python/JSONL, Unicode NFC và chuẩn hóa khoảng trắng, đối chiếu exact-text, Git và SHA-256. Không dùng model, Ollama hoặc API.

## Review nhãn và dấu thời gian

| Trường ở từng record | Giá trị | Ý nghĩa |
|---|---|---|
| `reviewer_id` | `Dev3` | Reviewer theo xác nhận của project owner |
| `reviewer_status` | `INDEPENDENT_REVIEW_COMPLETE` | Đã ghi nhận review nhãn |
| `approval_status` | `APPROVED` | Đã ghi nhận chấp thuận nhãn |
| `review_date` | `null` | Chưa được cung cấp ngày thực hiện review |
| `review_confirmation_recorded_at` | `2026-11-23` | Ngày đồng bộ xác nhận vào repo, không phải ngày review |
| `review_confirmation_source` | `project_owner_confirmation` | Nguồn xác nhận là phiên làm việc với project owner |
| `review_before_prediction` | `null` | Chưa chứng minh review diễn ra trước prediction |
| `usage_status` | `CONSUMED` | Bộ đã chạy, không phải holdout chưa mở |

Các trường ngày review chưa được cung cấp vẫn giữ `null`. Quyết định chốt bản chính thức được ghi ngày 23/11/2026, không hồi tố thành ngày review hoặc ngày freeze gốc.

| Mốc | Bằng chứng | Giới hạn |
|---|---|---|
| Review Dev3 | Project owner đã xác nhận | Chưa có ngày/link review gốc; chưa chứng minh thứ tự với run |
| Run v6 | Báo cáo ghi UTC `2026-11-17T13:49:31.520502+00:00` | Giữ kết quả gốc; chưa có prediction JSONL đầy đủ trong hồ sơ này |
| Commit chứa source và kết quả | `48956492b63238b4d1df323cad06d8547e1cc4b7`; commit time `2026-11-17T20:56:36+07:00` | Commit sau mốc run khoảng 7 phút; không dùng commit time làm bằng chứng freeze trước run |
| Snapshot bàn giao hiện tại | `d76244d8b454aedec7518bd37fecda3d419790cc`; [hồ sơ D4.1](../../docs/router_freeze.md) | Chỉ refactor boundary/explanation/config; không phải snapshot đã chạy v6 |
| Đồng bộ hồ sơ | `2026-11-23` | Không hồi tố ngày review/sign-off |

Dev3 và Tech Lead sign-off Router v5 đã được project owner xác nhận ở D4.1. Project owner chấp thuận hồ sơ v6 hiện có để chốt D4.2; các thông tin thời điểm chưa có bằng chứng vẫn giữ nguyên trạng thái chưa xác định. Không gán Git HEAD hoặc config SHA của run gốc từ snapshot hiện tại.

## SHA và bảo toàn dữ liệu

| Đối tượng | SHA-256 |
|---|---|
| JSONL v6 tại run gốc, LF | `c1db665fd29e75ec6ef287642e5391a8401ef9167991e442c552f330f3a5127c` |
| JSONL v6 sau cập nhật metadata, LF | `b9eeb081552b0eaf87326fd86f9426818aee615c8e70b5fd96857c8effd670b8` |
| Nội dung cốt lõi trước/sau cập nhật | `88ba5571cbfd2bda5d1a926a6da4df4ea98b7d74df209230ecf90f1a21a91fe4` |
| Router v5 của kết quả gốc, LF | `996bd6a0894aeaf964f188f032961329ec6cdecfe1575bcf80df685aa068f2f7` |
| Router v5 bàn giao hiện tại, LF | `081152e3e71795454b702c57092987703bd281f943cdfc3b740076a393780067` |
| Snapshot source/config bàn giao tổng hợp | `14acb337f0d8af87ba746418c435d8e8569e569b95bdce4888d57841eb290c8a` |

Hash LF đổi CRLF thành LF trước khi băm bytes. Hash nội dung cốt lõi chọn `id`, `query`, `expected_route`, `expected_action`, `category`, `reason`, giữ thứ tự 36 dòng; serialize cả array bằng `ensure_ascii=False`, `sort_keys=True`, `separators=(',', ':')`, thêm một LF cuối rồi băm UTF-8. Nội dung 36 bản ghi này giống hệt trước/sau đồng bộ. SHA file đổi do metadata, không phải do sửa nhãn. Giữ nguyên SHA input lịch sử, không thay bằng SHA sau cập nhật trong kết quả run cũ.

## Quyết định chốt holdout chính thức

Ngày 23/11/2026, project owner yêu cầu bỏ phần nhận xét semantic audit và chấp thuận v6 làm holdout độc lập chính thức. Ghi nhận quyết định **ACCEPTED_OFFICIAL_HOLDOUT**; D4.2 được chốt theo quyết định nghiệm thu này. Các nhận xét audit trước đó không còn được dùng làm blocker nghiệm thu.

Đây là chấp thuận của project owner đối với hồ sơ và kết quả hiện có, không phải xác minh mới rằng zero semantic overlap hoặc thứ tự review/freeze/prediction đã được chứng minh đầy đủ. Không thay nhãn, thời điểm, SHA hoặc tạo thêm kết quả chạy để diễn giải quyết định này.

Exact-text validator: PASS, 36/36 bản ghi hợp lệ, đủ 5 route, mapping route/action đúng và 0 câu trùng chính xác trên 10 nguồn: `test/agent/data/router_holdout.jsonl`, `test/agent/data/router_holdout_independent_v1.jsonl`, Week 10 holdout v1–v5, `data/benchmark/queries_dev.json`, Negative Set v2 và `test/agent/test_rule_router.py`.

## Kết quả lịch sử và mẫu số

Ma trận sau tổng hợp từ phân bố 36 nhãn và hai mismatch đã ghi trong báo cáo gốc; không phải output của một lần chạy mới, không thay thế prediction JSONL nguyên bản.

| Nhãn đúng \ Dự đoán | HNGĐ | Ngoài phạm vi | Mixed | Non-legal | Chưa rõ phạm vi | Tổng |
|---|---:|---:|---:|---:|---:|---:|
| `LEGAL_HNGD` | 10 | 0 | 0 | 0 | 0 | 10 |
| `LEGAL_OUT_OF_SCOPE` | 0 | 7 | 0 | 0 | 1 | 8 |
| `MIXED_LEGAL_SCOPE` | 0 | 0 | 6 | 0 | 0 | 6 |
| `NON_LEGAL` | 0 | 0 | 0 | 5 | 1 | 6 |
| `LEGAL_SCOPE_UNCERTAIN` | 0 | 0 | 0 | 0 | 6 | 6 |
| Tổng | 10 | 7 | 6 | 5 | 8 | 36 |

| Chỉ số | Kết quả | Phạm vi |
|---|---|---|
| Exact route/action | 34/36 = 94,44% | Toàn bộ 36 câu |
| Legal → NON_LEGAL/GENERAL_CHAT | 0/30 = 0% | 30 câu có nhãn khác NON_LEGAL, gồm cả uncertain |
| Legal được giữ ở các route pháp lý | 30/30 = 100% | Chỉ đo không bị chuyển thành chat, không đồng nghĩa đúng domain |
| Non-legal được nhận đúng | 5/6 = 83,33% | 6 câu NON_LEGAL |
| Out-of-scope đi POLICY_ABSTENTION | 7/8 = 87,50% | 8 câu LEGAL_OUT_OF_SCOPE |
| Mixed đi POLICY_ABSTENTION | 6/6 = 100% | 6 câu MIXED_LEGAL_SCOPE |

Mismatch giữ nguyên: `W16RH_012` có nhãn OUT_OF_SCOPE/POLICY_ABSTENTION nhưng dự đoán UNCERTAIN/LEGAL_RETRIEVAL; `W16RH_029` có nhãn NON_LEGAL/GENERAL_CHAT nhưng dự đoán UNCERTAIN/LEGAL_RETRIEVAL. Không có legal → chat, nhưng vẫn có lỗi đưa ngoài phạm vi vào retrieval.

Ngưỡng classifier cho independent holdout trong smoke hiện tại là 90%; số liệu lịch sử 94,44% vượt ngưỡng này và safety 0/30 đạt. V6 được giữ là bản chính thức đã chốt; các lần chạy lại nếu có chỉ phục vụ regression, không thay kết quả chính thức.

## Kết luận nghiệm thu

| Điều kiện D4.2 | Trạng thái |
|---|---|
| 30–40 case hợp lệ, đủ route/action | Đạt: 36 case |
| Reviewer identity và approval cho từng record | Đã đồng bộ Dev3 cho 36/36, theo project owner |
| Ngày review và bằng chứng review trước prediction | Giữ thông tin chưa xác định; project owner chấp thuận hồ sơ hiện có |
| Exact duplicate audit | Đạt trên 10 nguồn |
| Chấp thuận phạm vi độc lập của v6 | Project owner chấp thuận bản chính thức; không ghi thành xác minh mới về zero semantic overlap |
| Source SHA gắn kết quả | Có SHA lịch sử, tái lập khớp source tại `4895649` |
| Snapshot freeze/config gốc trước prediction | Giữ provenance gốc hiện có; không thay bằng snapshot bàn giao mới |
| Confusion matrix và safety có denominator | Đã bổ sung từ báo cáo lịch sử |
| Chốt D4.2 independent holdout | **ACCEPTED_OFFICIAL_HOLDOUT**, theo quyết định project owner ngày 23/11/2026 |

Lệnh kiểm tra cấu trúc và exact-text, không gọi Router dự đoán:

```powershell
.\.venv\Scripts\python.exe scripts/validate_router_holdout.py --holdout evaluation/router_holdout/router_holdout_week10_v6.jsonl
```
