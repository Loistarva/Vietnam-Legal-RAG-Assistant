# Performance smoke – live E2E 23/11/2026 (Sprint 11 D5.4)

Đây là số đo của một lần chạy, không phải kết luận NFR. NFR2.1 (< 2 s tới sự kiện trạng thái đầu tiên) cần SSE (đợt 2) và máy tham chiếu (D-10, chưa chốt); ngưỡng p95 của BO-05 chưa chốt. So sánh latency chỉ hợp lệ khi cùng máy (NFR2.3).

## Cấu hình máy

| Mục | Giá trị |
| --- | --- |
| Hệ điều hành | Windows 11 Home Single Language 10.0.26200 |
| CPU | 12th Gen Intel Core i7-12700H, 20 luồng |
| RAM | 15,7 GB |
| GPU | NVIDIA GeForce RTX 3050 Ti Laptop, 4 GB VRAM, driver 32.0.16.2101 |
| Python | 3.14 (`D:\AI_PRJ\.venv-vlra`), torch CUDA |
| Elasticsearch | 9.5.3 local, index `bm25-e6-verified-20261101` (2.322 chunk) |
| Qdrant | embedded, collection `vietnam_legal_chunks` (BGE-M3, 2.322 chunk, corpus `sha256:7105c484…6b023`) |
| Reranker | `bge-reranker-v2-m3`, cùng tiến trình API |
| Model | Ollama 0.40.17, `qwen2.5:7b` digest `845dbda0…697e`, temperature 0, `num_ctx 8192`, `num_predict 1024`, timeout 120 s |
| Đồng thời | `LEGAL_RAG_MAX_CONCURRENCY = 1`; request gửi tuần tự |

Qwen 7B không vừa 4 GB VRAM nên Ollama chia CPU/GPU; BGE-M3 và reranker dùng chung GPU trong tiến trình API.

## Số đo (ms, server `timings` của `AskResponse`)

Lượt 2, sau khi model đã nạp (lượt 1 cùng ngày nạp BGE-M3, reranker và Qwen).

| Ca | retrieval (gồm rerank) | LLM tổng | TTFT model | Tổng server | Client |
| --- | --- | --- | --- | --- | --- |
| Tuổi kết hôn nam | 1.490 | 15.464 | 153 | 16.981 | 16.988 |
| Tài sản chung | 2.356 | 31.482 | 148 | 33.847 | 33.859 |
| Ngày trong câu hỏi (2015) | 2.771 | 15.308 | 153 | 18.086 | 18.115 |
| UI: tuổi kết hôn nữ | 1.320 | 16.136 | 577 | 17.461 | 17.534 |
| HN_035, dưới ngưỡng (không gọi LLM) | 2.613 | – | – | 2.617 | 2.621 |
| Non-legal / ngoài phạm vi (API) | – | – | – | 1,9 / 2,0 | 7 / 23 |
| Non-legal / ngoài phạm vi (UI) | – | – | – | 1,7 / 1,8 | 86 / 78 |
| 401 / 422 | – | – | – | – | 2–25 |

Bốn câu Legal PASS: tổng server 17,0–33,8 s, trung vị khoảng 17,8 s; hơn 85% thời gian là sinh của Qwen (số token đầu ra quyết định). Retrieval + rerank 1,3–2,8 s. Bốn mẫu không đủ để tính p95.

Latency từng nhánh BM25 / Dense / RRF chưa đo được: Retrieval Adapter chưa trả các số này (D4.3, `RetrievalBundle.latency_breakdown` chờ duyệt ở SRS 5.6).
