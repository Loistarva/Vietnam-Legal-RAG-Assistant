"""Deterministic redaction of synthetic/tested patterns, not general PII detection."""
from __future__ import annotations

import math
import re
from collections.abc import Iterable
from typing import Any

_EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_PHONE = re.compile(r"(?<!\w)(?:\+84|0084|0)(?:[ .()-]*\d){8,10}(?!\w)")
_ID = re.compile(r"(?<!\w)(?:\d{12}|\d{9})(?!\w)")
_BEARER = re.compile(r"(?i)\bBearer\s+[^\s,;\"']+")
_ASSIGNMENT = re.compile(r"(?i)\b(?:api[_ -]?key|access[_ -]?token|password|secret)\s*[:=]\s*[^\s,;]+")
_TOKEN = re.compile(r"\b(?:sk-|sk_|hf_|ghp_|github_pat_|glpat-)[A-Za-z0-9_-]{8,}\b")
_SECRET_KEYS = {"authorization", "proxyauthorization", "apikey", "xapikey", "token", "accesstoken",
                "refreshtoken", "password", "secret", "cookie", "setcookie", "environment", "env",
                "headers", "requestheaders", "responseheaders", "environ"}
_RAW_KEYS = {"query", "prompt", "rawprompt", "rawquery", "answer", "answerdraft", "content",
             "chunktext", "rawresponse", "headers", "requestbody", "responsebody", "querytext",
             "prompttext", "answertext", "evidencetext", "rawbody"}


def key_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


class PIIMasker:
    def __init__(self, *, secret_values: Iterable[str] = (), debug: bool = False):
        self.debug = debug
        self._secrets = tuple(sorted({s for s in secret_values if isinstance(s, str) and s}, key=len, reverse=True))

    def mask_text(self, text: str) -> str:
        for secret in self._secrets:
            text = text.replace(secret, "[SECRET]")
        for pattern, replacement in [(_BEARER, "Bearer [SECRET]"), (_ASSIGNMENT, "[SECRET]"),
                                     (_TOKEN, "[SECRET]"), (_EMAIL, "[EMAIL]"),
                                     (_PHONE, "[PHONE]"), (_ID, "[ID]")]:
            text = pattern.sub(replacement, text)
        return text

    def sanitize(self, value: Any, *, _depth: int = 0) -> Any:
        if _depth > 12:
            return "[DEPTH_LIMIT]"
        if value is None or type(value) in (bool, int):
            return value
        if isinstance(value, float):
            return value if math.isfinite(value) else None
        if isinstance(value, str):
            return self.mask_text(value)
        if isinstance(value, dict):
            out = {}
            for key, item in value.items():
                if not isinstance(key, str):
                    continue
                normalized = key_name(key)
                if normalized in _SECRET_KEYS or any(s in normalized for s in
                                                      ("authorization", "password", "apikey", "secret", "token", "cookie", "environ")):
                    # Token usage/count metadata carries metrics, not credentials.
                    if normalized not in {"tokeninput", "tokenoutput", "tokenusage", "totaltokens"}:
                        continue
                if not self.debug and normalized in _RAW_KEYS:
                    continue
                out[self.mask_text(key)] = self.sanitize(item, _depth=_depth + 1)
            return out
        if isinstance(value, (list, tuple)):
            return [self.sanitize(item, _depth=_depth + 1) for item in value]
        # Never serialize repr/str of arbitrary objects or exception values.
        return "[UNSUPPORTED_VALUE]"
