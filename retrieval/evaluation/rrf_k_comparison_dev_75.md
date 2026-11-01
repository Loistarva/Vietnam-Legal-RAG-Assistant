# So sánh cấu hình RRF trên Dev

- Ngày: 2026-11-01
- Tập Dev có 270 câu đã chạy retrieval; phép so sánh metric chỉ dùng 75 câu có Gold label được xác nhận. 195 câu còn lại chưa tham gia tính metric vì chưa có Gold label được xác nhận.
- Corpus: `data/chunking_output/chunks.jsonl`, 2.164 chunks, SHA-256 bắt đầu `9a72a35e532f`.
- Hai lượt chạy dùng cùng Elasticsearch index `bm25-e6-verified-20261101`, BGE-M3 1024 chiều, Qdrant collection `vietnam_legal_chunks`, candidate depth 50 và Top-10. Khác biệt cấu hình được đánh giá là `rrf_k`.
- Kết quả chi tiết: [`rrf_k10`](rrf_k10/retrieval_report.md) và [`rrf_k60`](rrf_k60/retrieval_report.md).

## Kết quả Hybrid

| Metric | RRF K=10 | RRF K=60 | Chênh lệch K10 − K60 | Tốt hơn |
| --- | ---: | ---: | ---: | :--- |
| Recall@10 | 0.7617 | 0.7395 | +0.0222 | K=10 |
| MRR@10 | 0.7033 | 0.6973 | +0.0060 | K=10 |
| nDCG@10 | 0.6671 | 0.6600 | +0.0071 | K=10 |
| Precision@10 | 0.1667 | 0.1640 | +0.0027 | K=10 |
| Temporal Violation Rate | 0.0000 | 0.0000 | 0.0000 | Hòa |

## Nhận xét và quyết định

Trong phép đánh giá hiện tại trên 75 câu có Gold label được xác nhận, K=10 cho kết quả tốt hơn K=60 ở cả bốn metric xếp hạng; temporal violation bằng 0 ở cả hai lượt.

RRF cho điểm mỗi tài liệu theo `sum(1 / (k + rank))`. Khi K nhỏ, chênh lệch đóng góp giữa thứ hạng cao và thấp lớn hơn tương đối; điều này làm các vị trí đầu của từng danh sách ảnh hưởng mạnh hơn đến thứ hạng hợp nhất.

`retrieval/config.yaml` hiện đặt `hybrid.rrf_k: 10` làm giá trị tạm thời, dựa trên phép so sánh này. Khi cả 270 câu Dev có Gold label được xác nhận, có thể đánh giá lại trên kết quả retrieval đã lưu nếu corpus, index và cấu hình retrieval không thay đổi. Không dùng kết quả Dev này để tuyên bố hiệu năng trên Test.

Giới hạn: hai báo cáo lượt chạy mô tả tập này là smoke test phát triển trên một văn bản và lưu ý nhãn chưa được chuyên gia pháp lý thẩm định. Vì vậy, kết quả hỗ trợ chọn cấu hình phát triển, chưa chứng minh chất lượng tổng quát trên nhiều lĩnh vực pháp luật.
