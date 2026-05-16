"""Alembic migration environment for Construction-LegalOps-DX.

Supports both async (online) and offline modes. The async path is used by
``alembic upgrade head`` against the production / staging asyncpg URL; the
offline path emits SQL only and is used to generate review-friendly diffs.

The SQLAlchemy URL is taken from ``settings.DATABASE_URL`` if present (the
Core team owns ``app.core.config``); otherwise from the standard
``sqlalchemy.url`` in ``alembic.ini``. Import-on-demand keeps this module
runnable even before the Core team lands their config.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig
from typing import Any

from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, async_engine_from_config

import app.models  # noqa: F401
from alembic import context

# Ensure every model is imported so its Table is registered on Base.metadata.
from app.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


target_metadata = Base.metadata


def _get_url() -> str:
    """Resolve the DB URL: prefer ``settings.DATABASE_URL`` then alembic.ini."""
    try:
        from app.core.config import settings  # type: ignore[import-not-found]

        url = getattr(settings, "DATABASE_URL", None) or getattr(
            settings, "database_url", None
        )
        if url:
            return str(url)
    except Exception:
        # Core / config module not available yet — fall back to alembic.ini.
        pass
    return config.get_main_option("sqlalchemy.url", "")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — emits SQL without a DB connection."""
    url = _get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Build an AsyncEngine, dispatch into the sync migration runner."""
    configuration: dict[str, Any] = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _get_url()

    connectable: AsyncEngine = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Detects whether the configured URL is async (``+asyncpg``) and dispatches
    to the appropriate runner so that the same ``env.py`` works for both
    pytest (sync psycopg) and the production stack (async asyncpg).
    """
    url = _get_url()
    if "+asyncpg" in url:
        asyncio.run(run_async_migrations())
        return

    configuration: dict[str, Any] = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = url
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        do_run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
