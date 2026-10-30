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
- Việc loại bỏ `parent_resolver`/`confidence_filter` hooks khỏi `HybridRetriever` cần làm sau khi nhánh BM25 được tích hợp để tránh xung đột file; không thực hiện trong thay đổi E8/E2 độc lập.
