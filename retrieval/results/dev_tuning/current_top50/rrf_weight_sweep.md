# Dev: đánh giá trọng số Reciprocal Rank Fusion

- Ngày chạy: 2026-10-26
- Truy vấn Dev: 285
- Truy vấn có nhãn được chấm: 267
- Loại khỏi metric chunk-level: 18 query có nhãn `version_*` không tồn tại trong `chunks.jsonl`.
- Nhãn: `data\benchmark\gold_id_proposals_300.json`; không nạp hàng thuộc Test.
- Corpus: `data\chunking_output\chunks.jsonl` (2011 chunks).
- Candidate depth: 50; RRF k: 60.
- Đơn vị liên quan: `chunk_id`; Recall@5 là số nhãn chunk tìm thấy trong Top-5 chia tổng nhãn của query.

## Baseline và lựa chọn

| Cấu hình | BM25 / Dense | Recall@5 | MRR@5 |
| --- | ---: | ---: | ---: |
| BM25-only | — | 0.7466 | 0.6022 |
| Dense-only | — | 0.5986 | 0.4393 |
| Hybrid RRF hiện tại | — | 0.7915 | 0.6154 |

Lưới cho thấy cấu hình được chọn theo Recall@5 (hòa thì ưu tiên MRR@5) là BM25 0.65 / Dense 0.35. 
Cấu hình này được khóa theo Dev; kết quả Test đã chạy trước đó không được dùng để chọn trọng số.

## Lưới trọng số Dev

| BM25 | Dense | Recall@5 | MRR@5 |
| ---: | ---: | ---: | ---: |
| 0.00 | 1.00 | 0.5986 | 0.4393 |
| 0.05 | 0.95 | 0.6230 | 0.4747 |
| 0.10 | 0.90 | 0.6673 | 0.5174 |
| 0.15 | 0.85 | 0.6729 | 0.5257 |
| 0.20 | 0.80 | 0.7047 | 0.5434 |
| 0.25 | 0.75 | 0.7179 | 0.5498 |
| 0.30 | 0.70 | 0.7441 | 0.5630 |
| 0.35 | 0.65 | 0.7634 | 0.5830 |
| 0.40 | 0.60 | 0.7603 | 0.5860 |
| 0.45 | 0.55 | 0.7821 | 0.5944 |
| 0.50 | 0.50 | 0.7915 | 0.6154 |
| 0.55 | 0.45 | 0.7859 | 0.6177 |
| 0.60 | 0.40 | 0.7859 | 0.6252 |
| 0.65 | 0.35 | 0.7990 | 0.6307 |
| 0.70 | 0.30 | 0.7953 | 0.6287 |
| 0.75 | 0.25 | 0.7821 | 0.6189 |
| 0.80 | 0.20 | 0.7634 | 0.6210 |
| 0.85 | 0.15 | 0.7597 | 0.6300 |
| 0.90 | 0.10 | 0.7653 | 0.6297 |
| 0.95 | 0.05 | 0.7559 | 0.6201 |
| 1.00 | 0.00 | 0.7466 | 0.6022 |

## Độ trễ

Thời gian truy xuất BM25 + Dense + RRF trung bình 299.6 ms; trung vị 210.9 ms; p95 326.7 ms. Đây là một lần retrieve chung cho hai nhánh song song, không phải latency tách riêng từng nhánh.

## Giới hạn diễn giải

Trong 267 query Dev, 9 có `gold_context_ids_confirmed=true`; 258 query dùng nhãn proposal chưa được xác nhận đầy đủ. Vì vậy metric là kết quả tuning theo proposal, chưa phải kết luận chất lượng pháp lý độc lập.

Các query có ID nhãn phiên bản văn bản (`version_*`) được liệt kê riêng trong JSON và không tính là miss retrieval, vì benchmark này đối chiếu ở cấp chunk và các ID đó không tồn tại trong corpus chunk.

Tuning trọng số không đổi chunking. Kết quả này không dùng Test; do Test đã được xem ở lượt trước, không chạy lại Test để chọn cấu hình mới.

## Tệp nguồn

- BM25 Top-50: `retrieval\results\dev_tuning\current_top50\dev_bm25.json`
- Dense Top-50: `retrieval\results\dev_tuning\current_top50\dev_dense.json`
- Hybrid RRF Top-50 đối chiếu: `retrieval\results\dev_tuning\current_top50\dev_hybrid.json`
- Kết quả đầy đủ theo query và từng trọng số: `retrieval\results\dev_tuning\current_top50\rrf_weight_sweep.json`
