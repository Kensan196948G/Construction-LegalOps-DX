"""FastAPI application factory and ASGI entry point.

Wires together: lifecycle, CORS, TrustedHost, exception handlers,
structured logging middleware, Prometheus metrics, and the v1 router.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from typing import Any, Final

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import (
    clear_request_context,
    configure_logging,
    get_logger,
    set_request_context,
)
from app.db.session import dispose_engine, get_db, update_pool_metrics
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.sensitive_masking import SensitiveMaskingMiddleware
from app.observability.operational_metrics import update_operational_metrics

# Router import is intentionally lazy at module level to avoid pulling
# the entire API layer into worker processes that don't need it.

logger = get_logger(__name__)

try:
    from importlib.metadata import version as _installed_version

    APP_VERSION = _installed_version("construction-legalops-dx-backend")
except Exception:  # pragma: no cover - source checkout without install
    # Mirror backend/pyproject.toml when the package metadata is unavailable.
    APP_VERSION = "0.1.12"

_REGISTRY: Final[CollectorRegistry] = CollectorRegistry()

_REQUEST_COUNTER: Final[Counter] = Counter(
    "http_requests_total",
    "Total HTTP requests handled.",
    ("method", "path", "status"),
    registry=_REGISTRY,
)
_REQUEST_LATENCY: Final[Histogram] = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds.",
    ("method", "path"),
    registry=_REGISTRY,
)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Application startup / shutdown hooks."""
    configure_logging()
    logger.info(
        "app_startup",
        app_env=settings.app_env,
        app_name=settings.app_name,
    )
    _pool_metrics_task: asyncio.Task[None] | None = None
    try:
        _pool_metrics_task = asyncio.create_task(_pool_metrics_loop())
        yield
    finally:
        if _pool_metrics_task is not None:
            _pool_metrics_task.cancel()
            with suppress(asyncio.CancelledError):
                await _pool_metrics_task
        logger.info("app_shutdown")
        await dispose_engine()


async def _pool_metrics_loop(interval: float = 30.0) -> None:
    """Periodically update DB pool metrics for Prometheus scraping."""
    while True:
        try:
            update_pool_metrics()
        except Exception:
            logger.debug("pool_metrics_update_failed", exc_info=True)
        await asyncio.sleep(interval)


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


class RequestContextMiddleware:
    """Pure-ASGI middleware: injects X-Request-Id and binds structlog context.

    Replaces the previous ``@app.middleware("http")`` function which used
    ``BaseHTTPMiddleware`` internally and triggered asyncpg loop-binding
    errors when combined with HTTPX ASGITransport in tests.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _get_request_id(scope)

        # Store in scope state so downstream code (e.g. masking middleware)
        # can access it via request.state.request_id. scope["state"] must be
        # treated as a PLAIN DICT: real ASGI servers (uvicorn) pre-populate it
        # as a dict, and Starlette's Request.state wraps that dict — assigning
        # an attribute on it blew up with AttributeError and 500'd every
        # request under uvicorn (caught by the first real k6 smoke run; the
        # httpx ASGITransport used in tests never populates "state", which is
        # why the integration suite could not see it).
        scope.setdefault("state", {})["request_id"] = request_id
        set_request_context(request_id=request_id)

        started = time.perf_counter()
        response_status: list[int] = [200]

        async def add_request_id_header(message: Message) -> None:
            if message["type"] == "http.response.start":
                response_status[0] = message.get("status", 200)
                message.setdefault("headers", [])
                MutableHeaders(scope=message)["X-Request-Id"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, add_request_id_header)
        finally:
            elapsed = time.perf_counter() - started
            # Use route template when available (set by Starlette router after
            # dispatch), fall back to raw ASGI path.
            route = scope.get("route")
            path_label: str = str(getattr(route, "path", None) or scope.get("path", ""))
            try:
                _REQUEST_LATENCY.labels(
                    method=scope.get("method", ""),
                    path=path_label,
                ).observe(elapsed)
            except Exception:  # pragma: no cover — metrics must never break requests
                logger.debug("metrics_latency_failure", exc_info=True)
            clear_request_context()

        try:
            _REQUEST_COUNTER.labels(
                method=scope.get("method", ""),
                path=path_label,
                status=str(response_status[0]),
            ).inc()
        except Exception:  # pragma: no cover
            logger.debug("metrics_counter_failure", exc_info=True)


def _get_request_id(scope: Scope) -> str:
    """Extract X-Request-Id from ASGI scope headers, or generate a new UUID."""
    headers: list[tuple[bytes, bytes]] = scope.get("headers", [])
    for name, value in headers:
        if name.lower() == b"x-request-id":
            return value.decode("latin-1")
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    configure_logging()

    app = FastAPI(
        title=settings.app_name,
        version=APP_VERSION,
        description=(
            "Construction-LegalOps-DX backend API. Japanese construction "
            "industry legal operations platform."
        ),
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ----- Middleware -----
    # Starlette wraps middleware in LIFO order, so the last call below is
    # the OUTERMOST layer that touches the raw request first. We want:
    #
    #   CORS (outermost) -> TrustedHost -> SecurityHeaders ->
    #     SensitiveMasking -> request_context (innermost)
    #
    # so add them in reverse, ending with CORS.
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(SensitiveMaskingMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.trusted_hosts,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-Id"],
    )

    # ----- Exception handlers -----
    register_exception_handlers(app)

    # ----- Health endpoints -----
    @app.get("/health", tags=["meta"], include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/healthz", tags=["meta"], include_in_schema=False)
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", tags=["meta"], include_in_schema=False)
    async def readyz_root(session: AsyncSession = Depends(get_db)) -> dict[str, Any]:
        """Root-level readiness probe (used by Docker healthcheck)."""
        try:
            await session.execute(text("SELECT 1"))
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"status": "not_ready"},
            )
        return {"status": "ready", "db": "ok"}

    @app.get(
        f"{settings.api_v1_prefix}/health",
        tags=["meta"],
        summary="Health check",
    )
    async def health_v1() -> dict[str, str]:
        """Lightweight liveness probe."""
        return {"status": "ok", "version": app.version}

    @app.get("/metrics", include_in_schema=False)
    async def metrics(session: AsyncSession = Depends(get_db)) -> Response:
        """Prometheus scrape endpoint."""
        try:
            update_pool_metrics()
            await update_operational_metrics(session)
        except Exception:
            logger.debug("operational_metrics_refresh_failed", exc_info=True)
        payload = generate_latest(_REGISTRY) + generate_latest(REGISTRY)
        return Response(
            content=payload,
            media_type=CONTENT_TYPE_LATEST,
        )

    # ----- API v1 router -----
    # Imported lazily so import-time failures in downstream modules don't
    # crash the worker / metrics processes.
    try:
        from app.api.v1 import api_router  # type: ignore[import-not-found]
    except ImportError as exc:
        logger.warning(
            "api_router_unavailable",
            detail="api_router import failed; API v1 routes unavailable",
            error=str(exc),
        )
    else:
        # ``api_router`` already declares ``prefix="/api/v1"`` so we mount it
        # without an additional prefix. Adding ``settings.api_v1_prefix`` here
        # would yield duplicated ``/api/v1/api/v1/...`` paths.
        app.include_router(api_router)

    logger.info(
        "app_created",
        cors_origins=settings.cors_origins,
        trusted_hosts=settings.trusted_hosts,
    )
    return app


app: Final[FastAPI] = create_app()


__all__ = ["app", "create_app"]
