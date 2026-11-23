# D4.1 / M0 — Baseline Verification snapshot

**Cập nhật:** 10/11/2026  
**Nhánh:** `feature/retrieval-router-batch`  
**Commit code tại lúc tạo precompute:** `70427828ae9b5eff3b2a0a10ef1042a12cccf04e`  
**Commit `origin/testing` được G3 xác nhận:** `afc3d32f33f27ba83a0c2e48d7e76ef172ac12f8`

## Baseline hiện tại

| Hạng mục | Kết quả | Bằng chứng |
| --- | --- | --- |
| Corpus | 2.322 chunks; SHA-256 chuẩn hóa CRLF→LF: `7105c484061399010b0f087c6c0d457cd688030b8184b0071f1291a036b6b023` | `data/chunking_output/chunks.jsonl`; SHA theo `embedding.vector_store.chunk_file_sha256()` |
| Retrieval config | SHA-256 chuẩn hóa: `08df4180c8c47fe86592bb2a41d8b0e5f88cc0194160a7990990b3c139de8179` | `retrieval/config.yaml` |
| Reranking config | SHA-256 chuẩn hóa: `b99cf7319ec93eeb49c241904eb89b5e3e6b41fbbc05b56e63347b25693c6471` | `reranking/config.yaml` |
| Elasticsearch mặc định | `bm25-e6-verified-20261101`; runtime smoke có request thành công | `reports/retrieval/week09_retrieval_smoke_20261110.md`; chưa có report riêng xác minh metadata SHA của index |
| Qdrant mặc định | `vietnam_legal_chunks`; migration report PASS, 2.322 points, dimension 1.024, Cosine; corpus SHA khớp | `reports/retrieval/d4_3_qdrant_migration_default_20261109.json` |
| Retrieval + Cross-Encoder | 3 smoke current/historical/outdated hoàn tất; Top-50 → Cross-Encoder → Top-5; các hit đạt kiểm tra hiệu lực theo ngày | `reports/retrieval/week09_retrieval_smoke_20261110.md` và ba JSON D4.7 cùng ngày chạy |
| D4.4 Dev30 precompute | 30 queries; 150 hits; retrieval rank đầy đủ; output SHA `6eb200f3803dfe341299f092ae1be9723ec9236f501f7bb53ef47dc098dd1353` | `evaluation/results/precompute/20261110_dev30_retrieval.jsonl`; manifest `reports/retrieval/precompute_manifest_20261110.json` |
| PR #26 / sign-off Dev3, Dev5 | Chưa ghi nhận bằng chứng sign-off mới trong snapshot này | Cần đối chiếu PR/reviewer trước khi tuyên bố nghiệm thu |

## Phân biệt Top-K

- Retrieval benchmark: kết quả Top-10.
- Official RAG: Top-50 fused → Cross-Encoder → Top-5.
- G3 precompute nguồn là artifact reranker Dev30; không dùng benchmark Top-10 thay cho Top-50 fused hoặc kết quả RAG Top-5.

## Lịch sử bằng chứng

Các report D4.1/D4.2/D4.3 ngày 08/11 và report B3 chạy riêng trên các collection/index hậu tố `_b3` đã bị thay thế cho baseline mặc định bởi migration/runtime evidence ngày 09–10/11. SHA corpus cũ `c1823935…` không còn là baseline hiện tại.

## Còn cần xác minh

1. Lưu bằng chứng metadata SHA runtime Elasticsearch để đối chiếu trực tiếp với corpus SHA hiện tại; smoke thành công và corpus SHA trong config của runner chưa tự chứng minh metadata index.
2. Ghi nhận sign-off của Dev3/Dev5 và trạng thái PR #26 nếu D4.1 cần đóng theo quy trình review.
