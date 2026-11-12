# Grounding and hallucination event taxonomy

| Code | Meaning | Recovery eligibility |
|---|---|---|
| `citation_invalid` | Empty/malformed selected indices or inline reference omitted from selection | Eligible for bounded regeneration |
| `unsupported_evidence_index` | Selected or numeric inline citation is outside context | Eligible for bounded regeneration |
| `duplicate_evidence_index` | Selected index occurs more than once | Eligible for bounded regeneration |
| `context_mismatch` | Evidence and source map identities/text/dates differ or indices collide | Never repair with LLM |
| `citation_metadata_missing` | Citation lacks required source metadata | Fix upstream context |
| `context_invalid` | Malformed context/date | Fix upstream context |
| `temporal_metadata_invalid` | Missing/invalid effective date or reversed interval | Fix upstream metadata |
| `evidence_not_effective` | Evidence interval excludes supplied as_of_date | Fix upstream retrieval |
| `retrieval_empty` | No evidence supplied | Clarify/abstain, no generation |
| `low_confidence` | Producer reports evidence below its frozen threshold | Clarify/abstain, no generation |
| `json_invalid` | Invalid LLM response shape, fabricated citation fields or blank draft | Eligible for bounded regeneration |
| `llm_incomplete` | Truncated/unfinished model output | Eligible for bounded regeneration |
| `gate_fail` | Orchestrator declines release | Orchestrator policy |

`retryable` is an eligibility hint, not an instruction to call a model. Dev 5
owns bounded recovery (at most one extra attempt when its policy permits it),
final abstention and preventing draft streaming. Dev 1 never executes retries.

`hallucination_flag` defaults to null, with `hallucination_source=null`. Citation
failure or PASS does not establish semantic hallucination/faithfulness. Labels
are retained only with `human_rubric`, or `verifier:<id>` explicitly included in
the logger's `approved_verifiers`. The human rubric owner supplies the assessment;
the logger cannot authenticate a rater's judgment. No verifier is enabled here.
Other claimed sources are reset to null. Summaries keep unassessed counts separate.
