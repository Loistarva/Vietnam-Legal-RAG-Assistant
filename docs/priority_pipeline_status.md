# Priority data and retrieval baseline — 2026-11-12

## Three-model dense Dev comparison completed

All runs use the same 1,079-chunk fixture, 638 eligible chunks under the current
expiry filter, and the same ten supporting-clause Dev judgments. All three
tokenizer audits pass. Input hashes, per-query macro scores, Top-10 ID existence,
uniqueness and exclusion of fully expired evidence were checked independently.

| Model | Recall@5 | MRR@10 | Labelled evidence Top-1 |
|---|---:|---:|---:|
| BKAI | 0.90 | 0.85 | 8/10 |
| AITeamVN | 1.00 | 1.00 | 10/10 |
| BGE-M3 | 1.00 | 1.00 | 10/10 |

See `docs/dense_dev_comparison.md` and
`embedding/results/priority_dense_dev_comparison.json` for timings, observed
model snapshot revisions and recomputed rankings. New runs also record package
versions/device. The ten questions remain assistant-reviewed, not human-approved
or exhaustive relevance labels. No Test query was run or modified. No production
model winner is declared from this small development set.

**Next priority:** repair article/appendix/footer boundaries in ND01 and ND04.
In the BGE smoke result, ND01 appendix items appear as Article 67 clauses;
the appendix describes customs to eliminate/prohibit and must retain that scope.
Review candidate relevance labels separately, then freeze a corrected corpus
and judgment version before hybrid retrieval or final Test evaluation. Baseline
scores and labels are preserved rather than edited after viewing rankings.

## Provisional Dev baseline completed

All 10 Dev questions were reviewed against their supporting corpus chunks and
parser clause excerpts before retrieval. Three queries were clarified to match
the source scope; the 40 Test labels were not edited or evaluated. The reviewed
file is `embedding/data/priority_bkai_dev.support_reviewed.json`; its manifest
records input/output hashes and explicitly keeps human review pending.

BKAI successfully embedded and ingested all **1,079 points**. The existing
filter excludes fully expired documents, leaving **638 eligible chunks**;
partially expired and unknown-status documents remain eligible.
On the fixed supporting-clause labels: **Recall@5 = 0.90**, **MRR@10 = 0.85**,
mean query embedding plus vector search **45.14 ms** (not full request latency).
See `docs/bkai_dev_baseline.md` and the corresponding results/context JSONs.

One labelled clause was not retrieved in Top-10, but its Top-1 alternative
Article 69(1) also supports the question. Labels and scores remain unchanged;
this exposes incomplete relevance judgments requiring review rather than
proving a total evidence-retrieval failure. These are provisional Dev results,
not a production legal-accuracy measurement or independent human validation.
Next: review candidate relevance labels, fix parser structure/validity issues
and compare models using one frozen Dev corpus/judgment version. Reserve Test.

## Token-safe derivative — current embedding input

Use `embedding/data/priority_bkai_chunks.json` with its matching
`priority_bkai_dev.draft.json` / `priority_bkai_test.draft.json` labels.
The original 1,066-record fixture remains preserved for provenance.
Exactly 11 oversized original records were split, producing **1,079 chunks**.
All 50 draft questions are remapped through `priority_bkai_id_map.json`;
labels remain drafts. Current queries target L01, so their relevant IDs were
unchanged (the split chunks belong to ND02 and ND04).

The splitter measures full context plus body after BKAI underthesea
preprocessing, including tokenizer special tokens. Each segment repeats its
document/chapter/article header. Long intros are split as content rather than
repeated without a bound. Source fields and clause parent links are retained.
Offsets and ID mapping allow exact reconstruction of each original text.
Existing parser contamination (notably appendix/footer content inside ND04
Article 26) is preserved and still requires structural review; token compliance
does not certify legal correctness.

