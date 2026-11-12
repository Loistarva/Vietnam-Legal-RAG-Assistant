# Structure-v2 Dev rerun

All three models were run sequentially on CPU with the same 10 Dev query/label semantics as the frozen baseline. Only the corpus version changed: 1,079 → 1024 token-safe article chunks, with 630 eligible under the unchanged expiry filter. Every model passed its tokenizer audit. Human review remains pending; no Test queries were run.

| Model | Recall@5: baseline → v2 | MRR@10: baseline → v2 | Labelled evidence Top-1 in v2 |
|---|---:|---:|---:|
| BKAI | 0.90 → 0.90 | 0.85 → 0.85 | 8/10 |
| AITeamVN | 1.00 → 1.00 | 1.00 → 1.00 | 10/10 |
| BGE-M3 | 1.00 → 1.00 | 1.00 → 1.00 | 10/10 |

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

The baseline files were preserved. Fixture/label hashes, query semantics, corpus/point counts, token audits, unique existing Top-10 IDs, expiry exclusion and per-query/macro metrics were independently checked. Raw result JSONs, cache snapshot observations and recomputed comparison are in `data/structure_v2/benchmark`.

Dataset SHA-256: `882ccfe5db1a061d5f133759cf67a16428608a6e5fb2e99379efe6be0a9ee78f`.
Labels SHA-256: `39c19e8d94f523f33dea8433a3b8ce81a7479ad8549a917883ae4ca2756bb3e0`.

These are provisional diagnostics on ten source-like questions, not a legal-accuracy certification. Candidate alternative evidence (e.g. Article 69 for the Article 70 question) remains outside the frozen judgments; labels were not edited to improve scores. Partial/unknown validity is still eligible and other parser issues remain. Timings are single CPU samples excluding preprocessing.

Next: review corpus-wide relevance and article-level validity, then implement a BM25 baseline and hybrid/RRF comparison on this frozen Dev version. Keep Test reserved until the configuration and labels are fixed.

BGE cache provenance was checked separately: its main revision matches the baseline; the additional safetensors-only snapshot has identical values and dtypes for all 391 tensors compared with the cached base `.bin` weights. Exact file hashes and the read-only verification method are in `data/structure_v2/benchmark/bge_weight_equivalence.json`. The result collector uses archived evidence and does not require a local model cache to rebuild this report.
