# Test retrieval- Dev set với chunk hiện hành và proposal 300

Ngày chạy: 2026-10-18

## Đầu vào

- Dev set: `data/benchmark/queries_dev.json` — 285 câu.
- Corpus truy xuất: `data/chunking_output/chunks.jsonl` — 1.159 Child chunks theo parser và chunking rule hiện tại.
- Nhãn tạm: `data/benchmark/gold_id_proposals_300.json`.
- Model Dense: `bkai-foundation-models/vietnamese-bi-encoder` (768 chiều).
- Top-K: 10; candidate-K: 50; RRF k: 60.
- BM25 Elasticsearch index: `task4-legal-proposal300-current`.
- Qdrant collection: `task4-bkai-proposal300-current`.

Ground truth dùng trong lần chạy được lưu tại `ground_truth_proposal_300_chunks_only.json`. Chỉ giữ ID chunk có trong corpus hiện tại; bỏ 27 ID `version_*` vì đây là metadata hiệu lực văn bản, không phải chunk có thể truy xuất. HN_271 không có gold chunk do parser Điều 8 chưa đầy đủ; chunk Điều 8 hiện tại chỉ được tính từ candidate. `ground_truth.json` chính thức không được dùng hoặc sửa.

## Chunk-level metrics

| Method | Recall@10 | MRR@10 | nDCG@10 | Precision@10 |
|---|---:|---:|---:|---:|
| BM25 | 0.6269 | 0.3703 | 0.4218 | 0.0679 |
| Dense | 0.6866 | 0.4271 | 0.4814 | 0.0731 |
| Hybrid | **0.7407** | **0.4544** | **0.5145** | **0.0802** |

268/285 câu được chấm chunk-level; 17 câu không có nhãn chunk sau khi lọc metadata-only IDs. Trong số 268 câu được chấm, 9 câu có gold chunk đã xác nhận; 259 câu dùng nhãn proposal chưa xác minh.

## Article-level metrics

| Method | Recall@10 | MRR@10 | nDCG@10 | Precision@10 |
|---|---:|---:|---:|---:|
| BM25 | 0.6648 | 0.4074 | 0.4589 | 0.0723 |
| Dense | **0.7846** | **0.5322** | **0.5843** | 0.0839 |
| Hybrid | 0.7753 | 0.5043 | 0.5612 | **0.0843** |

267/285 câu được chấm article-level; 18 câu không có nhãn Điều.

## So sánh mô hình

- **Tìm đúng chunk:** Hybrid đứng đầu cả bốn metric. So với BM25, Hybrid tăng Recall@10 **11,38 điểm phần trăm**, MRR@10 **8,41 điểm**, nDCG@10 **9,26 điểm** và Precision@10 **1,23 điểm**. So với Dense, Hybrid tăng Recall@10 **5,41 điểm**, MRR@10 **2,73 điểm**, nDCG@10 **3,31 điểm** và Precision@10 **0,71 điểm**.
- **Tìm đúng Điều:** Dense đứng đầu Recall@10, MRR@10 và nDCG@10; Hybrid chỉ nhỉnh hơn Dense ở Precision@10 **0,04 điểm phần trăm**. So với BM25, Dense tăng Recall@10 **11,99 điểm**, MRR@10 **12,48 điểm** và nDCG@10 **12,53 điểm**.
- **Kết luận:** Hybrid phù hợp nhất nếu mục tiêu là đưa đúng chunk lên Top‑10. Dense hiệu quả nhất khi đánh giá ở cấp Điều. BM25 thấp hơn hai cách còn lại trên hầu hết metric; kết hợp BM25 với Dense giúp cải thiện xếp hạng chunk.

## Giới hạn

Đây là kết quả thử nghiệm trên Dev và nhãn tạm. 259 nhãn chunk-level chưa được xác minh pháp lý nên các chỉ số tổng thể không phải kết luận chất lượng benchmark chính thức. Không dùng kết quả này để chọn cấu hình cuối cùng thay cho đánh giá độc lập trên Test.

## Tệp đầu ra

- `dev_bm25.json`, `dev_dense.json`, `dev_hybrid.json`
- `metrics.csv`, `article_metrics.csv`
- `ground_truth_proposal_300_chunks_only.json`
