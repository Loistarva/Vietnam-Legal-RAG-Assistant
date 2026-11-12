# Remaining work against the SRS

Scope: source and artifacts present on `feature/legal-data-chunking`. Completed
experiments are development baselines, not acceptance of the finished chatbot.

## Completed foundation

- Seven-document corpus; two contaminated final articles repaired; source archives
  and a versioned 1,024-chunk article retrieval fixture with token checks.
- Three-model dense Dev comparison, local BM25, parallel BM25/BGE search and RRF.
- Optional BGE cross-encoder reranker, integrated after RRF and evaluated on the
  fixed Top-50 pools. It reaches Recall@5/MRR@10 1.00/1.00 on the ten Dev labels;
  measured CPU rerank cost is about 18.9 seconds/query and needs optimization.
- Strict-by-default evidence search, shared metadata predicates before sparse/
  vector ranking, conservative reference extraction and canonical parent context
  with source-safe citations. Earlier benchmark policies/results are preserved.
- Input/version checks, full index payload verification, per-query metrics and
  regression checks. The 40 Test questions remain reserved.

## Implementation priorities

| Priority | Requirement | Remaining concrete work |
|---|---|---|
| 1 | Retrieval / FR2 | Optimize and validate reranker latency/candidate budget on Dev; preserve the measured Top-50 baseline. Small-set gains do not yet select a production configuration. |
| 1 | Data / NFR1 | Verify ND01 article-level partial expiry, ND03 status and other unresolved extraction/source/consolidation issues. Strict metadata filtering is implemented, but source labels and per-article legal effect still need verification before product answers. |
| 1 | Evaluation | Human-review all labels and alternative supporting clauses; broaden beyond L01 and source-like questions to other documents, ambiguous queries and no-answer cases. Freeze judgments/configuration before final Test evaluation. |
| 2 | Retrieval / FR2 | Extend the explicit-reference rules to disambiguation, negation and verified temporal/as-of policies. Integrate Elasticsearch if the SRS infrastructure is retained; the current BM25 backend is local Python. |
| 2 | Context / FR4 | Add a model-specific context packer/token budget and citation verification for generated claims. Parent resolution and synthetic-number handling are implemented; point-level extraction and broader source review remain pending. |
| 3 | Agent / FR1, FR3 | Implement legal/non-legal routing, clarification and evidence/confidence policy. Calibrate thresholds on labelled data; raw cosine/RRF scores alone are not legal confidence. |
| 3 | Generation / FR4, FR5 | Integrate an LLM with source-bound citation prompts, grounding checks, bounded retry and abstention/refusal when evidence is insufficient. |
| 4 | API and Web UI | Build API gateway, SSE streaming chat and citations/evidence panel; add integration tests for the full question-to-answer path. |
| 4 | NFR2, NFR3 and logging | Redis semantic cache, API key guard, rate limiting, request/quality logs and operational configuration. Measure full streaming TTFB and cached response latency after the application exists. |
| 5 | Acceptance | Run the frozen Test split, grounded-answer/citation checks, out-of-domain/no-answer scenarios and end-to-end performance/security checks. Document limits and deployment instructions. |

The next bounded implementation step is routing/clarification plus budgeted,
source-bound generation. Dataset/validity and human label work can proceed alongside implementation;
they must be resolved before claiming legal correctness or production readiness.
Do not treat 1.00 on ten Dev queries as general legal accuracy.

Sources in this repo: `docs/SRS.md`, `docs/structure_v2.md`,
`docs/structure_v2_dev.md`, `docs/hybrid_dev.md`, `docs/reranker_dev.md` and the versioned result JSONs.
