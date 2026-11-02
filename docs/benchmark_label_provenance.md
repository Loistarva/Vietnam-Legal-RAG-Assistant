# Nguồn và trạng thái nhãn benchmark Retrieval

## Bổ sung mapping context từ nhánh testing

Sáu câu HN_039, HN_046, HN_048, HN_050, HN_058, HN_060 hiện được điền
`FAKE_HN_..._PENDING_EVIDENCE` theo yêu cầu để thử nghiệm, với
`gold_context_ids_confirmed=false`. Vì vậy 300 câu có mảng ID không rỗng,
nhưng chỉ 294 câu dùng ID corpus thật. Sáu placeholder không thuộc corpus,
không dùng cho metric Gold và sẽ bị validator benchmark từ chối. Fixture riêng
ở `data/benchmark/synthetic_gold_context_ids.json`. Báo cáo audit bên dưới ghi
nhận 294 mapping thật và vẫn liệt kê sáu câu này trong `pending`.

Đợt bổ sung này thêm `gold_context_ids` cho 177 câu Dev từ corpus hiện có:
176 câu đã dẫn toàn Điều và HN_053 dẫn Điều 132 Luật 52/2014/QH13.
Mapping lấy đủ các child chunk của Điều được dẫn, bao gồm chunk nối tiếp;
không chuyển nguyên danh sách proposal được xếp hạng thành Gold.

Sau khi rà lại raw data và corpus, thêm 12 câu hiệu lực bằng các điều khoản
bãi bỏ/thay thế/ngày hiệu lực đã có trong production; bổ sung citation và
`gold_article_ids` tương ứng, giữ nguyên đáp án và trạng thái duyệt.
Hiện có 294/300 câu có context mapping: Dev 264/270, Test 30/30;
tổng 793 lượt ID, 589 ID duy nhất. Sáu câu HN_039, HN_046, HN_048,
HN_050, HN_058, HN_060 còn chờ xác định chunk chứng minh đáp án.

`production_verified` và `gold_context_ids_confirmed=true` ở 189 câu mới chỉ
xác nhận ID tồn tại và khớp Điều/corpus. Các câu này vẫn `review_status=draft`,
giữ nguyên `answer_kind`, đáp án, tên/ngày người duyệt và ghi
`evidence_level=chunk_text_matched_unverified`. Chưa xác nhận tính đầy đủ của
đáp án, liên kết dẫn chiếu sang Điều khác hoặc hiệu lực pháp lý theo ngày hỏi.
Không coi 294 câu có mapping là 294 câu Gold đã được con người duyệt.

Metric dùng cho báo cáo Gold đã duyệt vẫn phải giới hạn vào 105 câu
`source_checked` (Dev 75, Test 30). Evaluator đọc mọi `gold_context_ids` không
tự bảo đảm điều kiện này; nếu dùng cả 294 câu, phải ghi rõ đây là kết quả trên
mapping mở rộng gồm 189 câu chưa duyệt. Số lượng chunk liên quan của mapping
toàn Điều có thể lớn hơn `top_k`; cần xét điều này khi diễn giải Recall@k.

Kiểm tra bằng `node scripts/complete_gold_context_ids.cjs`; xem danh sách
mapping mới và 6 câu chờ xác định chứng cứ trong
`data/benchmark/gold_context_completion_audit.json`. Manifest Test được kiểm tra
SHA-256 và không thay đổi. Script chỉ ghi dữ liệu khi có `--write`.

## Trạng thái nhãn trước đợt bổ sung mapping

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
