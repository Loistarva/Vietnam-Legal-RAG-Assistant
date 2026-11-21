"""HTTP client for the public FastAPI Ask contract."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import requests


class APIResponseError(ValueError):
    """The server returned a response that the UI cannot interpret."""


def _read_sse_response(
    response: requests.Response,
    on_status: Callable[[dict[str, Any]], None] | None,
) -> dict[str, Any]:
    """Consume status events and return the single contract-shaped final event."""
    event_name = "message"
    data_lines: list[str] = []
    final_payload: dict[str, Any] | None = None

    def dispatch() -> None:
        nonlocal event_name, data_lines, final_payload
        if not data_lines:
            event_name, data_lines = "message", []
            return
        try:
            event_data = json.loads("\n".join(data_lines))
        except json.JSONDecodeError as exc:
            raise APIResponseError("SSE chứa event JSON không hợp lệ.") from exc
        if not isinstance(event_data, dict):
            raise APIResponseError("SSE event phải chứa một JSON object.")
        if event_name == "status":
            if on_status:
                on_status(event_data)
        elif event_name == "final":
            final_payload = event_data
        elif event_name == "error":
            raise APIResponseError(
                str(event_data.get("message") or "API gặp lỗi trong khi stream.")
            )
        event_name, data_lines = "message", []

    for raw_line in response.iter_lines(decode_unicode=True):
        line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
        if not line:
            dispatch()
            continue
        if line.startswith(":"):
            continue
        field, separator, value = line.partition(":")
        if not separator:
            value = ""
        elif value.startswith(" "):
            value = value[1:]
        if field == "event":
            event_name = value
        elif field == "data":
            data_lines.append(value)
    dispatch()
    if final_payload is None:
        raise APIResponseError("SSE kết thúc mà không có event final.")
    return final_payload


def ask(
    question: str,
    *,
    api_url: str,
    api_key: str = "",
    as_of_date: str | None = None,
    session_id: str | None = None,
    request_id: str | None = None,
    timeout_seconds: float = 180,
    on_status: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Call POST /api/v1/ask; omit optional request fields when not supplied."""
    body: dict[str, str] = {"query": question}
    for key, value in (
        ("as_of_date", as_of_date),
        ("session_id", session_id),
        ("request_id", request_id),
    ):
        if value:
            body[key] = value

    headers = {"Accept": "application/json, text/event-stream"}
    if api_key:
        headers["X-API-Key"] = api_key
    response = requests.post(
        api_url,
        json=body,
        headers=headers,
        timeout=timeout_seconds,
        stream=True,
    )
    content_type = response.headers.get("Content-Type", "").casefold()
    if "text/event-stream" in content_type:
        return _read_sse_response(response, on_status)
    try:
        payload = response.json()
    except ValueError as exc:
        response.raise_for_status()
        raise APIResponseError("API không trả về JSON hợp lệ.") from exc
    if not isinstance(payload, dict):
        response.raise_for_status()
        raise APIResponseError("API response phải là một JSON object.")

    # Pipeline errors use AskResponse and must remain visible to the UI even
    # when FastAPI maps them to HTTP 5xx. Auth/validation errors use ApiError.
    if not response.ok and payload.get("status") != "ERROR":
        response.raise_for_status()
    return payload
