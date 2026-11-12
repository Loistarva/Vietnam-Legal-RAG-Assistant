# BKAI development baseline

This provisional run uses 10 assistant-reviewed supporting-clause questions. Three questions were clarified before retrieval (priority_006, priority_026, priority_041). Human review remains pending; the 40 Test questions were not run or changed.

- Dataset: 1079 chunks; 638 eligible under the existing expiry filter.
- Recall@5: **0.9000**.
- MRR@10: **0.8500**.
- Mean query embedding + Qdrant search: **45.14 ms**, excluding model loading, document indexing and preprocessing outside the encode timer.
- Labels hash: `365d39189ac6354e6d36f41465e069d11f79c2e4d200e7f8fd02a8dffcc84c62`.
- Dataset hash: `79b4a7085e80142f6aad6703a5f53781f73cd998626f36f97ec84daa914c5cc5`.
- Model revision: `84f9d9ada0d1a3c37557398b9ae9fcedcdf40be0`.

| Question | First labelled relevant rank | Recall@5 | MRR@10 | Top-1 |
|---|---:|---:|---:|---|
| priority_001 | 1 | 1.000 | 1.000 | `L01_art_8_clause_1_chunk_1` |
| priority_006 | 1 | 1.000 | 1.000 | `L01_art_14_clause_1_chunk_1` |
| priority_011 | 1 | 1.000 | 1.000 | `L01_art_20_clause_1_chunk_1` |
| priority_016 | 1 | 1.000 | 1.000 | `L01_art_28_clause_1_chunk_1` |
| priority_021 | 2 | 1.000 | 0.500 | `L01_art_35_clause_2_chunk_1` |
| priority_026 | 1 | 1.000 | 1.000 | `L01_art_45_clause_1_chunk_1` |
| priority_031 | 1 | 1.000 | 1.000 | `L01_art_53_clause_1_chunk_1` |
| priority_036 | >10 | 0.000 | 0.000 | `L01_art_69_clause_1_chunk_1` |
| priority_041 | 1 | 1.000 | 1.000 | `L01_art_81_clause_1_chunk_1` |
| priority_046 | 1 | 1.000 | 1.000 | `L01_art_90_clause_1_chunk_1` |

These are development diagnostics against known supporting clauses, not comprehensive legal-relevance judgments. Other relevant chunks may be unlabelled. The small set is close to source wording. Partial/unknown legal statuses remain eligible and parser structure issues remain; these metrics do not establish production readiness or select a model winner.

Next: inspect missed queries and alternative evidence, review human labels and parser structure, then compare other models on exactly the same corpus and Dev labels. Keep Test reserved until configuration is frozen.

## Post-run evidence review (labels and scores unchanged)

- **priority_036:** labelled Article 70(1) is absent from Top-10, so its stored Recall/MRR are zero. Top-1 is Article 69(1), whose corpus text directly states that parents should love their children and respect their opinions. This is a candidate additional supporting label requiring review; the observed miss is not sufficient to conclude that retrieval returned no useful evidence. No post-run relabelling or optimistic metric was applied.
- **priority_021:** labelled Article 35(1) is ranked second. Top-1 Article 35(2) discusses written agreement for particular transactions. Top-3 ND01 Article 13(1) also states the agreement rule, but ND01 is partially expired and needs article-level validity verification before its evidence can be approved for current-law answers.

Review these candidate labels in a separately versioned judgment set before comparing models. Preserve this run and its original labels for an honest baseline.
