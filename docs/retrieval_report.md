# Retrieval benchmark report

## Latest run: updated corpus

BM25-only, Dense-only, and Hybrid RRF were run against the current Dev set and the latest chunk corpus on 2026-10-26.

- Dev set: `data/benchmark/queries_dev.json` (285 queries).
- Corpus: `data/chunking_output/chunks.jsonl` (2,011 unique chunks).
- BM25 index: `legal-child-chunks-current`.
- Dense model: `bkai-foundation-models/vietnamese-bi-encoder` (768 dimensions), collection `vietnam_legal_chunks_current`.
- Hybrid: Reciprocal Rank Fusion, candidate depth 50, RRF k=60, Top-10.
- 267 queries had candidate labels and 18 had no labels. No scored labels are confirmed gold labels; metrics are exploratory.

### Chunk-level metrics

| Method | Recall@10 | MRR@10 | nDCG@10 | Precision@10 |
| --- | ---: | ---: | ---: | ---: |
| BM25-only | 0.7923 | 0.6961 | 0.7028 | 0.2071 |
| Dense-only | 0.6850 | 0.5939 | 0.5709 | 0.1697 |
| **Hybrid RRF** | **0.8209** | **0.7678** | **0.7377** | **0.2131** |

### Article-level metrics

| Method | Recall@10 | MRR@10 | nDCG@10 | Precision@10 |
| --- | ---: | ---: | ---: | ---: |
| BM25-only | 0.8539 | 0.6986 | 0.7259 | 0.0929 |
| Dense-only | 0.8146 | 0.5977 | 0.6394 | 0.0876 |
| **Hybrid RRF** | **0.9120** | **0.7697** | **0.7920** | **0.0985** |

Hybrid led all reported metrics in this run. Because the labels are provisional, the comparison validates the retrieval workflow rather than legal answer quality.

The latest run's result files and detailed report are in [`retrieval/results`](../retrieval/results/), including [BM25](../retrieval/results/dev_bm25.json), [Dense](../retrieval/results/dev_dense.json), [Hybrid](../retrieval/results/dev_hybrid.json), [metrics](../retrieval/results/metrics.csv), [article metrics](../retrieval/results/article_metrics.csv), and the [run report](../retrieval/results/retrieval_report.md). These files are replaced when a new benchmark run is evaluated; outdated result snapshots are not kept in this folder.
