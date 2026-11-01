# Nguồn và trạng thái nhãn benchmark Retrieval

## Trạng thái nhãn hiện tại

| Thành phần | Tệp | Số bản ghi | Trạng thái |
| --- | --- | ---: | --- |
| Query Dev | `data/benchmark/queries_dev.json` | 270 | 75 câu có Gold đã duyệt, 195 câu draft |
| Query Test | `data/benchmark/queries_test.json` | 30 | 30 câu có Gold đã duyệt; câu hỏi và đáp án đã khóa |
| Nhãn | `data/benchmark/ground_truth.json` | 300 | 105 `source_checked`, 195 `draft` |
| Corpus ChildChunk | `data/chunking_output/chunks.jsonl` | 2.164 chunk | Mọi ID Gold và proposal đều có trong corpus |

Query dùng ID `HN_001`–`HN_300`, không trùng ID và đều có `as_of_date`. 105 câu Gold đã duyệt có `review_status = "source_checked"`, `gold_context_ids_confirmed = true`, `verified_by` và `verified_at`, tổng cộng 250 `gold_context_ids`. Quy tắc gán nhãn, người duyệt và cách chia Dev/Test xem [sprint6_benchmark.md](sprint6_benchmark.md).

195 câu Dev còn lại ở `draft`: `gold_context_ids` rỗng, `gold_context_ids_confirmed = false`. `candidate_context_ids` (213 câu, 541 ID, 434 ID duy nhất) là proposal, không phải ground truth.

Test được khóa bằng hai manifest: `docs/test_questions_freeze.json` (câu hỏi) và `docs/test_gold_freeze.json` (câu hỏi và đáp án). Kiểm tra bằng `python scripts/freeze_test.py --verify` và `python scripts/freeze_gold.py --verify`.

## Cách dùng nhãn

- Metric chính tính trên `gold_context_ids` của các câu `source_checked`. Chọn tham số (model Dense, `rrf_k`, `rerank_top_k`) chỉ trên 75 câu Dev đã duyệt; Test chỉ chạy một lần với cấu hình đã khóa.
- Metric tính trên `candidate_context_ids` chỉ là **phép đo thăm dò theo proposal** và phải ghi rõ như vậy; không gọi là kết quả trên Gold.
- Không gộp `candidate_context_ids` vào `gold_context_ids` và không đổi `review_status`, `verified_by`, `verified_at`, `gold_context_ids_confirmed` khi chưa có người duyệt.
- Câu không có proposal phải được thống kê riêng, không coi là câu không có tài liệu liên quan.

## Kết quả cũ

Các metric trong [retrieval_report.md](retrieval_report.md) là kết quả lịch sử trên corpus 1.159/1.175 chunk, model BKAI 768 chiều và nhãn proposal; không dùng làm kết quả cho corpus 2.164 chunk và BGE-M3 hiện tại. Chưa có số đo mới (G3).

## Ghi chú về SHA-256 corpus

Index BM25 và Qdrant lưu SHA-256 của các byte trong `chunks.jsonl` khi dựng; runner và evaluator từ chối index dựng từ corpus khác. Với `core.autocrlf=true` trên Windows, file được checkout với CRLF nên hash khác bản LF trên Linux/macOS. Vì vậy mỗi máy phải tự dựng index từ chính checkout của mình, không chép index giữa các máy có cấu hình line ending khác nhau.
