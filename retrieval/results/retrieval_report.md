# Retrieval evaluation report

- Ngày tạo: 2026-10-15
- Dev set: `embedding/data/dev_queries.json` (14 câu hỏi)
- Corpus: `embedding/data/han_gia_dinh_smoke_chunks.json` (321 chunks; fixture SHA-256 bắt đầu `f1d9af4423dd`).
- CSV includes retrieved chunk text, relevance flag, and expected relevant chunk IDs/text for direct comparison.
- Dense model: BKAI Vietnamese Bi-Encoder; Qdrant local collection khớp fixture.
- Cấu hình truy xuất: Top-10; Hybrid candidate depth=50; RRF k=60.
- Nhãn relevant được đối chiếu với nội dung chunk nhưng chưa được chuyên gia pháp lý thẩm định.
- Cấu hình hiện tại là một lượt chạy cố định, chưa phải sweep tuning. Tinh chỉnh tham số chỉ trên Dev set; repo hiện chưa có Test set tách biệt.

## Kết quả

| Phương pháp | Số kết quả | Recall@10 | MRR@10 |
| --- | ---: | ---: | ---: |
| BM25 | 140 | 0.7857 | 0.7381 |
| DENSE | 140 | 0.9643 | 0.8595 |
| HYBRID | 140 | 1.0000 | 0.8333 |

## Diễn giải và giới hạn

Các chỉ số là macro average trên 14 câu hỏi. Recall@10 là tỷ lệ chunk có nhãn relevant được lấy về trong 10 kết quả; MRR@10 là nghịch đảo hạng của chunk relevant đầu tiên, hoặc 0 nếu không có chunk relevant trong Top-10.

Đây là bộ Dev nhỏ, được tạo từ một văn bản và nhãn chưa qua đánh giá chuyên gia. Kết quả chỉ xác nhận quy trình và hỗ trợ phát triển; không đại diện cho chất lượng trên các lĩnh vực pháp luật hoặc văn bản khác.

Chi tiết từng truy vấn và chunk nằm trong `retrieval_results.csv`.
