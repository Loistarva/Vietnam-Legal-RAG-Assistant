# B3 — Retrieval và Qdrant trên corpus mới

Cập nhật: 09/11/2026. Corpus chuẩn hóa và runtime index đã được dựng, migrate và smoke test trên `origin/testing`.

## Source và corpus

| Hạng mục | Kết quả | Bằng chứng |
| --- | --- | --- |
| `origin/testing` | `5065bd380d8dba03877bee6fb50db931607f4df5` | `git show -s`; commit ngày 09/11/2026, PR #33 |
| PR nền trong lịch sử branch | #38, #39, #40, #41 | `git log origin/testing`; gồm cập nhật hiệu lực Khoản, benchmark, G3 rerun và D1.5 |
| Corpus | 2.322 chunks | `data/chunking_output/chunks.jsonl` |
| Corpus SHA chuẩn hóa CRLF→LF | `7105c484061399010b0f087c6c0d457cd688030b8184b0071f1291a036b6b023` | `embedding.vector_store.chunk_file_sha256()` |
| Corpus SHA raw trên Windows | `81c72a08bbfa41f2cb190faebb16d02beb4d505c8bb56b2072acada719c0d578` | SHA-256 bytes của JSONL; khác chuẩn hóa do line endings |

## BM25 và Qdrant

| Thành phần | Kết quả |
| --- | --- |
| Elasticsearch BM25 | PASS — index `bm25-e6-verified-20261109-b3`, indexed/count `2322/2322`, errors `0`, corpus SHA khớp |
| Qdrant local | PASS — collection `vietnam_legal_chunks_b3`, model `BAAI/bge-m3`, dimension 1024 |
| Qdrant Server migration | PASS — [migration report](d4_3_qdrant_migration_20261109.json); 2322 points, dimension 1024, Cosine |
| Payload fingerprint | Khớp — `f8054234939dc81f8a52b4edb973615c77164fa52881627cae27bd6fbbfb9323` |
| Vector comparison | PASS — tolerance `1e-7`, max abs diff `1.4900970457532026e-08`, min cosine similarity `0.9999999999999996` |
| Runtime smoke | Cả hai smoke dùng CLI override cho index `bm25-e6-verified-20261109-b3` và collection `vietnam_legal_chunks_b3`; `retrieval/config.yaml` được giữ nguyên để bảo toàn hash Test đã freeze. Để dùng Qdrant Server, đặt `QDRANT_URL=http://127.0.0.1:6333`. |

## Runtime smoke tests

| Trường hợp | Kết quả | Artifact |
| --- | --- | --- |
| Historical | PASS — Hybrid Top-50 → Cross-Encoder Top-5; `as_of_date=2010-01-01`, source `question` | [b3_historical_smoke_20261109.json](b3_historical_smoke_20261109.json) |
| Current | PASS — Hybrid Top-50 → Cross-Encoder Top-5; `as_of_date=2026-11-09`, source `ui` | [b3_current_smoke_20261109.json](b3_current_smoke_20261109.json) |
| Corpus/config trong runtime | Cả hai output ghi corpus SHA `7105c484...`, BM25 index và Qdrant collection B3 |

## D4.4 precompute liên quan

Precompute official Dev30 đã PASS, 30/30 IDs. Output SHA-256 là `f4f2d76c483bb76f420aa2ad7a734e2bd296c5e2715922eb07eddb336a7f8d2c`; source G3 SHA-256 là `738a07c63bb4812bd3a2f9a5e6bb3a57fc5358515057def63d87fc6c2d764dc7`. Manifest ở `reports/retrieval/precompute_manifest.json` ghi config SHA tại thời điểm precompute; lần cập nhật B3 sau đó đổi mặc định BM25/Qdrant sang index B3.

## Kết luận

B3.1–B3.5 có bằng chứng PASS cho source baseline, corpus, build BM25, build/migration Qdrant và historical/current runtime smoke. Collection cũ `vietnam_legal_chunks` được giữ nguyên; các smoke B3 đã xác minh collection mới bằng CLI override. Cấu hình đóng băng cho Test không bị thay đổi.
