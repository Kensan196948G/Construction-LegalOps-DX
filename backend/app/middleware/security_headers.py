"""Security response-header middleware.

Attaches the standard browser-side hardening headers required by
``docs/security_policy.md``:

* **Content-Security-Policy** (production) / **-Report-Only** (dev)
  — strict ``default-src 'self'``. *SharePoint* image allowlisting is the
  frontend's responsibility (``next.config.mjs``) so it is **not** added
  here.
* **Strict-Transport-Security** — 2 years, ``includeSubDomains``,
  ``preload``. Only emitted over HTTPS or when running in production
  (avoids breaking local ``http://localhost`` dev loops).
* **X-Frame-Options: DENY** — defence-in-depth on top of CSP
  ``frame-ancestors``.
* **X-Content-Type-Options: nosniff**
* **Referrer-Policy: strict-origin-when-cross-origin**
* **Permissions-Policy** — disables unused powerful APIs.
* **Cross-Origin-Opener-Policy: same-origin** (process isolation).
* **Cross-Origin-Resource-Policy: same-site**

The middleware is *additive only*: existing headers set by downstream
handlers (e.g. ``X-Request-Id``) are preserved.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Final

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.config import settings

# ---------------------------------------------------------------------------
# Header values
# ---------------------------------------------------------------------------

# `default-src 'self'` per spec. We intentionally do *not* whitelist
# SharePoint here — the frontend's `next.config.mjs` rewrites SharePoint
# image fetches through the Next.js image optimiser, so the browser only
# sees same-origin requests.
_CSP_DIRECTIVES: Final[tuple[tuple[str, str], ...]] = (
    ("default-src", "'self'"),
    ("base-uri", "'self'"),
    ("frame-ancestors", "'none'"),
    ("form-action", "'self'"),
    ("object-src", "'none'"),
    # Style: 'self' + 'unsafe-inline' is required by Next.js streamed
    # styled-components fallback. Loop 5 may tighten via nonces.
    ("style-src", "'self' 'unsafe-inline'"),
    # Scripts: same-origin only. ``'strict-dynamic'`` is intentionally
    # *omitted* until nonces land (Loop 5).
    ("script-src", "'self'"),
    ("img-src", "'self' data: blob:"),
    ("font-src", "'self' data:"),
    ("connect-src", "'self'"),
    ("manifest-src", "'self'"),
    ("worker-src", "'self' blob:"),
    ("upgrade-insecure-requests", ""),
)

_PERMISSIONS_POLICY: Final[str] = ", ".join(
    [
        "accelerometer=()",
        "ambient-light-sensor=()",
        "autoplay=()",
        "camera=()",
        "geolocation=()",
        "gyroscope=()",
        "magnetometer=()",
        "microphone=()",
        "payment=()",
        "usb=()",
        "interest-cohort=()",
    ]
)

_HSTS_VALUE: Final[str] = "max-age=63072000; includeSubDomains; preload"


def _build_csp() -> str:
    """Serialise the CSP directives into a single header value."""
    parts: list[str] = []
    for name, value in _CSP_DIRECTIVES:
        parts.append(name if not value else f"{name} {value}")
    return "; ".join(parts)


_CSP_HEADER_VALUE: Final[str] = _build_csp()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Append browser-hardening response headers."""

    def __init__(self, app: ASGIApp, *, force_https: bool | None = None) -> None:
        super().__init__(app)
        self._force_https = settings.is_production if force_https is None else force_https

    async def dispatch(  # type: ignore[override]
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)

        # Enforce CSP when is_csp_enforce is True (production by default, or
        # when CSP_ENFORCE=true is set explicitly e.g. on staging).
        csp_header = (
            "Content-Security-Policy"
            if settings.is_csp_enforce
            else "Content-Security-Policy-Report-Only"
        )
        response.headers.setdefault(csp_header, _CSP_HEADER_VALUE)
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", _PERMISSIONS_POLICY)
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-site")
        response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        # Cache hint for authenticated API responses — never store on shared
        # caches. Individual endpoints may override.
        response.headers.setdefault("Cache-Control", "no-store, no-cache, must-revalidate, private")

        # HSTS only over HTTPS to avoid pinning unreachable hosts during
        # local docker-compose loops.
        if self._force_https or _is_https(request):
            response.headers.setdefault("Strict-Transport-Security", _HSTS_VALUE)

        return response


def _is_https(request: Request) -> bool:
    """Detect HTTPS taking ``X-Forwarded-Proto`` into account."""
    if request.url.scheme == "https":
        return True
    forwarded = request.headers.get("x-forwarded-proto", "").lower()
    return "https" in forwarded


__all__ = ["SecurityHeadersMiddleware"]
