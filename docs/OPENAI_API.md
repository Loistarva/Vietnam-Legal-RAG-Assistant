# OpenAI source selection and HTTP API

This stage connects the existing evidence agent to OpenAI Responses API. The model
selects source IDs under a strict JSON schema. The application validates those IDs
and renders original excerpts with citations. It does **not** generate free-form
legal advice; `answer_generated` remains false. This is deliberate pending a
separate grounded-answer implementation and evaluation.

## Local setup (PowerShell, repository root)

Install the retrieval environment as described in the existing embedding docs,
then install the HTTP/provider dependencies:

```powershell
& .\.venv-embedding\Scripts\python.exe -m pip install -r api/requirements.txt
```

The default is `LLM_PROVIDER=disabled`: retrieval and original excerpts work
without sending data to OpenAI. To enable OpenAI, set these variables locally:

```powershell
$env:LLM_PROVIDER = 'openai'
$env:LLM_MODEL_ID = '<model supporting Responses and strict JSON schema>'
$env:OPENAI_API_KEY = '<your local secret>'
$env:LLM_CONTEXT_WINDOW = '4096'
$env:LLM_OUTPUT_RESERVE = '512'
$env:LLM_MAX_ATTEMPTS = '1'
```

Use a context window no larger than your selected model's documented limit.
No model is selected implicitly. `.env.example` lists configuration, but the app
does not automatically load `.env`. Never commit real keys or paste them in chat.

Counting uses `client.responses.input_tokens.count` with the same model, messages,
schema and disabled truncation as generation. It sends question/source data to
OpenAI; packing can issue several count requests. A bounded in-process cache
avoids identical counts. Generation uses `store=False`, a fixed output reserve,
30-second SDK timeout and SDK retries disabled. At most one generation attempt
is made by default (two only when configured); invalid source selections never
widen retrieval. Refusals, malformed JSON and incomplete responses are rejected.
Provider outages return a generic unavailable result, without credential details.

Implementation references: [OpenAI token counting](https://developers.openai.com/api/docs/guides/token-counting)
and [structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs).

The optional `transformers_local` adapter requires an already cached chat model
and an exact 40-character `LLM_MODEL_REVISION`; it never downloads a model.

## Serve JSON and SSE

```powershell
& .\.venv-embedding\Scripts\python.exe -m uvicorn api.app:create_app --factory --host 127.0.0.1 --port 8000 --workers 1
```

`GET /health` reports process health, not model/index readiness. Models and the
existing Qdrant index load lazily on the first legal question. Greeting,
clarification and out-of-scope routes bypass model loading. The corpus hash and
existing index are verified before legal retrieval. Keep one worker for the
local Qdrant directory; model/index access is serialized.

Both `POST /chat` and `POST /chat/stream` accept only
`{"query":"Điều kiện kết hôn theo Luật số 52/2014/QH13?"}` (1–4,000 characters).
JSON returns the final gated result. SSE sends `status`, then a complete validated
`result` or generic `error`, then `done`. It does not stream unvalidated model
tokens. Clients must use a streaming POST client rather than browser EventSource.
Raw packed prompts are excluded from responses.

Set `LEGAL_RAG_API_KEY` to require `X-API-Key` on both chat endpoints; health is
public. With no API key this interface is intended for local development only.
There is no cross-origin configuration, distributed rate limit, shared cache,
multi-turn memory or production deployment in this stage.

## Validation and next stage

```powershell
& .\.venv-embedding\Scripts\python.exe -m unittest discover -s test -p 'test_*.py'
node --test test/priority_dataset.test.cjs
```

Provider tests inject a fake client and check count/generation payload parity,
budget rejection, bounded attempts, incomplete output and unavailable services.
HTTP tests check validation, authentication, SSE framing and sanitized failures.
Validated in the project environment: 70 Python tests and 4 Node data checks pass.
`python -m api.validate_http` also passes greeting, JSON legal retrieval and SSE
legal retrieval against the existing local index (OpenAI disabled); the report
is saved in `data/structure_v2/api/http_smoke.json`.
No paid OpenAI calls are made by these tests. Live OpenAI validation still requires
a locally configured key and compatible model. Next: run that live validation,
then implement/evaluate grounded answer synthesis before claiming legal answers.
