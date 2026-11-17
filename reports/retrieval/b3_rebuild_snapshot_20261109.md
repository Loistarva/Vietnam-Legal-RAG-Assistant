# B3 — Retrieval và Qdrant trên corpus mới

**Cập nhật:** 10/11/2026. Bằng chứng baseline phải dùng corpus chuẩn hóa `7105c484…`; corpus `c1823935…` và các index cũ không được xem là baseline B3.

## Source và corpus

| Hạng mục | Trạng thái | Bằng chứng |
| --- | --- | --- |
| `origin/testing` | Commit `afc3d32f33f27ba83a0c2e48d7e76ef172ac12f8` (theo manifest precompute) | Bao gồm trạng thái `testing` được G3 kiểm tra |
| Corpus | 2.322 chunks | `data/chunking_output/chunks.jsonl` |
| Corpus SHA-256 chuẩn hóa CRLF→LF | `7105c484061399010b0f087c6c0d457cd688030b8184b0071f1291a036b6b023` | `embedding.vector_store.chunk_file_sha256()` |

## Runtime mặc định và Qdrant

| Thành phần | Cấu hình | Bằng chứng / giới hạn |
| --- | --- | --- |
| Elasticsearch BM25 | `bm25-e6-verified-20261101` | Runtime `GET /_mapping`: `_meta.corpus_sha256=7105c484061399010b0f087c6c0d457cd688030b8184b0071f1291a036b6b023`; `GET /_count`: 2.322 documents (kiểm tra 10/11/2026) |
| Qdrant Server | `vietnam_legal_chunks` | [Migration report mặc định](d4_3_qdrant_migration_default_20261109.json): 2.322 points, dimension 1.024, Cosine, corpus SHA khớp |
| Retrieval runtime | Hybrid Top-50 → Cross-Encoder Top-5 | [Smoke report](week09_retrieval_smoke_20261110.md): current, historical, outdated; không override tên index/collection |

Các collection/index hậu tố `_b3` là kết quả build tạm trước khi xác nhận tên mặc định. Không dùng chúng làm runtime target sau khi đã chuyển về tên trong `retrieval/config.yaml`.

## D4.4 precompute

Precompute Dev30 mới: 30 query, output SHA-256 `6eb200f3803dfe341299f092ae1be9723ec9236f501f7bb53ef47dc098dd1353`, corpus SHA khớp `7105c484…`. Manifest ngày 10/11 ghi SHA config chuẩn hóa và raw SHA riêng.

## Artifact

- `reports/retrieval/d4_3_qdrant_migration_default_20261109.json`
- `reports/retrieval/week09_retrieval_smoke_20261110.md`
- `reports/retrieval/precompute_manifest.json`
- `evaluation/results/precompute/20261110_dev30_retrieval.jsonl`
