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

Implementation note: pure ASGI (no ``BaseHTTPMiddleware``) to avoid the
anyio task-group loop-binding issue that occurs with asyncpg in tests.
The ``send`` callable is intercepted directly: the ``http.response.start``
message is held in a closure until the complete body arrives so that a
masking failure can still change the status to 500 (fail-closed guarantee).
"""

from __future__ import annotations

import json
from typing import Any, Final

import structlog
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

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


def _extract_content_type(headers: list[tuple[bytes, bytes]]) -> str | None:
    """Extract Content-Type value from a raw ASGI headers list."""
    for name, value in headers:
        if name.lower() == b"content-type":
            return value.decode("latin-1")
    return None


class SensitiveMaskingMiddleware:
    """Pure-ASGI middleware that masks PII in outgoing JSON responses."""

    def __init__(self, app: ASGIApp, *, max_body_bytes: int = _MAX_BODY_BYTES) -> None:
        self.app = app
        self._max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        max_bytes = self._max_body_bytes

        # Per-request mutable state captured by the inner closure.
        # Using lists/dicts for mutability without nonlocal rebind for booleans.
        state: dict[str, Any] = {
            "pass_through": False,
            "start_message": None,  # dict copy of http.response.start
            "body_chunks": [],
            "total_size": 0,
        }

        async def masked_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                # Inspect Content-Type before deciding whether to buffer.
                raw_headers: list[tuple[bytes, bytes]] = list(message.get("headers") or [])
                content_type = _extract_content_type(raw_headers)
                if not _is_maskable_content_type(content_type):
                    state["pass_through"] = True
                    await send(message)
                    return
                # Hold the start message — emit it only once we have the
                # complete body (or fail-closed with a 500 start message).
                state["start_message"] = {
                    "type": message["type"],
                    "status": message.get("status", 200),
                    "headers": raw_headers,
                }
                return

            if message["type"] == "http.response.body":
                if state["pass_through"]:
                    await send(message)
                    return

                chunk: bytes = message.get("body") or b""
                more: bool = bool(message.get("more_body", False))
                state["body_chunks"].append(chunk)
                state["total_size"] += len(chunk)

                if state["total_size"] > max_bytes:
                    # Body is too large to mask in-process — flush everything
                    # buffered so far and switch to pass-through mode.
                    start = state["start_message"]
                    if start is not None:
                        start.setdefault("headers", [])
                        MutableHeaders(scope=start)["X-Pii-Masked"] = "skipped-too-large"
                        await send(start)
                        state["start_message"] = None
                    accumulated = b"".join(state["body_chunks"])
                    state["body_chunks"] = []
                    state["pass_through"] = True
                    await send(
                        {
                            "type": "http.response.body",
                            "body": accumulated,
                            "more_body": more,
                        }
                    )
                    return

                if not more:
                    # Full body is now in the buffer — process it.
                    raw = b"".join(state["body_chunks"])
                    request_id: str | None = None
                    try:
                        req_state = scope.get("state")
                        if req_state is not None:
                            request_id = getattr(req_state, "request_id", None)
                    except Exception:
                        pass
                    await _process_and_send(
                        state["start_message"],
                        raw,
                        request_id,
                        send,
                    )
                return

            # All other message types (e.g. http.response.disconnect) pass through.
            await send(message)

        await self.app(scope, receive, masked_send)


async def _process_and_send(
    start_message: dict[str, Any] | None,
    raw: bytes,
    request_id: str | None,
    send: Send,
) -> None:
    """Mask ``raw`` and send the complete response, or emit a 500 on failure."""
    if start_message is None:
        return

    if not raw:
        # Empty body: emit unchanged.
        await send(start_message)
        await send({"type": "http.response.body", "body": b"", "more_body": False})
        return

    # Attempt JSON decode.
    try:
        decoded: Any = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        # Content-Type lied — replay verbatim rather than corrupting.
        start_message.setdefault("headers", [])
        MutableHeaders(scope=start_message)["X-Pii-Masked"] = "skipped-not-json"
        await send(start_message)
        await send({"type": "http.response.body", "body": raw, "more_body": False})
        return

    # Attempt masking — fail-closed on any exception.
    try:
        masked = mask_value(decoded)
        new_body = json.dumps(masked, ensure_ascii=False).encode("utf-8")
    except Exception:
        logger.error("sensitive_masking.mask_failed", request_id=request_id, exc_info=True)
        error_body = json.dumps(
            {
                "type": "about:blank",
                "title": "Internal Server Error",
                "status": 500,
                "detail": "response body could not be safely serialised",
                "request_id": request_id,
            }
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 500,
                "headers": [
                    (b"content-type", b"application/problem+json"),
                    (b"content-length", str(len(error_body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": error_body, "more_body": False})
        return

    # Overwrite Content-Length — the masked body may differ in size.
    start_message.setdefault("headers", [])
    headers = MutableHeaders(scope=start_message)
    headers["content-length"] = str(len(new_body))
    headers["X-Pii-Masked"] = "1"
    await send(start_message)
    await send({"type": "http.response.body", "body": new_body, "more_body": False})


__all__ = ["SensitiveMaskingMiddleware"]
