# Báo cáo baseline Retrieval trên Dev

**Ngày báo cáo:** 2026-11-03  
**Phạm vi:** BM25, Dense và Hybrid RRF; chỉ đánh giá truy xuất, chưa đánh giá câu trả lời sinh ra.

## Tóm tắt

| Phương pháp | Recall@5 | Parent Match@5 | MRR@5 | nDCG@5 | Recall@10 | Parent Match@10 | MRR@10 | nDCG@10 | Precision@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BM25 | 0.6010 | 0.6053 | 0.5733 | 0.5304 | 0.6736 | 0.6872 | 0.5778 | 0.5612 | 0.1480 |
| Dense | 0.6441 | 0.6663 | 0.6489 | 0.6039 | **0.7574** | **0.7751** | 0.6563 | 0.6490 | 0.1587 |
| Hybrid (BM25 + Dense, RRF) | **0.6769** | **0.6903** | **0.6938** | **0.6315** | 0.7395 | 0.7493 | **0.6973** | **0.6600** | **0.1640** |

Các metric trong bảng là trung bình macro trên 75 câu Dev đủ điều kiện. Precision@10 là số chunk gold trong Top-10 chia cho 10, lấy trực tiếp từ `average.precision@10` trong các file JSON `bm25_dev_metrics.json`, `dense_dev_metrics.json` và `hybrid_dev_metrics.json`.

| Phương pháp | Temporal Violation Rate | Vi phạm / kết quả đã kiểm tra | Thiếu metadata ngày |
| --- | ---: | ---: | ---: |
| BM25 | 0.0000 | 0 / 750 | 0 |
| Dense | 0.0000 | 0 / 750 | 0 |
| Hybrid | 0.0000 | 0 / 750 | 0 |

## Dữ liệu và cấu hình

- Bộ benchmark có 270 câu Dev. Trong đó, 75 câu có `gold_context_ids` đã xác minh được chấm; 195 câu draft được bỏ qua, không xem là câu trả lời sai. 30 câu Test đã đóng băng và không được dùng trong báo cáo này.
- Mỗi phương pháp trả 10 kết quả cho mỗi câu được chấm: 750 kết quả/phương pháp.
- Gold nguồn: `data/benchmark/ground_truth.json`, chỉ dùng `gold_context_ids` đã xác minh (`ground_truth.gold_context_ids`).
- Corpus: 2.164 chunk, 24 văn bản; SHA-256 bắt đầu `9a72a35e532f`.
- Dense: `BAAI/bge-m3`, 1024 chiều, Qdrant collection `vietnam_legal_chunks`.
- BM25: Elasticsearch index `bm25-e6-verified-20261101`, tìm kiếm `content_segmented`.
- Hybrid: BM25 + Dense, Reciprocal Rank Fusion với `rrf_k=60`, candidate depth 50, Top-10.
- `as_of_date` của từng câu được dùng theo cấu hình retrieval đã lưu.

## Định nghĩa metric

- **Strict Recall@K:** với từng câu hỏi, số `gold_context_id` phân biệt trong Top-K chia cho tổng số gold ID của câu; báo cáo là trung bình macro theo câu. Đây là quyết định benchmark `hits / len(gold)`, không phải hit-based (chỉ 0/1 cho câu có ít nhất một hit).
- **Parent Match@K:** tỷ lệ `parent_clause_id` gold phân biệt được tìm thấy trong parent ID của Top-K; dùng metadata parent trong corpus.
- **MRR@K:** nghịch đảo thứ hạng của gold chunk đầu tiên trong Top-K.
- **nDCG@K:** xếp hạng theo nhãn liên quan nhị phân của gold chunk.
- **Precision@10:** số chunk gold trong Top-10 chia cho 10.
- **Temporal Violation Rate:** tỷ lệ kết quả có metadata hiệu lực nhưng không có hiệu lực tại `as_of_date`; kết quả thiếu metadata ngày được thống kê riêng.

## Nhận xét

- Dense đạt Recall@10 và Parent Match@10 cao nhất, lần lượt **0.7574** và **0.7751**.
- Hybrid có Recall@5 cao nhất (**0.6769**), đồng thời đạt MRR@10 (**0.6973**), nDCG@10 (**0.6600**) và Precision@10 (**0.1640**) cao nhất. Điều này cho thấy Hybrid xếp các kết quả gold tốt hơn ở các vị trí đầu, dù độ bao phủ gold tại Top-10 thấp hơn Dense.
- BM25 thấp hơn Dense và Hybrid ở các metric truy xuất chính trong snapshot này.
- Không có temporal violation trong 750 kết quả/phương pháp được kiểm tra; điều này không chứng minh độ đúng pháp lý của nhãn hay câu trả lời.

## Giới hạn và diễn giải

- Đây là kết quả **Dev**, dùng để so sánh/tinh chỉnh; không đại diện cho kết quả Test hoặc chất lượng production. Chưa có kết quả Test trong các tệp nguồn của báo cáo.
- Chỉ 75/270 câu Dev được chấm vì chỉ các câu này có Gold đã xác minh. Kết quả không bao phủ 195 câu draft.
- Không có kiểm định ý nghĩa thống kê/độ bất định trong các file metric; chênh lệch giữa phương pháp là mô tả trên snapshot, không khẳng định có ý nghĩa thống kê.
- Đây là retrieval baseline, không phải đánh giá end-to-end của RAG, answer quality, Zero-shot hay Hybrid + Reranker.
- Precision@10, Recall, Parent Match, MRR, nDCG và provenance được lấy/đối chiếu từ `evaluation/results/bm25_dev_metrics.json`, `dense_dev_metrics.json`, `hybrid_dev_metrics.json`; temporal metrics được trích từ `retrieval/evaluation/retrieval_report.md`. Các metric JSON ghi cùng corpus hash, cấu hình Top-10/candidate depth 50/RRF k=60 và cùng 75 câu.

## Kết luận

Với mục tiêu tối đa hóa độ bao phủ gold trong Top-10, Dense là baseline dẫn đầu trên snapshot Dev này. Nếu ưu tiên đưa gold lên các thứ hạng đầu, Hybrid có MRR/nDCG/Precision cao nhất và Recall@5 cao nhất. Nên giữ cả hai làm đối chứng khi đánh giá các thay đổi tiếp theo; chỉ chốt lựa chọn sau khi chạy Test theo quy trình đã khóa.
