"""Error body for requests that never reach the pipeline (auth, invalid body, server fault).

A request that reaches the pipeline always gets an ``AskResponse`` (contract), also for
``status=ERROR``. ``ApiError`` reuses the contract ``ErrorCode`` values; it carries no
exception text, traceback, header or request body.
"""
from __future__ import annotations

from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from api.security.api_key_guard import AuthError
from orchestration.ask_service import InvalidAskRequest, RoutingFailed, new_query_id
from orchestration.events import StageEmitter
from schemas.models import SCHEMA_VERSION, ErrorCode, SchemaVersionType

# AskResponse.status=ERROR -> HTTP status
ERROR_HTTP_STATUS: dict[str, int] = {"LLM_TIMEOUT": 504, "LLM_UNAVAILABLE": 503, "INTERNAL_ERROR": 500}


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


def router_input_details(exc: InvalidAskRequest) -> list[ValidationDetail]:
    """Router ``INVALID_*`` reason -> one 422 detail; the message never echoes the input."""
    field = "as_of_date" if exc.reason_code == "INVALID_AS_OF_DATE" else "query"
    return [ValidationDetail(loc=["body", field], msg="Router từ chối đầu vào", type=exc.reason_code)]


def _rejection(request: Request, status_code: int, code: ErrorCode, message: str, *,
               details: list[ValidationDetail] | None = None) -> JSONResponse:
    query_id = getattr(request.state, "query_id", None) or new_query_id()
    service = request.app.state.ask_service
    if service is not None:
        StageEmitter(query_id, service.sink).emit("api", "request_rejected", "error", http_status=status_code,
                                                error_code=code)
    headers = {"X-Query-ID": quote(query_id, safe="")}
    if status_code == 401:
        headers["WWW-Authenticate"] = "ApiKey"
    return error_response(status_code, code, message, query_id=query_id, details=details, headers=headers)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AuthError)
    async def _auth(request: Request, exc: AuthError) -> JSONResponse:
        return _rejection(request, exc.status_code, "AUTH_REQUIRED", exc.message)

    @app.exception_handler(RequestValidationError)
    async def _invalid(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _rejection(request, 422, "INVALID_REQUEST", "Request không hợp lệ", details=_validation_details(exc))

    @app.exception_handler(InvalidAskRequest)
    async def _router_invalid(request: Request, exc: InvalidAskRequest) -> JSONResponse:
        return _rejection(request, 422, "INVALID_REQUEST", "Request không hợp lệ",
                          details=router_input_details(exc))

    @app.exception_handler(RoutingFailed)
    async def _routing_failed(request: Request, exc: RoutingFailed) -> JSONResponse:
        return _rejection(request, 500, "INTERNAL_ERROR", "Hệ thống gặp lỗi khi xử lý request")

    @app.exception_handler(Exception)
    async def _internal(request: Request, exc: Exception) -> JSONResponse:
        return _rejection(request, 500, "INTERNAL_ERROR", "Hệ thống gặp lỗi khi xử lý request")


__all__ = ["ApiError", "ERROR_HTTP_STATUS", "ValidationDetail", "error_response", "install_error_handlers",
           "router_input_details"]
