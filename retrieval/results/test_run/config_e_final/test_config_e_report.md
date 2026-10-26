# Đánh giá Test — cấu hình E đã khóa

- Ngày chạy: 2026-10-26
- Queries: `data\benchmark\queries_test.json` (15 câu)
- Nhãn: `data\benchmark\gold_id_proposals_300_test_revised.json`; ánh xạ nhãn sang chunk E bằng cùng ID hoặc text-span liên tiếp trong cùng clause.
- Corpus: E, 1923 chunks; Elasticsearch `legal-child-chunks-dev-cfge`; Qdrant `vietnam_legal_dev_cfge`.
- Dense: `bkai-foundation-models/vietnamese-bi-encoder`; RRF Top-50, k=60, BM25/Dense=0.35/0.65.
- Reranker thật: `BAAI/bge-reranker-v2-m3`; Top-10 đầu ra, chấm tối đa 50 ứng viên.
- Metric lấy đúng Top-5; không dùng Test để điều chỉnh tham số.
- **Lưu ý:** cùng tập Test đã được xem ở lượt Config A; đây là đánh giá lại Config E, không phải Test độc lập mới.
- Hoàn tất 15/15 query, không có lỗi truy xuất hoặc rerank.

| Phương pháp | Recall@5 | MRR@5 | Latency mean / median / p95 (ms) |
| --- | ---: | ---: | ---: |
| BM25-only | 0.3111 | 0.1433 | 511.4 / 392.5 / 1006.9 |
| Hybrid RRF | 0.4222 | 0.3300 | 1677.7 / 891.3 / 8497.3 |
| Hybrid + Cross-Encoder thật | 0.6444 | 0.5222 | 52904.0 / 48686.8 / 83839.5 |

Latency BM25 đo riêng cho truy vấn Top-5; Hybrid gồm BM25 + Dense song song lấy Top-50 và RRF; Hybrid + Cross-Encoder là tổng Hybrid và rerank. Mean/p95 có tính cold start: Dense query encoder ở lần đầu và Cross-Encoder nạp model khoảng 17,9 giây một lần.

## Giới hạn diễn giải

Hybrid hiện chưa truyền `as_of_date` từ từng query vào hai nhánh truy xuất; bộ lọc `Hết hiệu lực` dùng trạng thái hiện tại. Kết quả vì vậy đánh giá ranking trên cấu hình E đang chạy, chưa xác nhận đầy đủ Metadata & Temporal Pre-filter theo sơ đồ.
Nhãn proposal còn provisional. Hai nhãn chunk từ corpus gốc có thay đổi ranh giới ở E được ánh xạ bằng text-span trong cùng clause; mapping chi tiết nằm trong JSON metric.

## Tệp kết quả

- Metric và kết quả theo query: `retrieval\results\test_run\config_e_final\test_config_e_metrics.json`
- Top-50 BM25/Dense/RRF và Top-10 rerank: `retrieval\results\test_run\config_e_final\test_config_e_rankings.json`
