# Priority data and retrieval baseline — 2026-11-12

## Verified locally

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
