"""SQLAlchemy 2.x async engine, session factory, and FastAPI dependency."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Final

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


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
    """
    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def dispose_engine() -> None:
    """Dispose the engine pool (call during application shutdown)."""
    await engine.dispose()


__all__ = [
    "AsyncSessionLocal",
    "dispose_engine",
    "engine",
    "get_db",
]
