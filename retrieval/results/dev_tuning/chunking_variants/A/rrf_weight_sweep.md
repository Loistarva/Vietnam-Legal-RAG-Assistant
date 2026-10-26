# Dev: đánh giá trọng số Reciprocal Rank Fusion

- Ngày chạy: 2026-10-26
- Truy vấn Dev: 285
- Truy vấn có nhãn được chấm: 267
- Loại khỏi metric chunk-level: 18 query có nhãn `version_*` không tồn tại trong `chunks.jsonl`.
- Nhãn: `data\benchmark\gold_id_proposals_300.json`; không nạp hàng thuộc Test.
- File ánh xạ nhãn theo biến thể: `retrieval\results\dev_tuning\chunking_variants\label_mapping.json` (A).
- Corpus: `retrieval\results\dev_tuning\chunking_variants\A\chunks.jsonl` (2011 chunks).
- Candidate depth: 50; RRF k: 60.
- Đơn vị liên quan: `chunk_id`; Recall@5 là số nhãn chunk tìm thấy trong Top-5 chia tổng nhãn của query.

## Baseline và lựa chọn

| Cấu hình | BM25 / Dense | Recall@5 | MRR@5 |
| --- | ---: | ---: | ---: |
| BM25-only | — | 0.7466 | 0.6022 |
| Dense-only | — | 0.7591 | 0.6124 |
| Hybrid RRF hiện tại | — | 0.7890 | 0.6549 |

Lưới cho thấy cấu hình được chọn theo Recall@5 (hòa thì ưu tiên MRR@5) là BM25 0.45 / Dense 0.55. 
Cấu hình này được chọn chỉ theo Dev; kết quả Test đã chạy trước đó không được dùng để chọn trọng số.

## Lưới trọng số Dev

| BM25 | Dense | Recall@5 | MRR@5 |
| ---: | ---: | ---: | ---: |
| 0.00 | 1.00 | 0.7591 | 0.6124 |
| 0.05 | 0.95 | 0.7653 | 0.6246 |
| 0.10 | 0.90 | 0.7971 | 0.6335 |
| 0.15 | 0.85 | 0.7971 | 0.6322 |
| 0.20 | 0.80 | 0.8096 | 0.6351 |
| 0.25 | 0.75 | 0.8152 | 0.6372 |
| 0.30 | 0.70 | 0.8152 | 0.6395 |
| 0.35 | 0.65 | 0.8171 | 0.6436 |
| 0.40 | 0.60 | 0.8059 | 0.6411 |
| 0.45 | 0.55 | 0.8196 | 0.6459 |
| 0.50 | 0.50 | 0.8140 | 0.6572 |
| 0.55 | 0.45 | 0.8027 | 0.6498 |
| 0.60 | 0.40 | 0.7984 | 0.6491 |
| 0.65 | 0.35 | 0.7890 | 0.6549 |
| 0.70 | 0.30 | 0.8002 | 0.6550 |
| 0.75 | 0.25 | 0.7871 | 0.6493 |
| 0.80 | 0.20 | 0.7871 | 0.6512 |
| 0.85 | 0.15 | 0.7778 | 0.6363 |
| 0.90 | 0.10 | 0.7784 | 0.6326 |
| 0.95 | 0.05 | 0.7597 | 0.6193 |
| 1.00 | 0.00 | 0.7466 | 0.6022 |

## Độ trễ

Thời gian truy xuất BM25 + Dense + RRF trung bình 305.5 ms; trung vị 226.0 ms; p95 527.3 ms. Đây là một lần retrieve chung cho hai nhánh song song, không phải latency tách riêng từng nhánh.

## Giới hạn diễn giải

Trong 267 query Dev, 9 có `gold_context_ids_confirmed=true`; 258 query dùng nhãn proposal chưa được xác nhận đầy đủ. Vì vậy metric là kết quả tuning theo proposal, chưa phải kết luận chất lượng pháp lý độc lập.

Các query có ID nhãn phiên bản văn bản (`version_*`) được liệt kê riêng trong JSON và không tính là miss retrieval, vì benchmark này đối chiếu ở cấp chunk và các ID đó không tồn tại trong corpus chunk.

Tuning trọng số không đổi chunking. Kết quả này không dùng Test; do Test đã được xem ở lượt trước, không chạy lại Test để chọn cấu hình mới.

## Tệp nguồn

- BM25 Top-50: `retrieval\results\dev_tuning\chunking_variants\A\results\dev_bm25.json`
- Dense Top-50: `retrieval\results\dev_tuning\chunking_variants\A\results\dev_dense.json`
- Hybrid RRF Top-50 đối chiếu: `retrieval\results\dev_tuning\chunking_variants\A\results\dev_hybrid.json`
- Kết quả đầy đủ theo query và từng trọng số: `retrieval\results\dev_tuning\chunking_variants\A\rrf_weight_sweep.json`
