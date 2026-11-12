# Reranker Dev evaluation

The [publisher's multilingual BGE reranker](https://huggingface.co/BAAI/bge-reranker-v2-m3) scores query/passage pairs. This run pins model and tokenizer revision `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`, uses CPU FP32 with batch size 16, and reranks the frozen RRF Top-50 candidates into Top-10. No retrieval candidates, labels or Test queries were regenerated.

| Method | Recall@5 | MRR@10 |
|---|---:|---:|
| dense | 1.000 | 1.000 |
| rrf | 1.000 | 0.950 |
| reranked | 1.000 | 1.000 |

| Question | Dense rank | RRF rank | Reranked rank |
|---|---:|---:|---:|
| priority_001 | 1 | 1 | 1 |
| priority_006 | 1 | 1 | 1 |
| priority_011 | 1 | 1 | 1 |
| priority_016 | 1 | 1 | 1 |
| priority_021 | 1 | 1 | 1 |
| priority_026 | 1 | 1 | 1 |
| priority_031 | 1 | 1 | 1 |
| priority_036 | 1 | 2 | 1 |
| priority_041 | 1 | 1 | 1 |
| priority_046 | 1 | 1 | 1 |

## Validation and cost

All 10/10 questions have every labelled supporting clause in the candidate pool. Maximum pair length is 335 tokens against a 512-token budget including special tokens; no truncation is allowed. The checker validates candidate sets, source text, eligibility, preserved RRF scores, new ordering, frozen baseline values and independently recomputed metrics. Seven new regression tests cover score validation, deterministic ties, evidence preservation, empty pools, token overflow and pipeline integration beyond Top-10.

Mean rerank wall time is **18.874 seconds/query** on this CPU, including pair tokenization, token-budget checking, model scoring and sorting. It excludes retrieval because candidates were replayed. This is an offline single-run cost measurement, not an API/streaming TTFB measurement. Raw logits rank evidence and are not calibrated legal confidence.

## Scope

The reusable reranker is integrated as an optional stage in `HybridRetriever`. When disabled, the earlier hybrid API/ordering remains available. When enabled, output includes the original hybrid Top-10 plus a separate reranked Top-10, provenance, original fusion rank/score and timing.

This small Dev set uses incomplete supporting-clause judgments and close-to-source wording. Human review is pending; no parameters or labels were adjusted after scoring. A different valid supporting clause may be unlabelled. Scores here do not choose a production winner or establish legal accuracy. Current-law-only filtering, metadata query extraction, parent context, answer generation, API/UI and full Test validation remain pending.

Run with the embedding environment and internet on first model load:

```powershell
.\.venv-embedding\Scripts\python.exe -u embedding/evaluate_reranker_dev.py
node embedding/summarize_reranker_dev.cjs
.\.venv-embedding\Scripts\python.exe -m unittest discover -s test -p test_reranking.py
```

Results and validation: `data/structure_v2/reranker/`. Candidate-source SHA-256: `1843dab1ccd498f5c28e8dcbe65dfff5201112277bc05df7cc5746a5d1e63f32`. For the completed run, the resolved revision is stored in result JSON; rerunning the evaluator resolves the current model revision again, so check that field before comparing runs.

For an exact cached rerun, pass `--revision 953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e` to the evaluator and set `HF_HUB_OFFLINE=1`. This bypasses resolving the current remote revision and reuses the pinned model/tokenizer.
