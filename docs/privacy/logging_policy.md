# Logging privacy policy

Production logs record operational metadata rather than conversation content. Use the canonical LogEvent, the metadata allow-list and `StructuredLogger`; route all event destinations through the sanitized sink.

## Data handling

- Do not persist raw query/prompt, model draft/answer, evidence text, request/response body, headers, cookies or environment mappings in production logs.
- Drop Authorization, API-key, password, token and secret-bearing keys recursively. Preserve numeric token usage metrics only under their documented metric keys.
- Redact email, Vietnamese-style phone patterns, standalone 9/12-digit ID patterns, Bearer credentials, common token prefixes and secret assignments in string values. Redact configured secret values wherever they occur, including otherwise permitted metadata fields.
- Dev 5 supplies the actual configured API keys/other runtime secrets through `PIIMasker(secret_values=...)`. Do not dump environment variables to discover secrets, or include real secrets in examples/tests.
- Debug mode requires explicit `PIIMasker(debug=True)`. It may retain query/prompt/draft fields but applies the same masking. Keep it disabled for production and official evaluation unless an approved privacy procedure says otherwise.

The masker is deterministic pattern handling, not a general detector of names, addresses, every international phone format or arbitrary unconfigured credentials. Unknown sensitive values can escape pattern detection; omit raw text and pass actual secret values to the masker. A log cannot establish that source content is legally correct or that an answer is semantically grounded.

## Storage and incidents

Use a restricted local destination, one process per path. Keep real runtime logs outside Git; `logs/` remains ignored. The only versioned exception is the explicitly staged synthetic `logs/sample_request.jsonl`, generated from fake metadata and checked against the canonical schema.

The deployment owner sets access control, retention and rotation before enabling persistent logging. Do not interpret this module as approving production PII persistence. Health diagnostics carry fixed codes and counters, never raw exception text, event payload, destination path or credentials. Review queue drops/write failures using `stats`; logging failure must not change the user-facing answer.
