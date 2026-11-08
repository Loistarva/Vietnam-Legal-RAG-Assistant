# D4.1 / M0 — Baseline Verification snapshot

Cập nhật: 08/11/2026. Working tree `feature/retrieval-router-batch`; corpus JSONL hiện tại đã là 2.322 chunks. Snapshot ghi tách bằng chứng code, corpus, smoke test và runtime index.

## Kết quả theo thứ tự nghiệm thu

| # | Hạng mục | Kết quả | Bằng chứng / giới hạn |
| --- | --- | --- | --- |
| 1 | Khởi tạo RetrievalPipeline | Đạt | `scripts/run_retrieval.py::build_pipeline` gọi `build_reranker(reranker_config)` và truyền đối tượng vào `RetrievalPipeline(...)`. |
| 2 | Metadata chunk | Đạt cho corpus hiện tại | Đã parse 2.322 JSON records hợp lệ, 2.322 `chunk_id` duy nhất. Root `title`, `document_number`, `document_type`, `breadcrumb` và nested `metadata.title`, `metadata.document_title`, `metadata.document_number`, `metadata.document_type` đều có trong 2.322/2.322. `metadata.breadcrumb` vắng mặt; code BM25 adapter đưa breadcrumb root vào metadata. |
| 3 | Cross-Encoder Top-5 trên query thật | Đạt | Artifact `reports/retrieval/d4_1_runtime_smoke_20261108.json`: retriever `hybrid`, ES index `bm25-e6-verified-20261101`, Qdrant collection `vietnam_legal_chunks`, Top-50 fused, SHA corpus `c1823935...b91264`; Cross-Encoder `BAAI/bge-reranker-v2-m3` chấm 50/50 và trả Top-5. Thời gian truy xuất 9.97s, rerank 54.00s, tổng 80.64s. |
| 4 | Qdrant SHA regression | Đạt | `python -m unittest test.test_run_dev_retrieval test.test_hybrid_retriever`: 22 tests pass. Bốn trường hợp metadata thiếu, SHA thiếu, SHA sai, SHA đúng nằm trong suite. |
| 5 | SHA runtime Elasticsearch/Qdrant | Đạt | Elasticsearch `bm25-e6-verified-20261101`: 2.322 docs; Qdrant `vietnam_legal_chunks`: 2.322 points. Cả metadata runtime/index metadata đều khớp SHA chuẩn hóa `c18239351424f62d65c4a146ef2a73ed023b1bf5330e0a3fdadb828872b91264`. |
| 6 | PR #26 | Đã xác minh merged | GitHub ghi merged vào `testing`; merge commit `f89ef8372a06102802349bb9ea0cf04fcc0a4646`; 2 checks passed. |
| 7 | Sign-off Dev3/Dev5 cho D4.1 | Chưa xác minh | Có xác nhận Dev3/Dev5 về phần review D1 trên PR #27, nhưng chưa có bằng chứng sign-off tương thích retrieval/reranker cho D4.1. Approval trên PR #26 chưa map được với vai trò Dev3/Dev5. |

## SHA và phân biệt Top-K

- Corpus `data/chunking_output/chunks.jsonl`: 2.322 records; SHA-256 băm raw `e6d17631cc75784c1885cc9a2d8b6dc58f63dcf40ffec1fed23fee6812d8d0f9`; SHA runner chuẩn hóa CRLF→LF `c18239351424f62d65c4a146ef2a73ed023b1bf5330e0a3fdadb828872b91264` (được Elasticsearch và Qdrant sử dụng).
- `retrieval/config.yaml`: SHA-256 `31f1b932cc7958dd979f7f7ff521c7401742cad823b80f0ac48b16600056c1d9`.
- `reranking/config.yaml`: SHA-256 `38d109b55a4da5b4e46369abbeea7bcf567cf20cf7779a951bb9073e016e0602`.
- Retrieval benchmark lưu/đánh giá Top-10; luồng RAG là Top-50 fused → Cross-Encoder → Top-5. Không dùng benchmark Top-10 thay cho Top-50 fused hoặc official RAG Top-5.

## Còn cần làm để đóng M0

1. Đã hoàn tất: Elasticsearch và Qdrant dựng lại trên 2.322 chunks; runtime count và SHA chuẩn hóa khớp.
2. Đã hoàn tất: query thật đi qua Hybrid Top-50 → Cross-Encoder Top-5; artifact JSON đã lưu.
3. Ghi sign-off Dev3/Dev5 cho tương thích reranker/retrieval hoặc xác nhận blocker còn lại.


