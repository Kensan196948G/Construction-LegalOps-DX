"""FastAPI application factory and ASGI entry point.

Wires together: lifecycle, CORS, TrustedHost, exception handlers,
structured logging middleware, Prometheus metrics, and the v1 router.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Final

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import (
    clear_request_context,
    configure_logging,
    get_logger,
    set_request_context,
)
from app.db.session import dispose_engine

# Router import is intentionally lazy at module level to avoid pulling
# the entire API layer into worker processes that don't need it.

logger = get_logger(__name__)

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
    try:
        yield
    finally:
        logger.info("app_shutdown")
        await dispose_engine()


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


async def request_context_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Inject X-Request-Id and bind structlog context for the request."""
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = request_id
    set_request_context(request_id=request_id)

    started = time.perf_counter()
    try:
        response = await call_next(request)
    finally:
        elapsed = time.perf_counter() - started
        # Use route template when available, fall back to raw path.
        route = request.scope.get("route")
        path_label = getattr(route, "path", None) or request.url.path
        try:
            _REQUEST_LATENCY.labels(
                method=request.method,
                path=path_label,
            ).observe(elapsed)
        except Exception:  # pragma: no cover — metrics must never break requests
            logger.debug("metrics_latency_failure", exc_info=True)
        clear_request_context()

    try:
        _REQUEST_COUNTER.labels(
            method=request.method,
            path=path_label,
            status=str(response.status_code),
        ).inc()
    except Exception:  # pragma: no cover
        logger.debug("metrics_counter_failure", exc_info=True)

    response.headers["X-Request-Id"] = request_id
    return response


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    configure_logging()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description=(
            "Construction-LegalOps-DX backend API. Japanese construction "
            "industry legal operations platform."
        ),
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ----- Middleware (outer-most last) -----
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-Id"],
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.trusted_hosts,
    )
    app.middleware("http")(request_context_middleware)

    # ----- Exception handlers -----
    register_exception_handlers(app)

    # ----- Health endpoints -----
    @app.get("/health", tags=["meta"], include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get(
        f"{settings.api_v1_prefix}/health",
        tags=["meta"],
        summary="Health check",
    )
    async def health_v1() -> dict[str, str]:
        """Lightweight liveness probe."""
        return {"status": "ok", "version": app.version}

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        """Prometheus scrape endpoint."""
        return Response(
            content=generate_latest(_REGISTRY),
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
            detail="app.api.v1.api_router not yet implemented",
            error=str(exc),
        )
    else:
        app.include_router(api_router, prefix=settings.api_v1_prefix)

    logger.info(
        "app_created",
        cors_origins=settings.cors_origins,
        trusted_hosts=settings.trusted_hosts,
    )
    return app


app: Final[FastAPI] = create_app()


__all__ = ["app", "create_app"]
