# Báo cáo đánh giá truy xuất

- Ngày tạo: 2026-11-08
- Bộ Dev: `data/benchmark/queries_dev.json` (270 câu; chấm 75 câu)
- Corpus: `data/chunking_output/chunks.jsonl` (2322 chunk; SHA-256 bắt đầu `7105c4840613`).
- Phạm vi: corpus 28 văn bản; chỉ chấm trên Dev set, không phải đánh giá trên Test set.
- CSV chứa nội dung chunk được truy xuất, cờ liên quan và nội dung/mã chunk chuẩn để đối chiếu.
- Truy xuất thưa: Elasticsearch BM25 `multi_match` trên nội dung phân đoạn, đường dẫn ngữ cảnh và metadata Điều/Khoản.
- Elasticsearch index: `bm25-e6-verified-20261101`.
- Dense model: `BAAI/bge-m3` (dimension=1024); Qdrant collection: `vietnam_legal_chunks`.
- Cấu hình thực tế: Top-10; candidate depth=50; fusion=RRF; RRF k=60.
- Nhãn: Gold đã duyệt (`gold_context_ids_confirmed`) từ `ground_truth.json`; bỏ qua 195 câu Dev chưa duyệt.
- Chỉ tinh chỉnh trên Dev set; Test set đã đóng băng và không dùng để tinh chỉnh.

## Kết quả định lượng

| Phương pháp | Số kết quả | Recall@10 | Parent Match@10 | MRR@10 | nDCG@10 | Precision@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BM25 | 750 | 0.7036 | 0.7225 | 0.5989 | 0.5828 | 0.1560 |
| DENSE | 750 | 0.7685 | 0.7858 | 0.6607 | 0.6568 | 0.1653 |
| HYBRID | 750 | 0.7528 | 0.7679 | 0.7129 | 0.6709 | 0.1693 |

| Phương pháp | Temporal Violation Rate | Số vi phạm / đã kiểm tra | Chunk thiếu metadata ngày |
| --- | ---: | ---: | ---: |
| BM25 | 0.0000 | 0 / 750 | 0 |
| DENSE | 0.0000 | 0 / 750 | 0 |
| HYBRID | 0.0000 | 0 / 750 | 0 |

## Cách đọc và giới hạn

Các chỉ số là trung bình macro trên các câu hỏi Dev. Recall@10 đo tỷ lệ chunk liên quan được lấy về trong Top-10; Parent Match@10 đo tỷ lệ Khoản gold được truy xuất, dựa trên `parent_clause_id` có sẵn trong corpus (N/A nếu thiếu metadata); MRR@10 là nghịch đảo thứ hạng của chunk liên quan đầu tiên; nDCG@10 dùng nhãn liên quan nhị phân; Precision@10 chia số chunk liên quan trong Top-10 cho 10.
Temporal Violation Rate chỉ tính trên kết quả có ít nhất một mốc hiệu lực; chunk thiếu cả effective_from và effective_to được đếm riêng, không mặc định xem là hợp lệ.

Nhãn chưa được chuyên gia pháp lý thẩm định. Kết quả trên Dev dùng để phát triển và chọn cấu hình; không đại diện cho chất lượng trên Test set hoặc các lĩnh vực pháp luật khác.

Chi tiết từng truy vấn và chunk nằm trong `retrieval_results.csv`. Tên cột CSV được viết bằng tiếng Việt.
