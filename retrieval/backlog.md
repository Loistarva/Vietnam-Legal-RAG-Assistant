# Backlog Retrieval

Các hạng mục dưới đây chưa nằm trong Sprint 6; giữ chúng ngoài luồng truy xuất đang nghiệm thu.

| ID | Hạng mục | Trạng thái | Owner | Điều kiện nghiệm thu |
| --- | --- | --- | --- | --- |
| E11-1 | Confidence Threshold Filter (LLM Judge, MMR và Active Clarification) | Chưa triển khai; cần chốt yêu cầu nghiệp vụ và tiêu chí đo | Chưa phân công | Có rubric được duyệt; test xác nhận ngưỡng, MMR, nhánh clarification và không làm giảm retrieval metrics ngoài mức chấp nhận đã thống nhất. |
| E11-2 | Semantic Query / Reranker cache qua Redis | Chưa tích hợp; `RedisJSONCache` hiện không thuộc luồng benchmark được xác nhận | Chưa phân công | Có quy tắc cache key bao gồm query, model, corpus/index, ngày truy vấn và cấu hình; test cache hit/miss, invalidation và đo latency. |

## Ranh giới kiến trúc hiện tại

- `ParentContextResolver` thuộc `RetrievalPipeline`, sau retrieval/reranking.
- BM25, Dense và RRF thuộc `HybridRetriever`.
- Reranker là thành phần tùy chọn sau fusion.
- E11-1/E11-2 không tự động bật trong pipeline cho đến khi được giao, có owner và tiêu chí nghiệm thu.

## Kết quả audit E11 (2026-10-30)

| Hook/thành phần | Implementation và call site hiện tại | Quyết định |
| --- | --- | --- |
| Parent context | `ParentContextResolver` đọc `parents.json`, tra `child_ids`, trả `parent_id` và `parent_text`; được gọi đúng một lần trong `RetrievalPipeline.run()` sau rerank. CLI tạo resolver trong `scripts/run_retrieval.py`. | Giữ tại Pipeline. Đã bỏ hook `parent_resolver` khỏi `HybridRetriever` để tránh resolve hai tầng. |
| Confidence filter | Trước đây là callback tùy ý trong `HybridRetriever`; không có LLM Judge, rubric hoặc active-clarification implementation/call site. | Đã bỏ callback khỏi Hybrid. LLM Judge, ngưỡng, MMR và clarification ở backlog E11-1; không giả lập confidence. |
| Reranker | Cross-Encoder adapter có implementation; CLI `scripts/run_retrieval.py` điều phối reranker ở Pipeline sau Hybrid. `HybridRetriever` cũng hỗ trợ reranker tùy chọn cho các caller trực tiếp. | Giữ; benchmark BM25/Dense/Hybrid không tự bật reranker. |
| RedisJSONCache / cache hook | JSON `GET`/`SETEX` adapter có thể dùng được nhưng không có call site production. Hybrid key chưa có version/hashes của model, corpus và index. | Không bật trong production/benchmark. E11-2 yêu cầu cache key có versioning/invalidation và test latency trước khi tích hợp. |

Các cache tests đang kiểm tra cách ly theo metadata filter và RRF, không chứng minh an toàn cache giữa các model/corpus/index. Không coi Redis cache là tính năng đã tích hợp.
