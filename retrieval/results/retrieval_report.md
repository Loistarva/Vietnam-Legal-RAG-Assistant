# Báo cáo đánh giá truy xuất

- Ngày tạo: 2026-10-16
- Bộ Dev: `data/benchmark/queries_dev.json` (14 câu hỏi)
- Corpus: `embedding/data/han_gia_dinh_smoke_chunks.json` (321 chunk; SHA-256 bắt đầu `f1d9af4423dd`).
- Phạm vi: bộ smoke test phát triển trên một văn bản; chưa phải đánh giá trên corpus lớn hoặc bộ kiểm thử độc lập.
- CSV chứa nội dung chunk được truy xuất, cờ liên quan và nội dung/mã chunk chuẩn để đối chiếu.
- Truy xuất thưa: Elasticsearch BM25 `multi_match` trên nội dung phân đoạn, đường dẫn ngữ cảnh và metadata Điều/Khoản.
- Elasticsearch index: `legal-child-chunks-dev`.
- Dense model: `BAAI/bge-m3`; collection Qdrant embedded dùng cùng corpus.
- Cấu hình: Top-10; Hybrid candidate depth=50; RRF k=60.
- Nhãn liên quan chưa được chuyên gia pháp lý thẩm định.
- Đây là một lượt chạy cố định, chưa phải khảo sát tinh chỉnh tham số. Chỉ tinh chỉnh trên Dev set; repo chưa có Test set độc lập.

## Kết quả định lượng

| Phương pháp | Số kết quả | Recall@10 | MRR@10 | nDCG@10 | Precision@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| BM25 | 140 | 0.8929 | 0.5620 | 0.6415 | 0.0929 |
| DENSE | 140 | 1.0000 | 0.9524 | 0.9586 | 0.1071 |
| HYBRID | 140 | 1.0000 | 0.8197 | 0.8684 | 0.1071 |

## Cách đọc và giới hạn

Các chỉ số là trung bình macro trên các câu hỏi Dev. Recall@10 đo tỷ lệ chunk liên quan được lấy về trong Top-10; MRR@10 là nghịch đảo thứ hạng của chunk liên quan đầu tiên; nDCG@10 dùng nhãn liên quan nhị phân; Precision@10 chia số chunk liên quan trong Top-10 cho 10.

Bộ Dev nhỏ này chỉ gồm một văn bản và nhãn chưa được chuyên gia thẩm định. Kết quả xác nhận quy trình và hỗ trợ phát triển; không đại diện cho chất lượng trên các lĩnh vực hoặc văn bản pháp luật khác.

Chi tiết từng truy vấn và chunk nằm trong `retrieval_results.csv`. Tên cột CSV được viết bằng tiếng Việt.
