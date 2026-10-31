# Nguồn và trạng thái nhãn benchmark Retrieval

## Snapshot được kiểm tra

Ngày kiểm tra: 2026-10-30. Các SHA-256 dưới đây nhận diện đúng các tệp trong workspace ở thời điểm rà soát; chúng không thay cho số phiên bản phát hành do nhóm phê duyệt.

| Thành phần | Tệp | Số bản ghi / mục | SHA-256 |
| --- | --- | ---: | --- |
| Query Dev | `data/benchmark/queries_dev.json` | 285 | `b79729c6687a04323ae77fc6372498f649af8ddba7f9d4562d6fae4d1caff69e` |
| Query Test | `data/benchmark/queries_test.json` | 15 | `c31bee109002c3ab88c9255d5c511efecef2d39f217903dda6e568fc70884314` |
| Nhãn và proposal | `data/benchmark/ground_truth.json` | 300 | `564398e9beb6b16adeefb1505645d750a538e2bb66b0ba80e58c9f77ecff8991` |
| Corpus ChildChunk | `data/chunking_output/chunks.jsonl` | 2.164 chunk ID duy nhất | `9a72a35e532f03447b348afe11e4d718ba7f3697f8f6b4d2108f1d28747c01bb` |
| ParentChunk | `data/chunking_output/parents.json` | file quan hệ cha-con | `cface5a462bfffea1231d71e98854275fc0941c6c074fd5c0eefd62ce01e02e8` |

Query Dev và Test dùng ID `HN_001`–`HN_300`, không trùng ID và có `as_of_date`. Trong `ground_truth.json`, cả 300 bản ghi đang ở `review_status=draft`; `verified_by` và `verified_at` đều trống, `gold_context_ids_confirmed` đều là `false`, và tổng số `gold_context_ids` đã xác nhận bằng 0. Vì vậy, hiện chưa có gold chunk được chuyên gia xác nhận.

Các `candidate_context_ids` là proposal, không phải ground truth: 276 câu có proposal, tổng cộng 770 ID (562 ID duy nhất); 24 câu chưa có proposal. Tại snapshot này, cả 770 ID proposal đều tồn tại trong corpus hiện tại. Điều đó xác nhận tính toàn vẹn ID, không xác nhận tính liên quan hoặc tính đúng pháp lý. `gold_article_ids`, câu trả lời và giải thích cũng chưa được thẩm định; `evidence_level` của các hàng được đánh dấu unverified.

## Cách dùng nhãn

- Báo cáo Recall/MRR dựa trên `candidate_context_ids` chỉ được ghi là **phép đo exploratory theo proposal**. Không gọi là benchmark gold, ground truth hoặc kết quả chất lượng pháp lý đã xác nhận.
- Không gộp `candidate_context_ids` vào `gold_context_ids` để làm đẹp metric. Không chuyển `review_status`, `verified_by`, `verified_at` hoặc `gold_context_ids_confirmed` nếu chưa có quy trình duyệt và bằng chứng tương ứng.
- Query không có proposal phải được thống kê riêng; không tự coi là query không có tài liệu liên quan.
- Khi có nhãn được duyệt, lưu phiên bản dataset mới cùng người duyệt, ngày duyệt, phương pháp gán nhãn, đơn vị liên quan (ChildChunk/Điều/Văn bản), quy tắc ánh xạ và SHA-256 corpus.

## Trạng thái benchmark và giới hạn tái lập

Không tạo kết quả G3 mới trong lượt kiểm tra 2026-10-30: Elasticsearch tại `localhost:9200` không xác minh được kết nối và mapping BM25 hiện tại không có `_meta` tokenizer/corpus provenance; Qdrant storage theo shared config chưa tồn tại. Cần dựng/rebuild index đúng config trước khi chạy. Các metric trong `docs/retrieval_report.md` là kết quả lịch sử trên corpus/index/config cũ, không đại diện cho corpus hiện tại 2.164 chunk hay model BGE-M3 1024 chiều.

Sau khi index sẵn sàng, có thể chạy Dev để chẩn đoán hệ thống bằng proposal, nhưng báo cáo vẫn phải ghi rõ nhãn exploratory. Chỉ gọi là đánh giá độc lập có gold khi nhãn liên quan được duyệt; nếu chạy Test trên proposal thì không dùng điểm đó để tuyên bố Recall/MRR đạt chuẩn kiểm thử độc lập.
