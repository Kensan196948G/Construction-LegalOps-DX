"""Application-layer rate limiting middleware.

The nginx reverse proxy already applies ``limit_req`` zones, but direct
backend access (e.g. inside the container network, k6 load tests, or a
misconfigured LB) bypasses it. This middleware enforces a second,
self-contained limit per client IP at the ASGI layer.

Design notes:

* Pure-ASGI implementation (no ``BaseHTTPMiddleware``) so it never triggers
  the asyncpg loop-binding issues seen with the previous middleware rewrite.
* Sliding-window counters are kept in memory. With 600 req/min per client
  and 10k clients this stays bounded for a 600-employee company; multi-replica
  deployments should additionally rely on the nginx/edge limits or a shared
  Redis-backed limiter (tracked in the operations backlog).
* Health/metrics/documentation endpoints are excluded so probes and
  monitoring never consume user quota.
* Auth endpoints get a stricter, dedicated limit (brute-force protection).
"""

from __future__ import annotations

import json
import time
from collections import defaultdict, deque
from typing import Final, cast

from starlette.types import ASGIApp, Receive, Scope, Send

_WINDOW_SECONDS: Final[int] = 60
_ALLOWLIST_PREFIXES: Final[tuple[str, ...]] = (
    "/health",
    "/healthz",
    "/readyz",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
    "/static",
)
_AUTH_PATH_MARKERS: Final[tuple[str, ...]] = ("/api/v1/auth", "/api/auth")

_TOO_MANY_BODY = json.dumps(
    {
        "type": "rate-limit",
        "title": "Too Many Requests",
        "status": 429,
        "detail": "Too Many Requests",
    }
).encode("utf-8")


class RateLimitMiddleware:
    """Sliding-window rate limiter keyed by client IP."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        enabled: bool = True,
        general_per_minute: int = 600,
        auth_per_minute: int = 60,
    ) -> None:
        self.app = app
        self.enabled = enabled
        self.general_limit = max(1, int(general_per_minute))
        self.auth_limit = max(1, int(auth_per_minute))
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def _client_key(self, scope: Scope) -> str:
        headers = cast("list[tuple[bytes, bytes]]", scope.get("headers") or [])
        for name, value in headers:
            if name.lower() == b"x-forwarded-for":
                first = value.split(b",", 1)[0].strip().decode("latin-1")
                if first:
                    return first
        client = cast("tuple[str, int] | None", scope.get("client"))
        if client and client[0]:
            return client[0]
        return "unknown"

    def _limit_for(self, path: str) -> int:
        return self.auth_limit if path.startswith(_AUTH_PATH_MARKERS) else self.general_limit

    def _is_exempt(self, path: str) -> bool:
        return path in {"/", ""} or path.startswith(_ALLOWLIST_PREFIXES)

    @staticmethod
    def _prune(window: deque[float], now: float) -> None:
        while window and now - window[0] > _WINDOW_SECONDS:
            window.popleft()

    async def _send_429(self, send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"retry-after", b"60"),
                    (b"cache-control", b"no-store"),
                ],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": _TOO_MANY_BODY,
            }
        )

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http" or not self.enabled:
            await self.app(scope, receive, send)
            return

        path = scope.get("path") or ""
        if self._is_exempt(path):
            await self.app(scope, receive, send)
            return

        key = self._client_key(scope)
        limit = self._limit_for(path)
        now = time.monotonic()
        window = self._hits[key]
        self._prune(window, now)
        if len(window) >= limit:
            await self._send_429(send)
            return
        window.append(now)
        await self.app(scope, receive, send)
