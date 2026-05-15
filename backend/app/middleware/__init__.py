"""HTTP middleware components for Construction-LegalOps-DX.

The modules in this package are deliberately self-contained ASGI / Starlette
middlewares so the FastAPI application factory can compose them without any
implicit ordering coupling. They are added in :func:`app.main.create_app` —
the outer-most layer last, per Starlette semantics.

Loop 4 (Security 統合) shipped:

* :class:`SecurityHeadersMiddleware` — CSP / HSTS / X-Frame-Options / etc.
* :class:`SensitiveMaskingMiddleware` — JSON response PII scrubber.

Both are fail-closed: on internal error they prefer to *drop* the response
body rather than risk leaking unmasked content.
"""

from __future__ import annotations

from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.sensitive_masking import SensitiveMaskingMiddleware

__all__ = [
    "SecurityHeadersMiddleware",
    "SensitiveMaskingMiddleware",
]
