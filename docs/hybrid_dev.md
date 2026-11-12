# Local BM25 and hybrid/RRF Dev baseline

The same frozen structure-v2 corpus (1,024 indexed chunks, 630 eligible) and 10 supporting-clause Dev labels were used. No Test queries, new labels, parameter sweep or reranker were used. Human review remains pending.

| Method | Recall@5 | MRR@10 | Labelled evidence Top-1 |
|---|---:|---:|---:|
| BM25 (local) | 1.000 | 0.883 | 8/10 |
| BGE-M3 dense | 1.000 | 1.000 | 10/10 |
| BM25 + BGE-M3 RRF | 1.000 | 0.950 | 9/10 |

| Question | BM25 rank | Dense rank | RRF rank |
|---|---:|---:|---:|
| priority_001 | 1 | 1 | 1 |
| priority_006 | 1 | 1 | 1 |
| priority_011 | 1 | 1 | 1 |
| priority_016 | 1 | 1 | 1 |
| priority_021 | 1 | 1 | 1 |
| priority_026 | 1 | 1 | 1 |
| priority_031 | 1 | 1 | 1 |
| priority_036 | 3 | 1 | 2 |
| priority_041 | 1 | 1 | 1 |
| priority_046 | 2 | 1 | 1 |

## Implementation and checks

BM25 uses full contextual text, Vietnamese underthesea segmentation, NFC/lowercase Unicode terms, binary query TF, k1=1.2 and b=0.75. IDF and length statistics are computed only over eligible documents. No-overlap lexical queries return no sparse evidence. These are standard BM25 parameters/IDF as documented by [Apache Lucene](https://lucene.apache.org/core/9_12_1/core/org/apache/lucene/search/similarities/BM25Similarity.html); this Python baseline is not an exact Lucene index or an Elasticsearch deployment.

The sparse and dense branches run concurrently; each returns up to 50 candidates. RRF uses sum(1/(60+rank)) with one-based ranks, ignores duplicate IDs per branch and uses deterministic ties. Parameters were fixed before viewing results, following the [original RRF paper](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf). No reranker is present.

The existing Qdrant collection was reused read-only after checking every ID, text and metadata payload against the fixture. Corpus vectors were not re-encoded. Live dense Top-10 rankings match the archived v2 baseline: **true**. A separate checker recomputed RRF and per-query/macro metrics, checked input hashes and rejected ineligible/unknown candidate IDs. Seven algorithm/concurrency/filter regression tests pass. Branch/end-to-end wall times include query preprocessing and are single CPU samples; they are not directly comparable to older encode-only timers.

## Findings and remaining work

RRF keeps all labelled evidence in Top-5 but moves priority_036 from dense rank 1 to fused rank 2, lowering labelled MRR from 1.00 to 0.95. BM25 ranks the same labelled clause third. No parameters or labels were changed to hide this result. The small source-like set has incomplete relevance judgments; it does not demonstrate that hybrid improves legal answer quality.

This implements an in-process BM25 baseline and parallel rank fusion, not full SRS FR2. Elasticsearch integration, metadata extraction/filtering by query, reranking and parent-context resolution remain pending. Validity filtering still matches the research baseline (fully expired excluded; partial/unknown retained), so it does not yet satisfy NFR1's current-law-only requirement. See [remaining_work.md](remaining_work.md) for the full project backlog.

Run from the repository root with cached models and the v2 Qdrant index available:

```powershell
.\.venv-embedding\Scripts\python.exe embedding/evaluate_hybrid_dev.py
node embedding/summarize_hybrid_dev.cjs
.\.venv-embedding\Scripts\python.exe -m unittest discover -s test -p test_hybrid_retrieval.py
```

Results: `data/structure_v2/hybrid/dev_results.json`. Dataset SHA-256: `882ccfe5db1a061d5f133759cf67a16428608a6e5fb2e99379efe6be0a9ee78f`; labels SHA-256: `39c19e8d94f523f33dea8433a3b8ce81a7479ad8549a917883ae4ca2756bb3e0`.
