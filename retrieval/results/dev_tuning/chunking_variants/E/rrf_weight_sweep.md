# Dev: đánh giá trọng số Reciprocal Rank Fusion

- Ngày chạy: 2026-10-26
- Truy vấn Dev: 285
- Truy vấn có nhãn được chấm: 267
- Loại khỏi metric chunk-level: 18 query có nhãn `version_*` không tồn tại trong `chunks.jsonl`.
- Nhãn: `data\benchmark\gold_id_proposals_300.json`; không nạp hàng thuộc Test.
- File ánh xạ nhãn theo biến thể: `retrieval\results\dev_tuning\chunking_variants\label_mapping.json` (E).
- Corpus: `retrieval\results\dev_tuning\chunking_variants\E\chunks.jsonl` (1923 chunks).
- Candidate depth: 50; RRF k: 60.
- Đơn vị liên quan: `chunk_id`; Recall@5 là số nhãn chunk tìm thấy trong Top-5 chia tổng nhãn của query.

## Baseline và lựa chọn

| Cấu hình | BM25 / Dense | Recall@5 | MRR@5 |
| --- | ---: | ---: | ---: |
| BM25-only | — | 0.7503 | 0.6043 |
| Dense-only | — | 0.7647 | 0.6218 |
| Hybrid RRF hiện tại | — | 0.8002 | 0.6654 |

Lưới cho thấy cấu hình được chọn theo Recall@5 (hòa thì ưu tiên MRR@5) là BM25 0.35 / Dense 0.65. 
Cấu hình này được chọn chỉ theo Dev; kết quả Test đã chạy trước đó không được dùng để chọn trọng số.

## Lưới trọng số Dev

| BM25 | Dense | Recall@5 | MRR@5 |
| ---: | ---: | ---: | ---: |
| 0.00 | 1.00 | 0.7647 | 0.6218 |
| 0.05 | 0.95 | 0.7747 | 0.6342 |
| 0.10 | 0.90 | 0.8009 | 0.6418 |
| 0.15 | 0.85 | 0.8065 | 0.6445 |
| 0.20 | 0.80 | 0.8059 | 0.6415 |
| 0.25 | 0.75 | 0.8134 | 0.6433 |
| 0.30 | 0.70 | 0.8152 | 0.6453 |
| 0.35 | 0.65 | 0.8246 | 0.6521 |
| 0.40 | 0.60 | 0.8134 | 0.6491 |
| 0.45 | 0.55 | 0.8121 | 0.6509 |
| 0.50 | 0.50 | 0.8084 | 0.6662 |
| 0.55 | 0.45 | 0.8027 | 0.6578 |
| 0.60 | 0.40 | 0.8059 | 0.6598 |
| 0.65 | 0.35 | 0.8002 | 0.6654 |
| 0.70 | 0.30 | 0.7984 | 0.6679 |
| 0.75 | 0.25 | 0.7984 | 0.6591 |
| 0.80 | 0.20 | 0.7928 | 0.6583 |
| 0.85 | 0.15 | 0.7834 | 0.6390 |
| 0.90 | 0.10 | 0.7784 | 0.6303 |
| 0.95 | 0.05 | 0.7634 | 0.6201 |
| 1.00 | 0.00 | 0.7503 | 0.6043 |

## Độ trễ

Thời gian truy xuất BM25 + Dense + RRF trung bình 216.7 ms; trung vị 174.1 ms; p95 290.0 ms. Đây là một lần retrieve chung cho hai nhánh song song, không phải latency tách riêng từng nhánh.

## Giới hạn diễn giải

Trong 267 query Dev, 9 có `gold_context_ids_confirmed=true`; 258 query dùng nhãn proposal chưa được xác nhận đầy đủ. Vì vậy metric là kết quả tuning theo proposal, chưa phải kết luận chất lượng pháp lý độc lập.

Các query có ID nhãn phiên bản văn bản (`version_*`) được liệt kê riêng trong JSON và không tính là miss retrieval, vì benchmark này đối chiếu ở cấp chunk và các ID đó không tồn tại trong corpus chunk.

Tuning trọng số không đổi chunking. Kết quả này không dùng Test; do Test đã được xem ở lượt trước, không chạy lại Test để chọn cấu hình mới.

## Tệp nguồn

- BM25 Top-50: `retrieval\results\dev_tuning\chunking_variants\E\results\dev_bm25.json`
- Dense Top-50: `retrieval\results\dev_tuning\chunking_variants\E\results\dev_dense.json`
- Hybrid RRF Top-50 đối chiếu: `retrieval\results\dev_tuning\chunking_variants\E\results\dev_hybrid.json`
- Kết quả đầy đủ theo query và từng trọng số: `retrieval\results\dev_tuning\chunking_variants\E\rrf_weight_sweep.json`
