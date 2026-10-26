# Dev: đánh giá trọng số Reciprocal Rank Fusion

- Ngày chạy: 2026-10-26
- Truy vấn Dev: 285
- Truy vấn có nhãn được chấm: 267
- Loại khỏi metric chunk-level: 18 query có nhãn `version_*` không tồn tại trong `chunks.jsonl`.
- Nhãn: `data\benchmark\gold_id_proposals_300.json`; không nạp hàng thuộc Test.
- File ánh xạ nhãn theo biến thể: `retrieval\results\dev_tuning\chunking_variants\label_mapping.json` (B).
- Corpus: `retrieval\results\dev_tuning\chunking_variants\B\chunks.jsonl` (2655 chunks).
- Candidate depth: 50; RRF k: 60.
- Đơn vị liên quan: `chunk_id`; Recall@5 là số nhãn chunk tìm thấy trong Top-5 chia tổng nhãn của query.

## Baseline và lựa chọn

| Cấu hình | BM25 / Dense | Recall@5 | MRR@5 |
| --- | ---: | ---: | ---: |
| BM25-only | — | 0.7179 | 0.5731 |
| Dense-only | — | 0.7266 | 0.5820 |
| Hybrid RRF hiện tại | — | 0.7647 | 0.6199 |

Lưới cho thấy cấu hình được chọn theo Recall@5 (hòa thì ưu tiên MRR@5) là BM25 0.45 / Dense 0.55. 
Cấu hình này được chọn chỉ theo Dev; kết quả Test đã chạy trước đó không được dùng để chọn trọng số.

## Lưới trọng số Dev

| BM25 | Dense | Recall@5 | MRR@5 |
| ---: | ---: | ---: | ---: |
| 0.00 | 1.00 | 0.7266 | 0.5820 |
| 0.05 | 0.95 | 0.7434 | 0.5991 |
| 0.10 | 0.90 | 0.7634 | 0.6069 |
| 0.15 | 0.85 | 0.7765 | 0.6107 |
| 0.20 | 0.80 | 0.7840 | 0.6132 |
| 0.25 | 0.75 | 0.7821 | 0.6136 |
| 0.30 | 0.70 | 0.7834 | 0.6098 |
| 0.35 | 0.65 | 0.7853 | 0.6072 |
| 0.40 | 0.60 | 0.7903 | 0.6056 |
| 0.45 | 0.55 | 0.7959 | 0.6069 |
| 0.50 | 0.50 | 0.7903 | 0.6243 |
| 0.55 | 0.45 | 0.7759 | 0.6071 |
| 0.60 | 0.40 | 0.7722 | 0.6147 |
| 0.65 | 0.35 | 0.7647 | 0.6199 |
| 0.70 | 0.30 | 0.7553 | 0.6199 |
| 0.75 | 0.25 | 0.7534 | 0.6149 |
| 0.80 | 0.20 | 0.7628 | 0.6176 |
| 0.85 | 0.15 | 0.7534 | 0.6177 |
| 0.90 | 0.10 | 0.7441 | 0.6065 |
| 0.95 | 0.05 | 0.7253 | 0.6011 |
| 1.00 | 0.00 | 0.7179 | 0.5731 |

## Độ trễ

Thời gian truy xuất BM25 + Dense + RRF trung bình 306.5 ms; trung vị 225.1 ms; p95 456.7 ms. Đây là một lần retrieve chung cho hai nhánh song song, không phải latency tách riêng từng nhánh.

## Giới hạn diễn giải

Trong 267 query Dev, 9 có `gold_context_ids_confirmed=true`; 258 query dùng nhãn proposal chưa được xác nhận đầy đủ. Vì vậy metric là kết quả tuning theo proposal, chưa phải kết luận chất lượng pháp lý độc lập.

Các query có ID nhãn phiên bản văn bản (`version_*`) được liệt kê riêng trong JSON và không tính là miss retrieval, vì benchmark này đối chiếu ở cấp chunk và các ID đó không tồn tại trong corpus chunk.

Tuning trọng số không đổi chunking. Kết quả này không dùng Test; do Test đã được xem ở lượt trước, không chạy lại Test để chọn cấu hình mới.

## Tệp nguồn

- BM25 Top-50: `retrieval\results\dev_tuning\chunking_variants\B\results\dev_bm25.json`
- Dense Top-50: `retrieval\results\dev_tuning\chunking_variants\B\results\dev_dense.json`
- Hybrid RRF Top-50 đối chiếu: `retrieval\results\dev_tuning\chunking_variants\B\results\dev_hybrid.json`
- Kết quả đầy đủ theo query và từng trọng số: `retrieval\results\dev_tuning\chunking_variants\B\rrf_weight_sweep.json`
