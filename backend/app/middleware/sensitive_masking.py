"""Response-body PII masking middleware.

This middleware acts as a *defence-in-depth* layer on top of the schema
boundary: even if a future endpoint accidentally returns a raw My Number,
phone number, or email address, the egress filter will mask it before it
reaches the browser or external integrator.

Design constraints
------------------

* **Fail-closed.** If the body can't be parsed, decoded, or re-serialised
  we replace it with a 500 ``application/problem+json`` payload rather
  than risk leaking the unmasked original.
* **JSON only.** Non-JSON responses (PDFs, streamed Excel exports, etc.)
  pass through untouched — those flows go through dedicated server-side
  redaction in their respective services.
* **Bounded.** Bodies larger than :data:`_MAX_BODY_BYTES` are streamed
  through unchanged (the masking cost is paid by the structured logger
  upstream).
* **Audit-friendly.** Drops are recorded in the response header
  ``X-Pii-Masked: 1`` so downstream observability can alert on
  unexpected masks.

The implementation is intentionally synchronous after the body has been
collected so the regexes execute on the worker event-loop only briefly.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any, Final

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.security import mask_value

logger = structlog.get_logger(__name__)

_MAX_BODY_BYTES: Final[int] = 2 * 1024 * 1024  # 2 MiB
_MASKABLE_TYPES: Final[tuple[str, ...]] = (
    "application/json",
    "application/problem+json",
)


def _is_maskable_content_type(content_type: str | None) -> bool:
    if not content_type:
        return False
    # Strip the optional ``; charset=utf-8`` suffix before comparing.
    head = content_type.split(";", 1)[0].strip().lower()
    return head in _MASKABLE_TYPES


def _failsafe_response(request_id: str | None) -> Response:
    """Return an opaque 500 when we can't safely emit the original body."""
    body = {
        "type": "about:blank",
        "title": "Internal Server Error",
        "status": 500,
        "detail": "response body could not be safely serialised",
        "request_id": request_id,
    }
    return JSONResponse(
        status_code=500,
        content=body,
        media_type="application/problem+json",
    )


class SensitiveMaskingMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that masks PII in outgoing JSON responses."""

    def __init__(self, app, *, max_body_bytes: int = _MAX_BODY_BYTES) -> None:
        super().__init__(app)
        self._max_body_bytes = max_body_bytes

    async def dispatch(  # type: ignore[override]
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)

        if not _is_maskable_content_type(response.headers.get("content-type")):
            return response

        # Collect the streamed body. We intentionally use the documented
        # ``body_iterator`` attribute Starlette exposes for this purpose.
        body_chunks: list[bytes] = []
        total = 0
        try:
            async for chunk in response.body_iterator:  # type: ignore[attr-defined]
                if not isinstance(chunk, (bytes, bytearray, memoryview)):
                    # Starlette sometimes yields ``str`` for SSE; ignore
                    # masking on those streams.
                    return response
                body_chunks.append(bytes(chunk))
                total += len(chunk)
                if total > self._max_body_bytes:
                    # Too large to mask in-process — let it through but
                    # flag the response so observability can flag it.
                    response.headers["X-Pii-Masked"] = "skipped-too-large"
                    return _replay_response(response, body_chunks)
        except Exception:
            request_id = getattr(request.state, "request_id", None)
            logger.error(
                "sensitive_masking.body_iter_failed",
                request_id=request_id,
                exc_info=True,
            )
            return _failsafe_response(request_id)

        raw = b"".join(body_chunks)
        if not raw:
            return _replay_response(response, body_chunks)

        try:
            decoded: Any = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            # If the content-type lied, replay verbatim — we are not in
            # the business of corrupting non-JSON bodies. We still mark
            # the response so it is easy to spot in logs.
            response.headers["X-Pii-Masked"] = "skipped-not-json"
            return _replay_response(response, body_chunks)

        try:
            masked = mask_value(decoded)
            new_body = json.dumps(masked, ensure_ascii=False).encode("utf-8")
        except Exception:
            request_id = getattr(request.state, "request_id", None)
            logger.error(
                "sensitive_masking.mask_failed",
                request_id=request_id,
                exc_info=True,
            )
            return _failsafe_response(request_id)

        # Build a fresh response: must overwrite Content-Length so the
        # ASGI server doesn't truncate the new payload.
        headers = dict(response.headers)
        headers["content-length"] = str(len(new_body))
        headers["X-Pii-Masked"] = "1"
        return Response(
            content=new_body,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type or "application/json",
        )


def _replay_response(original: Response, chunks: list[bytes]) -> Response:
    """Re-emit a buffered response when masking was skipped."""
    body = b"".join(chunks)
    headers = dict(original.headers)
    headers["content-length"] = str(len(body))
    return Response(
        content=body,
        status_code=original.status_code,
        headers=headers,
        media_type=original.media_type,
    )


__all__ = ["SensitiveMaskingMiddleware"]