Dataset SHA-256: `79b4a7085e80142f6aad6703a5f53781f73cd998626f36f97ec84daa914c5cc5`.
The independent BKAI audit is `embedding/results/priority_bkai_token_safe_audit.json`.
It confirms **zero oversized inputs**, maximum **256 tokens**, over all 1,079
records. Six regression tests pass (including full-corpus content reconstruction,
metadata preservation and remapped-label/hash validation). Rebuilding the
derivative twice produced the same dataset SHA-256; `git diff --check` passes.

```powershell
$env:HF_HOME = "$PWD\.venv-embedding\hf-cache"
.\.venv-embedding\Scripts\python.exe embedding/fit_token_budget.py
.\.venv-embedding\Scripts\python.exe embedding/audit_token_limits.py --chunks embedding/data/priority_bkai_chunks.json --model bkai-foundation-models/vietnamese-bi-encoder --output embedding/results/priority_bkai_token_safe_audit.json
.\.venv-embedding\Scripts\python.exe -m unittest discover -s test -p test_token_budget.py
```

Next provisional Dev benchmark (after reviewing labels and source limitations):

```powershell
.\.venv-embedding\Scripts\python.exe embedding/retrieval_smoke_test.py --chunks embedding/data/priority_bkai_chunks.json --ground-truth embedding/data/priority_bkai_dev.draft.json --model bkai-foundation-models/vietnamese-bi-encoder --results embedding/results/priority_bkai_dev_draft.json
```

Use this same derivative fixture and matching labels for cross-model comparisons;
each other model still needs its own tokenizer audit. The provisional BKAI
Dev run completed later is described at the top of this document.

## Official-source refresh (supersedes the original snapshot below)

The refreshed export has **398 articles, 986 clauses and 1,066 chunks**.
L01 now contains Articles 1–133. Articles 132–133 were transcribed from page
43 of the signed official PDF and retain the PDF path, URL, page and SHA-256.
The legacy PDF and validated parser inputs were preserved. Raw extracted
metadata is retained alongside corrected metadata for auditability.

Corrections and supporting URLs are in `data/verified_legal_sources.json`:

| Document | Result |
|---|---|
| L01 / 52/2014/QH13 | Effective date corrected to 2015-01-01; official status page reports effective. |
| L02 / 22/2000/QH10 | Expired 2015-01-01. |
| ND01 / 126/2014/NĐ-CP | Partially expired; article-level validity mapping still required. |
| ND02 / 207/2025/NĐ-CP | Official status page reports effective. |
| ND03 / 01/2024/NQ-HĐTP | Issuing body/title corrected; current status remains unconfirmed. Export has 12 articles; completeness comparison against the official download remains pending. No missing article count is inferred from secondary websites. |
| ND04 / 10/2015/NĐ-CP | Expired 2025-10-01, replaced by 207/2025/NĐ-CP; title corrected. |
| ND05 / 70/2001/NĐ-CP | Expired 2015-02-15; issuing body/title corrected. |

Do not use the entire benchmark corpus as currently effective law. Historical
documents remain in the research fixture; production retrieval must enforce
validity rules, and partially expired documents need article-level review.
Metadata corrections do not certify the accuracy or amendment consolidation
of every article body. Question labels remain drafts requiring human review.

Refresh generated exports with the bundled Python interpreter (pydantic and
pdfplumber required), then regenerate the fixture and labels:

```powershell
python parser/refresh_verified_export.py
node embedding/prepare_priority_dataset.cjs
node embedding/build_priority_questions.cjs
python -m unittest discover -s test -p test_verified_sources.py
node --test test/priority_dataset.test.cjs
```

Four source-overlay regression tests and four Node integrity tests pass.
Updated fixture SHA-256: `871045104e89ac2806d8d9cca0db2a1794ca26ce10b72a05036a6574149539e1`.
The previous hash/results below describe the original pre-correction snapshot.

### Embedding environment and measured token limits

Python 3.12.14 environment `.venv-embedding` now has the embedding and BKAI
dependencies installed. `pip check` passes. Exact installed versions are
recorded in `embedding/requirements-priority-lock.txt`; model cache is local
inside the ignored virtual environment directory.

