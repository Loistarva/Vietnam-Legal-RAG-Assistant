# Báo cáo Tuần 7 — Retrieval trên Test

**Ngày chạy:** 26/10/2026  
**Query:** `data/benchmark/queries_test.json` (15 câu; nội dung giống `queries_test_revised.json`)  
**Nhãn:** `data/benchmark/gold_id_proposals_300_test_revised.json`  
**Chi tiết và giới hạn:** [`retrieval/results/test_run/test_report.md`](../retrieval/results/test_run/test_report.md)

**Lưu ý:** báo cáo giữ cả lượt đầu Config A và lượt đánh giá lại sau khi khóa cấu hình E. Lượt E không dùng để tune; do cùng Test đã được xem ở lượt A, đây không phải một phép đo độc lập mới.

## Kết quả lượt đầu — Config A, Top-5

| Phương pháp | Recall@5 | MRR@5 |
| --- | ---: | ---: |
| BM25-only | 0,3111 | 0,1433 |
| Hybrid RRF, `k=60` | 0,2889 | 0,2500 |
| Hybrid + Cross-Encoder thật `BAAI/bge-reranker-v2-m3` | 0,5778 | 0,4556 |

Cả 15 câu đều có `gold_context_ids` là chunk ID trong corpus Config A. Nhãn là proposal chưa được xác minh đầy đủ. Recall@5 của Cross-Encoder là 57,78%, chưa đạt mục tiêu 85%.

## Đánh giá lại sau khi khóa cấu hình E

| Phương pháp | Recall@5 | MRR@5 | Latency mean / median / p95 (ms) |
| --- | ---: | ---: | ---: |
| BM25-only | 0,3111 | 0,1433 | 511,4 / 392,5 / 1.006,9 |
| Hybrid RRF 0,35/0,65 | 0,4222 | 0,3300 | 1.677,7 / 891,3 / 8.497,3 |
| Hybrid + Cross-Encoder thật | **0,6444** | **0,5222** | 52.904,0 / 48.686,8 / 83.839,5 |

- Corpus/index: Config E, 1.923 chunks; Elasticsearch `legal-child-chunks-dev-cfge`; Qdrant `vietnam_legal_dev_cfge`.
- Dense model: `bkai-foundation-models/vietnamese-bi-encoder`; RRF `k=60`, Top-50, BM25/Dense `0,35/0,65`.
- Cross-Encoder: `BAAI/bge-reranker-v2-m3`, CPU, rerank Top-10; metric tính trên Top-5.
- Hoàn tất 15/15 query, không có lỗi truy xuất hoặc rerank.
- Latency BM25 đo riêng Top-5; Hybrid gồm BM25 + Dense song song và RRF; Hybrid + Cross-Encoder gồm cả truy xuất lẫn rerank. Trung bình/p95 gồm cold start; Cross-Encoder nạp model mất khoảng 17,9 giây ở query đầu.
- HN_040 và HN_056 có một nhãn được chuyển từ chunk gốc sang chunk E theo text-span trong cùng `clause_id`. Chi tiết ánh xạ được lưu trong JSON metric; file proposal gốc không sửa.
- Recall@5 64,44% chưa đạt mục tiêu 85%. Không có tham số nào được tune trên kết quả Test.
- `as_of_date` từng query chưa được truyền vào Hybrid retrieval; bộ lọc `Hết hiệu lực` dùng trạng thái hiện tại. Đây chưa phải phép đo toàn bộ temporal pre-filter của sơ đồ.

Kết quả chi tiết Config E: [`test_config_e_report.md`](../retrieval/results/test_run/config_e_final/test_config_e_report.md), metric và ánh xạ nhãn: [`test_config_e_metrics.json`](../retrieval/results/test_run/config_e_final/test_config_e_metrics.json), kết quả Top-50/Top-10: [`test_config_e_rankings.json`](../retrieval/results/test_run/config_e_final/test_config_e_rankings.json).

## Cấu hình Cross-Encoder ở lượt Config A

- Dense: `bkai-foundation-models/vietnamese-bi-encoder`; BM25 index: `legal-child-chunks-current`; Qdrant: `vietnam_legal_chunks_current`.
- Hybrid dùng RRF `k=60`, lấy Top-50 candidate; reranker chấm 50 candidate, trả Top-5.
- Model: `BAAI/bge-reranker-v2-m3`, `batch_size=16`, `max_length=512`, đầu vào `chunk_text`, thiết bị CPU.
- Các tham số giữ nguyên trong lượt Test; không dùng Test để tune.

## Tệp kết quả

- Raw output Cross-Encoder: [`hybrid_reranker_cross_encoder.json`](../retrieval/results/test_run/hybrid_reranker_cross_encoder.json)
- ID đầu ra cho evaluation: [`hybrid_reranker_cross_encoder_eval.json`](../retrieval/results/test_run/hybrid_reranker_cross_encoder_eval.json)
- Metric tổng hợp và theo query: [`test_proposal_metrics_top5_revised.json`](../retrieval/results/test_run/test_proposal_metrics_top5_revised.json), [`hybrid_reranker_cross_encoder_metrics.json`](../retrieval/results/test_run/hybrid_reranker_cross_encoder_metrics.json)

Lượt Config A trước đó chạy đủ 15 query, mỗi query chấm 50 candidate, không lỗi. Lượt Config E cũng chạy đủ 15 query bằng Cross-Encoder thật trên CPU. Cả hai lượt chưa áp dụng temporal pre-filter theo `as_of_date`, nên không đại diện đầy đủ pipeline production.
