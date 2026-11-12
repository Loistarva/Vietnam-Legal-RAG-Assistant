# Shared retrieval policy and parent context

The new `LegalSearchPipeline` assembles evidence with strict metadata filtering
and canonical parent context. It does not generate an answer or claim that
metadata alone certifies the legal validity/consolidation of source text.

## Behavior

- The high-level pipeline defaults to `current_only`: only records labelled
  `Còn hiệu lực` are eligible. The v2 corpus has 409 such chunks, versus 630 under
  the research filter. Fully expired, partially expired and unknown-status
  documents are not silently substituted when strict search returns no evidence.
- Document number/type and explicitly stated **publication year** can narrow the
  same predicate. Vietnamese/ASCII document-code variants are normalized. Generic
  phrases such as `pháp luật` or the verb in `Ai quyết định...` are not treated as
  document-type filters. A marriage year/age is not a publication-year filter.
- BM25 applies this predicate before computing per-query IDF/length statistics.
  Dense search applies the exact same eligible chunk IDs as a Qdrant `HasIdCondition`
  before vector ranking. Returned dense IDs are checked against the allowed set.
  An empty set returns no results and skips model inference; it never broadens
  the search to the whole corpus.
- For compatibility, calling low-level `HybridRetriever` without a policy keeps
  the research behavior used by earlier benchmarks. An explicit
  `RetrievalPolicy(validity_mode='exclude_expired')` is available for research;
  it does not approve partial/unknown documents for current-law answers.

This is conservative rule-based extraction of explicit references. Negation,
complex comparisons and historical/as-of validity are not interpreted. Issuance
year is not effective year. Those questions need a separate interpretation and
validity policy; they must not be answered as though this helper reasoned about
historical law. Allowlist filtering is practical for this small corpus; a larger
deployment should use indexed metadata filters with equivalent semantics.

## Context and citations

`ParentContextResolver` checks child/document/clause relationships against the
versioned v2 documents and fixture. It rejects mismatched hit text, forged source
metadata and evidence outside the selected policy. Parent lookup uses canonical
metadata, not ID-string guessing or model-supplied citations.

Each selected child restores its **full parent clause** and **full article**,
including sibling clauses and nonduplicated intro text. The pipeline deduplicates
article contexts while retaining each child and clause reference separately.
Source document number, URL/file/page and status are retained. Unnumbered
paragraphs stored under a synthetic clause ID do not produce `Khoản 1` in the
citation label, including older records where that flag was absent. No point-level
reference is invented. Citations reflect the archived source metadata; source
verification and unresolved parser issues remain separate work.

Context text is not silently truncated and is not passed back into the child
reranker. A future LLM context packer must apply an explicit token budget instead
of blindly concatenating every full article. Outputs contain `answer_generated:
false`, `evidence`, deduplicated `parent_contexts` and the `applied_policy`.

```python
from legal_context import ParentContextResolver, LegalSearchPipeline
from retrieval_policy import RetrievalPolicy

resolver = ParentContextResolver(document_dir, token_safe_fixture)
pipeline = LegalSearchPipeline(existing_hybrid_retriever, resolver)
result = pipeline.search('Điều kiện kết hôn theo Luật số 52/2014/QH13?')
# An explicit policy overrides automatic reference extraction; it is not merged
# silently with a partially interpreted natural-language query.
result = pipeline.search(query, policy=RetrievalPolicy(issue_year=2014))
```

## Verification

Eleven new regression tests cover strict/research eligibility, document reference
and year extraction, ambiguous wording, filtered BM25 statistics, shared dense
allowlists, zero-result behavior, blocked backend leakage, complete parent
restoration, citation numbering, forged metadata and parent deduplication.

`embedding/validate_legal_search.py` checks the real existing Qdrant index and
seven live scenarios: explicit law/decree references, issuance year, fully expired,
unknown/partial status exclusions and the generic decision verb. Reranking is
disabled in this smoke test to isolate policy/context behavior. No Dev scores,
Test questions, corpus data or old result files are changed.

```powershell
.\.venv-embedding\Scripts\python.exe -u embedding/validate_legal_search.py
python -m unittest discover -s test -p 'test_*.py'
node --test test/priority_dataset.test.cjs
```

Live evidence: `data/structure_v2/context_policy/smoke_results.json`.
The next application step is routing/clarification and a context packer for
source-bound LLM generation, alongside stronger validity/label review and
reranker latency work. FastAPI/SSE, UI and operational requirements remain open.
