"""Error body for requests that never reach the pipeline (auth, invalid body, server fault).

A request that reaches the pipeline always gets an ``AskResponse`` (contract), also for
``status=ERROR``. ``ApiError`` reuses the contract ``ErrorCode`` values; it carries no
exception text, traceback, header or request body.
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from api.security.api_key_guard import AuthError
from schemas.models import SCHEMA_VERSION, ErrorCode, SchemaVersionType

# AskResponse.status=ERROR -> HTTP status
ERROR_HTTP_STATUS: dict[str, int] = {"LLM_TIMEOUT": 504, "INTERNAL_ERROR": 500}


class ValidationDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")
    loc: list[str | int]
    msg: str
    type: str


class ApiError(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: SchemaVersionType = SCHEMA_VERSION
    error_code: ErrorCode
    message: str = Field(..., min_length=1)
    query_id: str | None = None
    details: list[ValidationDetail] = Field(default_factory=list)


def error_response(status_code: int, code: ErrorCode, message: str, *, query_id: str | None = None,
                   details: list[ValidationDetail] | None = None, headers: dict[str, str] | None = None) -> JSONResponse:
    body = ApiError(error_code=code, message=message, query_id=query_id, details=details or [])
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"), headers=headers)


def _validation_details(exc: RequestValidationError) -> list[ValidationDetail]:
    # ``input``/``ctx`` are dropped: they can echo the question back.
    return [ValidationDetail(loc=[str(p) if not isinstance(p, int) else p for p in err.get("loc", ())],
                             msg=str(err.get("msg", "")), type=str(err.get("type", "")))
            for err in exc.errors()]


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AuthError)
    async def _auth(request: Request, exc: AuthError) -> JSONResponse:
        headers = {"WWW-Authenticate": "ApiKey"} if exc.status_code == 401 else None
        return error_response(exc.status_code, "AUTH_REQUIRED", exc.message, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def _invalid(request: Request, exc: RequestValidationError) -> JSONResponse:
        return error_response(422, "INVALID_REQUEST", "Request không hợp lệ", details=_validation_details(exc))

    @app.exception_handler(Exception)
    async def _internal(request: Request, exc: Exception) -> JSONResponse:
        query_id: Any = getattr(request.state, "query_id", None)
        return error_response(500, "INTERNAL_ERROR", "Hệ thống gặp lỗi khi xử lý request", query_id=query_id)


__all__ = ["ApiError", "ERROR_HTTP_STATUS", "ValidationDetail", "error_response", "install_error_handlers"]