BKAI tokenizer audit ran on all **1,066 chunks**: **11 exceed 256 tokens**,
with a maximum of **704 tokens**. IDs and lengths are recorded in
`embedding/results/priority_bkai_token_audit.json`, bound to the fixture hash.
These inputs must be split without content loss before the BKAI dense
benchmark. The fail-fast embedding guard prevents silent truncation.
No Recall/MRR benchmark is claimed. Other model tokenizers remain to be checked.

```powershell
$env:HF_HOME = "$PWD\.venv-embedding\hf-cache"
.\.venv-embedding\Scripts\python.exe embedding/audit_token_limits.py --model bkai-foundation-models/vietnamese-bi-encoder --output embedding/results/priority_bkai_token_audit.json
```

## Original snapshot — before official-source corrections

- Current `data/chunking_output` contains 7 documents, 396 articles, 984 clauses and 1,064 chunks.
- `node embedding/prepare_priority_dataset.cjs` validates semantic IDs, clause/chunk parent links, duplicate IDs, JSONL/document agreement, source PDF existence, character counts and exact clause body reconstruction after whitespace normalization.
- No detected errors in those checks. This does not validate PDF extraction accuracy or legal correctness.
- Frozen embedding input: `embedding/data/priority_chunks.json`. It uses the new clause chunks rather than the older hierarchical smoke fixture. Raw text is retained; preprocessing belongs to each model. These two chunking approaches must not be treated as the same experiment.
- `node embedding/build_priority_questions.cjs` creates 50 draft questions with source clause excerpts, 10 Dev / 40 Test, with articles kept in only one split. Queries target L01; the other six documents are retrieval distractors. Labels are supporting clauses, not exhaustive judgments. Human review is pending.
- Embedding now fails explicitly on tokenizer overflow instead of silently truncating legal text. Benchmark output includes per-query rankings/metrics and ground-truth hash.

## Unresolved gates

- L01 effective date conflicts: current export says `2025-07-01`, normalized metadata says `2015-01-01`. Neither was automatically promoted as verified.
- L01 and ND01–ND05 have unknown validity status. Authoritative verification remains required; file existence alone does not verify provenance or current legal effect.
- L01 export stops at Article 131; Articles 132–133 are absent. No text has been synthesized.
- Model-tokenizer limits have not been measured. Character-based splitting does not establish token compliance. The new overflow guard may reject the fixture; split and regenerate labels before rerunning if necessary.
- Python is not available through `python` or `py` in the current PATH. A bundled interpreter was found at `C:/Users/ADMIN/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`. Both modified Python modules passed AST parsing there. It has pydantic/pdfplumber but lacks sentence-transformers, qdrant-client and pytest. The attempted BGE-M3 Dev run exits with the missing sentence-transformers dependency error before encoding. Recall/MRR remain unmeasured; no successful result file was produced.
- The dataset was rebuilt twice with identical SHA-256 `3afda7e27a860ea8d5fa18eeb4272236f7bc728d824a72740b3dc86dc852997b`. Four Node integrity tests pass, including deliberate content-loss and parent-link corruption. `git diff --check` passes.

## Reproduce validation

```powershell
node embedding/prepare_priority_dataset.cjs
node embedding/build_priority_questions.cjs
node --test test/priority_dataset.test.cjs
```

Before publishing benchmark results, review all question labels against source text, resolve metadata/completeness issues and record reviewed dataset hashes. Do not tune on the Test split.

Once Python 3.12 and requirements are available, run the draft Dev benchmark first (provisional results only):

```powershell
python embedding/retrieval_smoke_test.py --chunks embedding/data/priority_chunks.json --ground-truth embedding/data/priority_dev.draft.json --model BAAI/bge-m3 --results embedding/results/priority_bge_m3_dev_draft.json
```

Use the same fixture and query file for all three supported models. Preserve earlier smoke results. Run Test only after Dev configuration is fixed and labels reviewed.
