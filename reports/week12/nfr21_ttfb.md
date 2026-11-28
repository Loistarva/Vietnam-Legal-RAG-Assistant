# NFR2.1 – Thời gian tới sự kiện trạng thái đầu tiên (Sprint 12, Dev 5)

Ngày 26/11/2026. Căn cứ: SRS 2.1.3 (PR #68), NFR2.1-AC1 "Trên máy tham chiếu, qua API với Dev30, p95 thời gian tới byte trạng thái đầu tiên < 2 s"; D-10 (ghi cấu hình máy); kế hoạch Sprint 12 V1.5, task S12-D5.2.

## Kết quả: đạt

| Chỉ số (30 câu Dev30, tuần tự) | p50 | p95 | Ngưỡng |
| --- | --- | --- | --- |
| Tới sự kiện `status` đầu tiên (đo ở client) | 19 ms | 54 ms | < 2.000 ms |
| Tới sự kiện `final` (câu trả lời đã qua Gate) | 38,4 s | 103,3 s | Chưa có ngưỡng (BRD BO-05, D-10) |

Giá trị lớn nhất tới `status` đầu tiên: 210 ms ở client, 11 ms theo `elapsed_ms` của server. 30/30 request HTTP 200: 29 `SUCCESS`, 1 `ABSTAIN` `LOW_CONFIDENCE`. Percentile theo nearest rank.

## Điều kiện đo

- API: `origin/testing` `7d3c174`, `POST /api/v1/ask/stream`, live (Elasticsearch, Qdrant embedded BGE-M3, Ollama `qwen2.5:7b`, prompt `v1.2_controlled_rag`), `LEGAL_RAG_MAX_CONCURRENCY = 1`. Client và server cùng máy (localhost).
- Câu hỏi: `evaluation/rubrics/dev_gold_30_ids_v1.txt`, `as_of_date` lấy từ `data/benchmark/queries_dev.json`; mỗi câu gửi một lần, đọc hết stream rồi mới gửi câu sau.
- Máy: Windows 11 (10.0.26200), Intel 20 luồng (Family 6 Model 154), RAM 15,7 GB, NVIDIA GeForce RTX 3050 Ti Laptop 4 GB, Python 3.14.10. Máy tham chiếu chính thức chưa chốt (D-10); số trên chỉ so được với lượt đo cùng máy.
- Lệnh: `python scripts/measure_sse_ttfb.py --api-sha <sha> --out <dir>` (key từ `LEGAL_RAG_API_KEY`). Kết quả: [live/sse_ttfb_results.json](live/sse_ttfb_results.json), chỉ có `query_id`, mã trạng thái và thời gian, không có câu hỏi, câu trả lời hay key (NFR7.2).

## Ghi chú

- Sự kiện `status` (`accepted`) được gửi trước khi request chờ slot xử lý, nên con số này không gồm thời gian xếp hàng khi nhiều người dùng cùng lúc.
- Thời gian tới `final` gồm truy xuất và rerank live cùng sinh câu trả lời; khác latency của Run B official, vốn dùng kết quả truy xuất tính sẵn.
