"""Contract error envelope: {"error": {code, message, retryable}, "request_id": ...}.

Messages are fixed, user-safe strings. Never include credentials, SQL or provider bodies.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.models import ApiErrorBody, ApiErrorResponse


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        request_id: str | None = None,
    ) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.retryable = retryable
        self.request_id = request_id


def _envelope(status: int, code: str, message: str, retryable: bool, request_id: str | None) -> JSONResponse:
    body = ApiErrorResponse(
        error=ApiErrorBody(code=code, message=message, retryable=retryable),
        request_id=request_id,
    )
    return JSONResponse(status_code=status, content=body.model_dump(mode="json"))


_HTTP_CODES = {401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return _envelope(exc.status_code, exc.code, exc.message, exc.retryable, exc.request_id)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, __: RequestValidationError) -> JSONResponse:
        # Do not echo submitted content back; it may contain patient text.
        return _envelope(422, "VALIDATION_ERROR", "The request does not match the API contract.", False, None)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_CODES.get(exc.status_code, "HTTP_ERROR")
        return _envelope(exc.status_code, code, "Request could not be completed.", False, None)
