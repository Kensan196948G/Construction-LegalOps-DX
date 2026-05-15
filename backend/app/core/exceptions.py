"""Custom exceptions and RFC 7807 Problem Details handlers."""

from __future__ import annotations

from typing import Any, Final

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

logger = get_logger(__name__)

_PROBLEM_BASE_URI: Final[str] = "https://legalops.example.co.jp/errors"
_PROBLEM_CONTENT_TYPE: Final[str] = "application/problem+json"


# ---------------------------------------------------------------------------
# Custom exception hierarchy
# ---------------------------------------------------------------------------


class AppError(Exception):
    """Base application exception. All custom errors subclass this."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    title: str = "Internal Server Error"
    type_slug: str = "internal-server-error"

    def __init__(
        self,
        detail: str | None = None,
        *,
        errors: list[dict[str, Any]] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.detail = detail or self.title
        self.errors = errors or []
        self.extra = extra or {}
        super().__init__(self.detail)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    title = "Not Found"
    type_slug = "not-found"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    title = "Conflict"
    type_slug = "conflict"


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    title = "Forbidden"
    type_slug = "forbidden"


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    title = "Unauthorized"
    type_slug = "unauthorized"


class ValidationError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    title = "Validation Error"
    type_slug = "validation"


class AIServiceError(AppError):
    status_code = status.HTTP_502_BAD_GATEWAY
    title = "AI Service Error"
    type_slug = "ai-service"


class AuditLogTamperError(AppError):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    title = "Audit Log Tamper Detected"
    type_slug = "audit-log-tamper"


class RateLimitError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    title = "Too Many Requests"
    type_slug = "rate-limit"


# ---------------------------------------------------------------------------
# Problem Details builder
# ---------------------------------------------------------------------------


def _problem_response(
    *,
    request: Request,
    status_code: int,
    title: str,
    type_slug: str,
    detail: str,
    errors: list[dict[str, Any]] | None = None,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    """Build an RFC 7807 Problem Details JSON response."""
    request_id = getattr(request.state, "request_id", None)
    body: dict[str, Any] = {
        "type": f"{_PROBLEM_BASE_URI}/{type_slug}",
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": str(request.url.path),
    }
    if errors:
        body["errors"] = errors
    if request_id:
        body["request_id"] = request_id
    if extra:
        body.update(extra)

    return JSONResponse(
        status_code=status_code,
        content=body,
        media_type=_PROBLEM_CONTENT_TYPE,
    )


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def app_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handler for :class:`AppError` and subclasses."""
    if not isinstance(exc, AppError):  # defensive — typing safeguard
        return await unhandled_exception_handler(request, exc)
    logger.warning(
        "app_error",
        error_type=type(exc).__name__,
        status=exc.status_code,
        detail=exc.detail,
    )
    return _problem_response(
        request=request,
        status_code=exc.status_code,
        title=exc.title,
        type_slug=exc.type_slug,
        detail=exc.detail,
        errors=exc.errors or None,
        extra=exc.extra or None,
    )


async def http_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Handler for Starlette / FastAPI :class:`HTTPException`."""
    if not isinstance(exc, StarletteHTTPException):
        return await unhandled_exception_handler(request, exc)
    title = {
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        405: "Method Not Allowed",
        409: "Conflict",
        415: "Unsupported Media Type",
        429: "Too Many Requests",
    }.get(exc.status_code, "HTTP Error")
    return _problem_response(
        request=request,
        status_code=exc.status_code,
        title=title,
        type_slug=f"http-{exc.status_code}",
        detail=str(exc.detail) if exc.detail else title,
    )


async def validation_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Handler for FastAPI :class:`RequestValidationError`."""
    if not isinstance(exc, RequestValidationError):
        return await unhandled_exception_handler(request, exc)
    field_errors: list[dict[str, Any]] = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err.get("loc", ()) if part != "body")
        field_errors.append(
            {
                "field": loc or "body",
                "message": err.get("msg", "invalid"),
                "type": err.get("type", "value_error"),
            }
        )
    return _problem_response(
        request=request,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        title="Validation Error",
        type_slug="validation",
        detail="Request payload failed validation.",
        errors=field_errors,
    )


async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Catch-all for unexpected exceptions. Never leaks internals."""
    logger.exception(
        "unhandled_exception",
        error_type=type(exc).__name__,
    )
    return _problem_response(
        request=request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        title="Internal Server Error",
        type_slug="internal-server-error",
        detail="An unexpected error occurred. Please contact support if it persists.",
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the FastAPI app."""
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)


__all__ = [
    "AIServiceError",
    "AppError",
    "AuditLogTamperError",
    "ConflictError",
    "ForbiddenError",
    "NotFoundError",
    "RateLimitError",
    "UnauthorizedError",
    "ValidationError",
    "register_exception_handlers",
]
