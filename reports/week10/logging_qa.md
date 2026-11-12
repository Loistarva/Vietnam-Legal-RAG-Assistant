# Dev 1 logging/validator QA — 2026-11-12

Scope: Week 10 plan §5.1, D1.1–D1.5. Tests use synthetic fixtures and an in-process
callback harness only. No personal data, real prompts, API keys, external API,
model inference, live API integration or database calls were used in this QA.

| Task | Evidence delivered | Status / dependency |
|---|---|---|
| D1.1 | `grounding/citation_validator.py`; PASS/FAIL fixtures; negative mapping/index/date/inline citation tests | Standalone implemented/tested; canonical contract sign-off pending Dev 3/TL |
| D1.2 | JSONL sink, UTC timestamp/event UUID, one query_id across all nine stages, version/latency/citation metadata | Standalone implemented/tested |
| D1.3 | Recursive masker, secret removal, raw body exclusion, security regression fixtures, pure external hook | Local rules tested; TL policy approval pending; external P1 hook integration belongs to Dev 3 |
| D1.4 | Stable structural codes; nullable semantic labels with source allowlist; separate summary counts | Implemented/tested; no semantic verifier or human scoring claimed |
| D1.5 | Callback/timing adapter, broken sink/callback tests, masked samples and commands | Standalone handoff tested; live orchestration callbacks pending Dev 5 |

Do not mark whole-project W10-05 or W10-08 signed off from these fixtures alone.
`schemas/models.py` and the Week 9 validator/logger described by the plan were
absent in this checkout. No replacement canonical schema or second Gate was
created. Existing source-selection validation remains untouched. Dev 3 owns
contract freeze and mapping; Dev 5 owns Gate release/recovery and live callbacks.

## Checks and artifacts

- 28 Dev 1 unit/security/callback tests pass; full suite: **98 Python tests pass**.
- Existing Node data checks: **4 pass**; `git diff --check` passes.
- Model/provider/API modules were not edited by this delivery.
- Valid fixture returns trusted mapped citations; invalid fixture returns FAIL,
  no validated draft and no citations. It does not execute a retry or stream.
- Empty context, untrusted index/type/duplicates, missing metadata, conflicting
  document/article/clause/text mapping, fabricated citation fields, incomplete
  output and expired/not-yet-effective intervals are rejected deterministically.
- Email/phone/ID-like patterns, nested credentials and custom secret fixtures do
  not survive masking. Raw query/prompt/header/error fields are excluded.
- Logging disabled, malformed events, non-finite values, failed sinks and throwing
  callbacks are contained. Business results and exceptions remain unchanged.
- Concurrent threads sharing one logger produce 40 complete parseable JSON lines.
- Structural failure never automatically creates a semantic hallucination label.

`python -m monitoring.validate_handoff` generates:

- `logs/sample_request.jsonl`: nine synthetic stage events with the same query ID.
- `logs/sample_gate_fail.jsonl`: synthetic failure handoff, no answer text.
- `reports/week10/dev1_handoff.json`: full synthetic inputs, GroundingResults,
  separate taxonomy statistics and a measured 100-record local-file logger
  p50/p95. Those timings are **logger emit only**, not API TTFB or answer latency;
  they establish no end-to-end NFR target. Re-running updates timings/timestamps.

Commands and interface examples: [Dev 1 handoff](../../docs/dev1_handoff.md).
Rules/limitations: [privacy policy candidate](../../docs/privacy/logging_policy.md).

## Handoff acceptance still needed

1. Dev 3/TL: freeze canonical ContextPayload, LLMResponse, GroundingResult and
   LogEvent; confirm positive integer indices/full source-map values, required
   fields and exclusive `effective_to` semantics. Run producer/consumer tests.
2. Tech Lead: approve the documented masking policy and runtime retention/access
   controls. Regex coverage is limited; fixtures do not certify arbitrary PII-free
   text. Runtime logs stay under ignored `logs/runtime/`.
3. Dev 5: consume validator/callback interfaces in the existing orchestrator,
   gate every draft, exercise at-most-one recovery and real fail-safe abstention,
   then collect actual query-correlated integration traces and stage/API timings.

These are integration/sign-off dependencies in the original Dev 1 assignment,
not new Dev 1 features or a request to implement another owner's modules.
