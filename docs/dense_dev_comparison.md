# Provisional dense retrieval comparison on Dev

All three runs use the same frozen 1,079-chunk corpus and the same 10 assistant-reviewed Dev questions. The current filter leaves 638 eligible chunks. Human review is pending; the 40 Test questions were not evaluated. Every model passed a full-corpus tokenizer audit.

| Model | Recall@5 | MRR@10 | Labelled evidence Top-1 | Mean encode + search (ms) |
|---|---:|---:|---:|---:|
| BKAI | 0.900 | 0.850 | 8/10 | 45.14 |
| AITeamVN | 1.000 | 1.000 | 10/10 | 128.01 |
| BGE-M3 | 1.000 | 1.000 | 10/10 | 144.86 |

Times exclude model loading, corpus ingestion and preprocessing outside the encode timer. These single CPU runs are exploratory, not a controlled performance ranking.

| Question | BKAI relevant rank | AITeamVN relevant rank | BGE-M3 relevant rank |
|---|---:|---:|---:|
| priority_001 | 1 | 1 | 1 |
| priority_006 | 1 | 1 | 1 |
| priority_011 | 1 | 1 | 1 |
| priority_016 | 1 | 1 | 1 |
| priority_021 | 2 | 1 | 1 |
| priority_026 | 1 | 1 | 1 |
| priority_031 | 1 | 1 | 1 |
| priority_036 | >10 | 1 | 1 |
| priority_041 | 1 | 1 | 1 |
| priority_046 | 1 | 1 | 1 |

Dataset SHA-256: `79b4a7085e80142f6aad6703a5f53781f73cd998626f36f97ec84daa914c5cc5`.
Labels SHA-256: `365d39189ac6354e6d36f41465e069d11f79c2e4d200e7f8fd02a8dffcc84c62`.
Model revisions, source results and recomputed per-query scores are in `embedding/results/priority_dense_dev_comparison.json`.

The baseline judgments remain frozen. Article 69(1), returned for priority_036, is a candidate alternative supporting clause, so missing the labelled Article 70(1) does not establish that no useful evidence was retrieved. See `embedding/data/priority_dev.candidate_relevance_review.json`; candidate labels were not silently applied to any model's score.

Do not pick a production winner from ten source-like questions. Next, review corpus-wide relevance labels and parser structure/validity, freeze a new Dev judgment version if needed, then implement and compare BM25/hybrid retrieval. Keep Test reserved until configuration is fixed and labels are reviewed.

## Observed parser issue to address next

The BGE-M3 default smoke query returns `ND01_art_67_clause_1_chunk_1` and `ND01_art_67_clause_4_chunk_1` in its Top-5. Those corpus records contain appendix material classified as Article 67 clauses; the appendix describes customs to eliminate or prohibit, so its list items must not be read as standalone current-law prohibitions. This is an observed context-boundary problem, distinct from the ten-query retrieval metric. Separate article text, appendix headings/items and footer material in ND01 and ND04 before building an answer generator or declaring production readiness. Preserve this frozen baseline when regenerating corrected data.
