# Agent routing, budgeted context and source-only composition

This stage prepares source-grounded requests and renders verifiable excerpts.
It does **not** implement a configured real LLM provider or free-form legal
advice. No real generation API was called in the recorded validation.

## Implemented flow

1. `agent/routing.py` classifies social/nonlegal inputs, supported family-law
   topics, vague queries, mixed/unsupported domains and explicit historical
   validity requests. Social replies are static; vague/historical/mixed queries
   ask for clarification instead of invoking retrieval. These are conservative
   rules, not a trained or calibrated intent model.
2. `LegalAgent.prepare` preflights the base request budget **before** retrieval.
   Eligible legal requests use the existing strict evidence pipeline. No eligible
   evidence, oversized requests or whole sources that cannot fit lead to clear
   clarification states. Infrastructure/data errors are not disguised as missing
   user facts. Raw retrieval scores are not treated as legal confidence.
3. `ContextPacker` prefers a whole deduplicated article. If it cannot fit, it tries
   a whole parent clause, otherwise records that the source was omitted. It never
   slices legal text to force a fit. Article-level blocks have article-level
   citations rather than falsely citing one clause for every paragraph.
4. The packer counts the **full serialized message request**, including system
   instructions, question, source labels/text and citations, with an injected
   counter. A context-window budget reserves room for provider output. All source
   text is passed as data, not instructions.
5. `SourceGenerationStage` has a provider-neutral source-selection protocol. A
   provider may return only `selected_source_ids`; unknown/duplicate IDs or any
   free-form extra fields are rejected. The renderer prints canonical full source
   text and citation labels, never provider-written legal claims. Empty or invalid
   selection abstains. This is a source-ID/schema gate, **not** semantic entailment
   verification or a complete SRS Grounding Gate.

## Counter and provider contract

The offline demonstration uses the cached **BGE-M3 tokenizer as a planning
proxy**, with a 4,096-unit context budget and 512 reserved output units. Its count
is exact for that serialized proxy request, not for an unspecified generation
model/chat template. `provider_counter_configured` is false and real provider calls
are prohibited until a matching full-request counter and model ID are configured.
The reserve applies to the provider's short source-ID JSON response; full local
excerpt rendering is not an LLM output-token claim.

Implement `SourceSelectionProvider.model_id` and
`select_sources(messages, max_output_tokens)` to connect a selected service. Its
counter must include any additional chat/tool/schema framing actually sent. No
provider SDK, API credential or billed call is configured by this stage. Mock
providers are used only in unit tests. An adapter must not claim a real LLM answer
from the offline extractive fallback.

Without a provider, output has `selection_mode:
retrieval_order_extractive_fallback`, `llm_called: false`, `answer_generated:
false` and `extracts_rendered: true`. It is displayed as source excerpts for
comparison with the question, not a generated legal opinion. With a provider,
only validated source selections are rendered; model prose is never forwarded.

## Verification

- Eleven new tests check routing, bypassed retrieval, preflight rejection, whole
  article/clause packing, deduplication, citation scope, request budgets, source-ID
  rejection, mismatched counters, abstention and verbatim rendering.
- `agent.validate_agent_flow` runs seven local scenarios using the existing v2
  Qdrant/BGE evidence pipeline and cached tokenizer. Greeting, ambiguity, other
  domains, historical validity and oversized requests bypass retrieval. The
  supported legal request produces packed excerpts; an unknown-status source
  request clarifies. No generation API or Test query is evaluated.
- Evidence is saved in `data/structure_v2/agent/offline_flow.json`, including
  route decisions, budget/counter metadata, selected sources and explicit fallback
  flags. Long synthetic query text is omitted from the artifact.

```powershell
.\.venv-embedding\Scripts\python.exe -u -m agent.validate_agent_flow
python -m unittest discover -s test -p 'test_*.py'
node --test test/priority_dataset.test.cjs
```

## Remaining work

Choose/configure a real provider and its matching tokenizer/request counter;
evaluate provider source selection and then any proposed free-form answering
mode separately. Claim-level citation/entailment validation, calibrated evidence
confidence, bounded retry, multi-turn clarification, expanded human judgments and
historical/source validity work remain open. API/SSE, UI, Redis, authentication,
rate limiting and end-to-end acceptance remain open. The Test split is reserved.
