# Week 10: Dev 1 only

Source: user-supplied Week 10 V1.0 plan, section 5.1, D1.1–D1.5. This supersedes
the broad project roadmap for this work. Existing API/provider/retrieval code is
left untouched. No UI, new gateway, evaluator, Router tuning or Gate orchestration
is part of this delivery. The plan's claimed Week 9 canonical validator/logger
was not present in this branch; the existing `agent.validate_selection` validates
source-only excerpts and is preserved for its existing consumer.

## D1.1 validator interface

```python
from grounding.citation_validator import validate
result = validate(context_payload, llm_response)
```

The function accepts dict/model-dump inputs. Evidence uses positive integer
`evidence_index`; `source_map` maps the same index (integer or JSON decimal string)
to a complete trusted EvidenceItem. Complete fixtures are generated in
`reports/week10/dev1_handoff.json`. No `E1` source-selection format is silently
coerced into the Week 10 contract; Dev 3/5 own that explicit boundary adaptation.

The validator checks index membership/duplicates, complete source identities,
matching evidence text, citation metadata, dates and numeric `[n]` inline
references. It rejects fabricated `citations` response fields. Metadata comes
only from the trusted context, never from model prose. FAIL returns no draft or
citations. The complete supplied context is checked, even unselected evidence.
Dates use `effective_from <= as_of_date < effective_to`, with null `effective_to`
meaning an open interval supplied by the producer. This exclusive-end convention
needs confirmation at contract freeze. The validator cannot prove the producer's
metadata/source authenticity, amendments, article-level validity, or claim truth.
It does not fetch law or replace Dev 4's temporal retrieval.

## D1.2–D1.5 logger, privacy, taxonomy and QA

```python
from monitoring import StructuredLogger
from monitoring.integration import RequestTrace

logger = StructuredLogger('logs/runtime/requests.jsonl', enabled=True)
trace = RequestTrace('opaque-request-uuid', logger.emit,
                     {'model_version': 'your-frozen-version'})
with trace.stage('citation'):
    result = validate(context_payload, llm_response)
trace.record('citation', 'validation_completed', result['status'], {
    'grounding_status': result['status'],
    'violation_codes': result['violation_codes'],
    'citations': result['citations'],
})
```

Set `enabled=False` to disable writes. Dev 5 must use the same opaque query_id
for every callback. `trace.stage` observes the call; it does not decide Gate
release or catch business errors. No live API integration is claimed.

- [Log schema](../monitoring/log_schema.md)
- [Error and hallucination taxonomy](../monitoring/error_taxonomy.md)
- [Privacy policy candidate and limits](privacy/logging_policy.md)
- [QA evidence and remaining sign-off dependencies](../reports/week10/logging_qa.md)

Run from the repository root:

```powershell
& .\.venv-embedding\Scripts\python.exe -m unittest test.test_citation_validator test.test_pii_masker test.test_structured_logger -v
& .\.venv-embedding\Scripts\python.exe -m monitoring.validate_handoff
& .\.venv-embedding\Scripts\python.exe -m unittest discover -s test -p 'test_*.py'
```

No extra dependencies, API keys, model downloads, API or database services are
required for the Dev 1 tests/handoff. Test files follow the repo's flat `test/`
convention to keep its existing unittest discovery command working.
