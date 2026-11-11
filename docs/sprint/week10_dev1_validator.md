# Week 10 D1.1 - validator handoff

Baseline: `testing` at `cdca079`. Branch: `feature/week10-dev1-validator`.

## Interface retained from Week 9

```python
citations, invalid = map_evidence_indices_to_citations(llm.evidence_indices, context)
result = validate_citations(
    context, citations,
    evidence_indices=llm.evidence_indices,
    invalid_indices=invalid,
)
```

Use canonical models from `schemas.models`. Pass the exact context rendered into
the prompt, all original indices, and every mapper failure. Mapping remains with
the existing caller; API, provider, retry, answer emission and abstention policy
remain outside this validator. Gate must still reject malformed LLM output before
calling the validator, as in Week 9.

No Week 10 schema or new two-argument adapter is invented here. Once Dev 3 freezes
the shared contract, review its delta with Dev 5 before adapting the interface.
This is the remaining contract-dependent part of D1.1, not an approved schema.

## Checks and change

Existing checks cover selected-context membership, document/article/clause/chunk
and parent mapping, missing metadata, source-map consistency, duplicates, invalid
indices and mapper failures. FAIL returns no accepted citations; validation does
not repair inputs. PASS only certifies structural provenance, not semantic truth,
legal correctness or temporal validity.

New check `NON_CONTIGUOUS_CONTEXT_INDEX` rejects mutable payloads whose evidence
indices no longer follow the canonical ordered `[1]..[n]` prompt contract. It runs
after type/range and duplicate checks, before provenance checks. Existing reason
codes and the Week 9 public function signature are retained.

Added regressions cover gaps/order changes, missing citation/source-map metadata,
outside-context failure without input mutation, and validation with network calls
disabled. Synthetic PASS/FAIL outputs are in
`test/grounding/fixtures/week10_grounding_results.json`.

## Verification

```powershell
python -m pytest test/grounding/test_citation_validator.py test/orchestration/test_grounding_gate.py test/orchestration/test_evidence_index_mapping.py -q
git diff --check
```

No Qwen server, API, corpus change or Gold data is required.

Verified on 2026-11-11: **129 passed** across the three files above; `git diff
--check` passed. Runtime: Python 3.13. The host initially lacked PyYAML; PyYAML
6.0.3 and requests 2.34.2 were installed in a separate temporary dependency folder
and exposed through `PYTHONPATH`, without changing repository requirements or the
shared Python installation. The project's declared Python 3.12 runtime was not
available for this run.
