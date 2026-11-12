# Dev 1 logging privacy policy candidate — pending TL approval

The supplied branch has no approved masking policy artifact. The following rules
are implemented and tested on synthetic data; this is not a claim of policy or
privacy sign-off. Tech Lead must review this policy and Dev 3 must review any
external payload transformation before enabling an external experiment.

- Exclude query/prompt/evidence bodies, raw errors, headers and environments from
  the logger. Allow only documented metadata; use opaque correlation IDs.
- Remove nested authorization/cookie/API key/token/password/secret/environment
  fields. Replace explicitly supplied secret values, Bearer values, `sk-` key-like
  strings and common inline key assignments. Never copy originals to diagnostics.
- Replace email, Vietnamese phone-like strings and contiguous 9/12-digit ID-like
  patterns. Apply recursively, including numeric identifiers and metadata keys.
  These are synthetic pattern tests, not identity verification.
- Citation logs keep source identities/date metadata, not source text. Free-form
  text in allowlisted metadata still requires callers to avoid personal details.
- Production logs should use `logs/runtime/`, with access, retention, rotation and
  deletion controlled by the deployment owner. Samples in Git are synthetic only.

Known limitations: regex rules can miss names, addresses, foreign or obfuscated
numbers, spaced ID numbers and unknown secret formats; legal identifiers can
produce false positives. This module cannot certify arbitrary text is PII-free.
Python immutable strings are not securely erased from memory. Explicit secret
configuration is required for opaque values not recognized by patterns.

`mask_external_payload(payload, secrets=())` is a pure pre-call hook for Dev 3.
It returns a new value and does not issue an API call. It is **not wired into the
existing OpenAI adapter by Dev 1**, nor does it authorize Run C. Applying it can
alter legal text, so the owner must preserve/validate source mapping and assess
utility before enabling it. Log masking alone does not protect outbound payloads.

Local fixtures demonstrate masking and failure containment. TL policy approval,
Dev 3 outbound integration (conditional P1), and deployment retention enforcement
remain explicit handoff dependencies, outside Dev 1's standalone completion.
