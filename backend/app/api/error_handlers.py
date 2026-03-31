from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


ERROR_CODES_BY_STATUS = {
    400: "bad_request",
    401: "unauthorized",
    402: "payment_required",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
}


def success_response(
    message: str,
    data: dict[str, Any] | list[Any] | None = None,
    legacy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": True,
        "message": message,
        "data": data if data is not None else {},
    }
    if legacy:
        payload.update(legacy)
    return payload


def error_response(status_code: int, error: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "ok": False,
            "error": error,
            "message": message,
        },
    )


def status_to_error_code(status_code: int) -> str:
    return ERROR_CODES_BY_STATUS.get(status_code, "request_error")


def extract_error_message(detail: Any) -> str:
    if isinstance(detail, str) and detail.strip():
        return detail.strip()
    if isinstance(detail, dict):
        for key in ("message", "detail", "error"):
            value = detail.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return "Request failed"


async def handle_http_exception(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    return error_response(
        status_code=exc.status_code,
        error=status_to_error_code(exc.status_code),
        message=extract_error_message(exc.detail),
    )


async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    message = "Invalid request payload"
    errors = exc.errors()
    if errors:
        first = errors[0]
        field = ".".join(str(item) for item in first.get("loc", ()) if item != "body")
        reason = first.get("msg", "invalid value")
        message = f"{field}: {reason}" if field else reason

    return error_response(
        status_code=422,
        error="validation_error",
        message=message,
    )


async def handle_unexpected_error(
    _: Request,
    exc: Exception,
    *,
    logger,
) -> JSONResponse:
    logger.exception("Unhandled exception while processing request: %s", exc)
    return error_response(
        status_code=500,
        error="internal_error",
        message="Internal server error",
    )
