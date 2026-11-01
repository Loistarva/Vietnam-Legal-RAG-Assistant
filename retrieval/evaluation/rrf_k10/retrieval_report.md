# Báo cáo đánh giá truy xuất

- Ngày tạo: 2026-11-01
- Bộ Dev: `data/benchmark/queries_dev.json` (75 câu hỏi)
- Corpus: `data/chunking_output/chunks.jsonl` (2164 chunk; SHA-256 bắt đầu `9a72a35e532f`).
- Phạm vi: bộ smoke test phát triển trên một văn bản; chưa phải đánh giá trên corpus lớn hoặc bộ kiểm thử độc lập.
- CSV chứa nội dung chunk được truy xuất, cờ liên quan và nội dung/mã chunk chuẩn để đối chiếu.
- Truy xuất thưa: Elasticsearch BM25 `multi_match` trên nội dung phân đoạn, đường dẫn ngữ cảnh và metadata Điều/Khoản.
- Elasticsearch index: `bm25-e6-verified-20261101`.
- Dense model: `BAAI/bge-m3` (dimension=1024); Qdrant collection: `vietnam_legal_chunks`.
- Cấu hình thực tế: Top-10; candidate depth=50; fusion=RRF; RRF k=10.
- Nhãn: Gold đã duyệt (`gold_context_ids_confirmed`) từ `ground_truth.json`; bỏ qua 195 câu Dev chưa duyệt.
- Đây là một lượt chạy cố định, chưa phải khảo sát tinh chỉnh tham số. Chỉ tinh chỉnh trên Dev set; repo chưa có Test set độc lập.

## Kết quả định lượng

| Phương pháp | Số kết quả | Recall@10 | MRR@10 | nDCG@10 | Precision@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| BM25 | 750 | 0.6736 | 0.5778 | 0.5612 | 0.1480 |
| DENSE | 750 | 0.7574 | 0.6563 | 0.6490 | 0.1587 |
| HYBRID | 750 | 0.7617 | 0.7033 | 0.6671 | 0.1667 |

| Phương pháp | Temporal Violation Rate | Số vi phạm / đã kiểm tra | Chunk thiếu metadata ngày |
| --- | ---: | ---: | ---: |
| BM25 | 0.0000 | 0 / 750 | 0 |
| DENSE | 0.0000 | 0 / 750 | 0 |
| HYBRID | 0.0000 | 0 / 750 | 0 |

## Cách đọc và giới hạn

Các chỉ số là trung bình macro trên các câu hỏi Dev. Recall@10 đo tỷ lệ chunk liên quan được lấy về trong Top-10; MRR@10 là nghịch đảo thứ hạng của chunk liên quan đầu tiên; nDCG@10 dùng nhãn liên quan nhị phân; Precision@10 chia số chunk liên quan trong Top-10 cho 10.
Temporal Violation Rate chỉ tính trên kết quả có ít nhất một mốc hiệu lực; chunk thiếu cả effective_from và effective_to được đếm riêng, không mặc định xem là hợp lệ.

Bộ Dev nhỏ này chỉ gồm một văn bản và nhãn chưa được chuyên gia thẩm định. Kết quả xác nhận quy trình và hỗ trợ phát triển; không đại diện cho chất lượng trên các lĩnh vực hoặc văn bản pháp luật khác.

Chi tiết từng truy vấn và chunk nằm trong `retrieval_results.csv`. Tên cột CSV được viết bằng tiếng Việt.
