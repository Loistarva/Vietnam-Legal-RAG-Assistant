"""Environment-backed configuration for the Streamlit prototype."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date


MIN_AS_OF_DATE = date(1945, 1, 1)
MAX_AS_OF_DATE = date(2046, 12, 31)


@dataclass(frozen=True)
class UIConfig:
    local_api_url: str
    cloud_api_url: str
    mock_url: str
    api_key: str
    request_timeout_seconds: float


def load_config() -> UIConfig:
    """Load API settings without placing credentials in source control."""
    timeout_value = os.getenv("LEGAL_RAG_REQUEST_TIMEOUT_SECONDS", "180")
    try:
        timeout = float(timeout_value)
    except ValueError as exc:
        raise ValueError("LEGAL_RAG_REQUEST_TIMEOUT_SECONDS phải là số.") from exc
    if timeout <= 0:
        raise ValueError("LEGAL_RAG_REQUEST_TIMEOUT_SECONDS phải lớn hơn 0.")
    return UIConfig(
        local_api_url=os.getenv(
            "LEGAL_RAG_LOCAL_API_URL", "http://127.0.0.1:8000/api/v1/ask"
        ).strip(),
        cloud_api_url=os.getenv("LEGAL_RAG_API_URL", "").strip(),
        mock_url=os.getenv("LEGAL_RAG_MOCK_URL", "").strip(),
        api_key=os.getenv("LEGAL_RAG_API_KEY", ""),
        request_timeout_seconds=timeout,
    )
