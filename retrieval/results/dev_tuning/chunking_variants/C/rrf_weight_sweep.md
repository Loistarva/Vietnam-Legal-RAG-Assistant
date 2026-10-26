# Dev: đánh giá trọng số Reciprocal Rank Fusion

- Ngày chạy: 2026-10-26
- Truy vấn Dev: 285
- Truy vấn có nhãn được chấm: 267
- Loại khỏi metric chunk-level: 18 query có nhãn `version_*` không tồn tại trong `chunks.jsonl`.
- Nhãn: `data\benchmark\gold_id_proposals_300.json`; không nạp hàng thuộc Test.
- File ánh xạ nhãn theo biến thể: `retrieval\results\dev_tuning\chunking_variants\label_mapping.json` (C).
- Corpus: `retrieval\results\dev_tuning\chunking_variants\C\chunks.jsonl` (1906 chunks).
- Candidate depth: 50; RRF k: 60.
- Đơn vị liên quan: `chunk_id`; Recall@5 là số nhãn chunk tìm thấy trong Top-5 chia tổng nhãn của query.

## Baseline và lựa chọn

| Cấu hình | BM25 / Dense | Recall@5 | MRR@5 |
| --- | ---: | ---: | ---: |
| BM25-only | — | 0.7541 | 0.6052 |
| Dense-only | — | 0.7647 | 0.6177 |
| Hybrid RRF hiện tại | — | 0.8040 | 0.6630 |

Lưới cho thấy cấu hình được chọn theo Recall@5 (hòa thì ưu tiên MRR@5) là BM25 0.30 / Dense 0.70. 
Cấu hình này được chọn chỉ theo Dev; kết quả Test đã chạy trước đó không được dùng để chọn trọng số.

## Lưới trọng số Dev

| BM25 | Dense | Recall@5 | MRR@5 |
| ---: | ---: | ---: | ---: |
| 0.00 | 1.00 | 0.7647 | 0.6177 |
| 0.05 | 0.95 | 0.7747 | 0.6295 |
| 0.10 | 0.90 | 0.8021 | 0.6407 |
| 0.15 | 0.85 | 0.8040 | 0.6411 |
| 0.20 | 0.80 | 0.8059 | 0.6391 |
| 0.25 | 0.75 | 0.8134 | 0.6403 |
| 0.30 | 0.70 | 0.8227 | 0.6463 |
| 0.35 | 0.65 | 0.8171 | 0.6536 |
| 0.40 | 0.60 | 0.8152 | 0.6566 |
| 0.45 | 0.55 | 0.8177 | 0.6523 |
| 0.50 | 0.50 | 0.8140 | 0.6622 |
| 0.55 | 0.45 | 0.8065 | 0.6546 |
| 0.60 | 0.40 | 0.8134 | 0.6564 |
| 0.65 | 0.35 | 0.8040 | 0.6630 |
| 0.70 | 0.30 | 0.8059 | 0.6685 |
| 0.75 | 0.25 | 0.7965 | 0.6591 |
| 0.80 | 0.20 | 0.7834 | 0.6563 |
| 0.85 | 0.15 | 0.7815 | 0.6392 |
| 0.90 | 0.10 | 0.7747 | 0.6315 |
| 0.95 | 0.05 | 0.7634 | 0.6231 |
| 1.00 | 0.00 | 0.7541 | 0.6052 |

## Độ trễ

Thời gian truy xuất BM25 + Dense + RRF trung bình 290.3 ms; trung vị 222.1 ms; p95 445.7 ms. Đây là một lần retrieve chung cho hai nhánh song song, không phải latency tách riêng từng nhánh.

## Giới hạn diễn giải

Trong 267 query Dev, 9 có `gold_context_ids_confirmed=true`; 258 query dùng nhãn proposal chưa được xác nhận đầy đủ. Vì vậy metric là kết quả tuning theo proposal, chưa phải kết luận chất lượng pháp lý độc lập.

Các query có ID nhãn phiên bản văn bản (`version_*`) được liệt kê riêng trong JSON và không tính là miss retrieval, vì benchmark này đối chiếu ở cấp chunk và các ID đó không tồn tại trong corpus chunk.

Tuning trọng số không đổi chunking. Kết quả này không dùng Test; do Test đã được xem ở lượt trước, không chạy lại Test để chọn cấu hình mới.

## Tệp nguồn

- BM25 Top-50: `retrieval\results\dev_tuning\chunking_variants\C\results\dev_bm25.json`
- Dense Top-50: `retrieval\results\dev_tuning\chunking_variants\C\results\dev_dense.json`
- Hybrid RRF Top-50 đối chiếu: `retrieval\results\dev_tuning\chunking_variants\C\results\dev_hybrid.json`
- Kết quả đầy đủ theo query và từng trọng số: `retrieval\results\dev_tuning\chunking_variants\C\rrf_weight_sweep.json`
