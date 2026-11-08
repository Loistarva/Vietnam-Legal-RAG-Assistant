# Nguồn và trạng thái nhãn benchmark Retrieval

## Trạng thái nhãn hiện tại

| Thành phần | Tệp | Số bản ghi | Trạng thái |
| --- | --- | ---: | --- |
| Query Dev | `data/benchmark/queries_dev.json` | 270 | 75 câu có Gold đã duyệt, 195 câu draft |
| Query Test | `data/benchmark/queries_test.json` | 30 | 30 câu có Gold đã duyệt; câu hỏi và đáp án đã khóa |
| Nhãn | `data/benchmark/ground_truth.json` | 300 | 105 `source_checked`, 195 `draft` |
| Corpus ChildChunk | `data/chunking_output/chunks.jsonl` | 2.322 chunk | Mọi ID Gold và candidate đều có trong corpus |

Query dùng ID `HN_001`–`HN_300`, không trùng ID và đều có `as_of_date`. 105 câu Gold đã duyệt có `review_status = "source_checked"`, `gold_context_ids_confirmed = true`, `verified_by` và `verified_at`, tổng cộng 250 `gold_context_ids`. Quy tắc gán nhãn, người duyệt và cách chia Dev/Test xem [sprint6_benchmark.md](sprint6_benchmark.md).

195 câu Dev còn lại ở `draft`: `gold_context_ids` rỗng, `gold_context_ids_confirmed = false`, `verified_by` và `verified_at` trống. Evaluator (`retrieval/retrieval_evaluation.py`, `evaluation/metrics.py`) và `scripts/check_split.py` chỉ chấm câu có `gold_context_ids_confirmed = true`, nên số đo Dev vẫn tính trên 75 câu.

## Mapping context của các câu draft (PR #25)

PR #25 ghép các câu draft với chunk trong corpus: 176 câu dẫn toàn Điều, HN_053 dẫn Điều 109 Luật 22/2000/QH10, 12 câu hiệu lực dẫn điều khoản bãi bỏ, thay thế hoặc ngày hiệu lực, và 6 câu từng dùng ID giả. Mapping lấy đủ child chunk của Điều được dẫn, kể cả chunk nối tiếp. Các mapping này nằm ở `candidate_context_ids` với `mapping_status = "production_candidate_unverified"` và `evidence_level = "chunk_text_matched_unverified"`: chỉ xác nhận ID có trong corpus và khớp Điều được dẫn, chưa xác nhận đáp án đủ, dẫn chiếu sang Điều khác hay hiệu lực theo ngày hỏi. Danh sách mapping xem `data/benchmark/gold_context_completion_audit.json`.

Hiện có 230 câu có `candidate_context_ids` (582 ID, 458 ID duy nhất), trong đó 193 câu draft. Khi duyệt một câu, người duyệt chuyển candidate đúng sang `gold_context_ids`, đặt `gold_context_ids_confirmed = true` và ghi `verified_by`, `verified_at`. Mapping toàn Điều có thể nhiều chunk hơn `top_k` (HN_063 có 25 chunk), cần thu hẹp về Khoản khi duyệt.

Sáu câu từng dùng ID giả:

- HN_046, HN_050, HN_058 dùng Khoản 3 Điều 2 và Khoản 1 Điều 4 Thông tư 04/2024/TT-BTP; HN_060 dùng Khoản 1 Điều 2 và Khoản 1 Điều 5 Nghị định 07/2025/NĐ-CP. Hai văn bản này có toàn văn trong corpus (nguồn Công báo trong `data/reference/source_pdfs.json`), nên PR không còn giữ bản trích gõ tay.
- HN_039 (Nghị định 24/2013/NĐ-CP bãi bỏ Nghị định 68/2002/NĐ-CP) và HN_048 (Thông tư 01/2018/TT-BTP bãi bỏ Thông tư 07/2002/TT-BTP) để `not_mapped`, vì hai văn bản bãi bỏ chưa có trong corpus. Đưa vào thì cần chạy cleaner, parser, exporter với `data/reference/corpus_scope.json` (chỉ Điều 45 Nghị định 24/2013, Điều 1 và Điều 3 Thông tư 01/2018) và dựng lại index. PDF Dev 1 đã tải nằm trong commit 07d365d.

Câu hiệu lực draft có thể dùng điều khoản bãi bỏ của một văn bản đã hết hiệu lực làm chứng cứ (ví dụ HN_040, Điều 31 Thông tư 15/2015/TT-BTP bãi bỏ Thông tư 02a/2015/TT-BTP). `scripts/validate_benchmark.py` (`supports_historical_repeal`) chỉ chấp nhận khi đoạn trích có "bãi bỏ", nêu số hiệu văn bản bị bãi bỏ và ngày hiệu lực khớp ngày hết hiệu lực; với câu draft, chứng cứ đọc từ `candidate_context_ids`.

Việc còn lại cho người duyệt: 26 câu draft (HN_209–HN_239, HN_276, HN_277) có candidate là Điều 20–50 Nghị định 126/2014/NĐ-CP, hết hiệu lực từ 01/01/2016, trong khi `as_of_date` là 2026-10-15. Khi duyệt phải đổi sang quy định còn hiệu lực hoặc đổi `as_of_date`/`test_type`; nếu giữ nguyên, bộ lọc thời gian của Retrieval sẽ loại các chunk này.

Test được khóa bằng hai manifest: `docs/test_questions_freeze.json` (câu hỏi) và `docs/test_gold_freeze.json` (câu hỏi và đáp án). Kiểm tra bằng `python scripts/freeze_test.py --verify` và `python scripts/freeze_gold.py --verify`. PR #25 không đổi câu Test; 20 câu draft Dev được viết lại để không trùng Khoản gold của Test.

## Cách dùng nhãn

- Metric chính tính trên `gold_context_ids` của các câu `source_checked`. Chọn tham số (model Dense, `rrf_k`, `rerank_top_k`) chỉ trên 75 câu Dev đã duyệt; Test chỉ chạy một lần với cấu hình đã khóa.
- Metric tính trên `candidate_context_ids` chỉ là **phép đo thăm dò theo proposal** và phải ghi rõ như vậy; không gọi là kết quả trên Gold.
- Không gộp `candidate_context_ids` vào `gold_context_ids` và không đổi `review_status`, `verified_by`, `verified_at`, `gold_context_ids_confirmed` khi chưa có người duyệt.
- Câu không có proposal phải được thống kê riêng, không coi là câu không có tài liệu liên quan.

## Kết quả cũ

Các metric trong [retrieval_report.md](retrieval_report.md) là kết quả lịch sử trên corpus 1.159/1.175 chunk, model BKAI 768 chiều và nhãn proposal; không dùng làm kết quả cho corpus 2.164 chunk và BGE-M3 hiện tại. Chưa có số đo mới (G3).

## Ghi chú về SHA-256 corpus

Index BM25 và Qdrant lưu SHA-256 của các byte trong `chunks.jsonl` khi dựng; runner và evaluator từ chối index dựng từ corpus khác. Với `core.autocrlf=true` trên Windows, file được checkout với CRLF nên hash khác bản LF trên Linux/macOS. Vì vậy mỗi máy phải tự dựng index từ chính checkout của mình, không chép index giữa các máy có cấu hình line ending khác nhau. Riêng `docs/test_run_config_freeze.json` chuẩn hóa CRLF thành LF trước khi băm corpus/config để xác minh nội dung Test nhất quán trên Windows và Linux; cách băm của manifest không thay đổi hash byte-level dùng để đối chiếu index.
