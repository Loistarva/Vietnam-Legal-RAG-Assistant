"""API Key Guard (Sprint 10 D5.4).

* Keys come from ``LEGAL_RAG_API_KEYS`` (comma-separated) in the environment or a secret
  store; nothing is hardcoded and ``.env.example`` only has a placeholder.
* Clients send ``X-API-Key`` (the header Dev 2's Streamlit client already uses).
* Missing key -> 401 ``AUTH_REQUIRED``; wrong key -> 403 ``AUTH_REQUIRED``. Both happen in
  a dependency, before the pipeline runs.
* Only SHA-256 digests are kept in memory and compared with ``hmac.compare_digest``; the key
  never goes into a response, a log event or an exception message.
"""
from __future__ import annotations

import hashlib
import hmac
from collections.abc import Iterable

from fastapi import Request, Security
from fastapi.security import APIKeyHeader

API_KEY_HEADER = "X-API-Key"
MIN_KEY_LENGTH = 16

api_key_header = APIKeyHeader(name=API_KEY_HEADER, auto_error=False,
                              description="API key cấp cho client (biến môi trường LEGAL_RAG_API_KEYS ở server).")


class AuthError(Exception):
    """Raised before the pipeline; ``api.errors`` turns it into an ``ApiError`` body."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _digest(key: str) -> bytes:
    return hashlib.sha256(key.encode("utf-8")).digest()


class ApiKeyGuard:
    def __init__(self, keys: Iterable[str]):
        cleaned = [key.strip() for key in keys if key and key.strip()]
        if not cleaned:
            raise ValueError("Chưa cấu hình API key: đặt LEGAL_RAG_API_KEYS (phân tách bằng dấu phẩy)")
        short = [key for key in cleaned if len(key) < MIN_KEY_LENGTH]
        if short:
            raise ValueError(f"API key phải dài ít nhất {MIN_KEY_LENGTH} ký tự ({len(short)} key quá ngắn)")
        self._digests = tuple(_digest(key) for key in cleaned)

    @classmethod
    def from_value(cls, value: str | None) -> "ApiKeyGuard":
        return cls((value or "").split(","))

    def check(self, presented: str | None) -> None:
        if presented is None or not presented.strip():
            raise AuthError(401, f"Thiếu header {API_KEY_HEADER}")
        candidate = _digest(presented.strip())
        # Compare against every key so the time does not depend on which one matched.
        matched = False
        for digest in self._digests:
            matched |= hmac.compare_digest(candidate, digest)
        if not matched:
            raise AuthError(403, "API key không hợp lệ")

    def __repr__(self) -> str:  # never print key material
        return f"ApiKeyGuard(keys={len(self._digests)})"


def require_api_key(request: Request, api_key: str | None = Security(api_key_header)) -> None:
    """FastAPI dependency; the guard lives on ``app.state.api_key_guard``."""
    guard: ApiKeyGuard = request.app.state.api_key_guard
    guard.check(api_key)


__all__ = ["API_KEY_HEADER", "ApiKeyGuard", "AuthError", "api_key_header", "require_api_key"]
