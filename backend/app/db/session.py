"""SQLAlchemy 2.x async engine, session factory, and FastAPI dependency."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Final

from prometheus_client import Counter, Gauge
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import AsyncAdaptedQueuePool

from app.core.config import settings

logger = logging.getLogger(__name__)

_COMMIT_FAILURES: Final[Counter] = Counter(
    "db_commit_failures_total",
    "Total number of failed DB commits (commit-after-response window).",
    registry=None,
)

_DB_POOL_SIZE: Final[Gauge] = Gauge(
    "db_pool_size",
    "Configured size of the asyncpg connection pool.",
    registry=None,
)

_DB_POOL_AVAILABLE: Final[Gauge] = Gauge(
    "db_pool_available",
    "Number of idle connections available in the asyncpg pool.",
    registry=None,
)

_DB_CONNECTION_ERRORS: Final[Counter] = Counter(
    "db_connection_errors_total",
    "Total number of database connection errors.",
    registry=None,
)


def _build_engine() -> AsyncEngine:
    """Build the async engine from settings (created once at import time)."""
    db_url = settings.db_url.get_secret_value()
    # SQLite requires NullPool — pool_size/max_overflow/pool_timeout are not
    # valid and will raise TypeError.  Rebuilding engines that differ per
    # environment (SQLite for dev/tests, asyncpg for prod) requires a
    # Mono-repo-safe approach.  We detect SQLite early and skip pool params.
    if "sqlite" in db_url:
        from sqlalchemy.pool import NullPool
        return create_async_engine(
            db_url,
            echo=settings.db_echo,
            poolclass=NullPool,
            future=True,
        )
    return create_async_engine(
        db_url,
        echo=settings.db_echo,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_recycle=1800,
        future=True,
    )


engine: Final[AsyncEngine] = _build_engine()

AsyncSessionLocal: Final[async_sessionmaker[AsyncSession]] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields an async DB session.

    Auto-commits on clean exit; rolls back on exception; always closes.
    Commit failures are logged and metered so the commit-after-response
    window (JIT provisioning / audit writes) is observable.
    """
    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        _COMMIT_FAILURES.inc()
        logger.warning("db_commit_failed", exc_info=True)
        raise
    finally:
        await session.close()


async def dispose_engine() -> None:
    """Dispose the engine pool (call during application shutdown)."""
    await engine.dispose()


async def update_pool_metrics() -> None:
    """Update Prometheus gauges with current connection pool state.

    Called periodically (e.g. from the FastAPI lifespan background task)
    to expose asyncpg pool metrics for Prometheus scraping.
    """
    pool = engine.pool
    if isinstance(pool, AsyncAdaptedQueuePool):
        _DB_POOL_SIZE.set(pool.size())
        _DB_POOL_AVAILABLE.set(pool.size() - pool.checkedout())


__all__ = [
    "AsyncSessionLocal",
    "dispose_engine",
    "engine",
    "get_db",
    "update_pool_metrics",
]
