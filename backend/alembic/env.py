"""Alembic migration environment for Construction-LegalOps-DX.

Supports both async (online) and offline modes. The async path is used by
``alembic upgrade head`` against the production / staging asyncpg URL; the
offline path emits SQL only and is used to generate review-friendly diffs.

The SQLAlchemy URL is taken from ``settings.DATABASE_URL`` if present (the
Core team owns ``app.core.config``); otherwise from the standard
``sqlalchemy.url`` in ``alembic.ini``. Import-on-demand keeps this module
runnable even before the Core team lands their config.

Session role (``ALEMBIC_DB_ROLE``)
----------------------------------
Why this exists: the migrations must be *applied* by the schema owner
(``legalops_mvp``), but that role's password lives in a root-only env file and
is deliberately not available to operators. The pragmatic route is to connect
with a DBA/superuser identity that is already reachable (e.g. unix-socket peer
auth) and then downgrade the session to the owning role with ``SET ROLE``.

This matters for correctness, not just privileges: PostgreSQL RLS is *bypassed*
for a table's owner, so if DDL ran as the superuser the new tables would be
owned by the wrong role and the application's row visibility would silently
change. Running as the owner keeps every new object owned by ``legalops_mvp``.

asyncpg exposes this through its connection ``server_settings``, which are
applied as session ``SET`` parameters. ``async_engine_from_config()`` has no
direct ``connect_args`` hook, so the mapping is built here and passed through
explicitly. When ``ALEMBIC_DB_ROLE`` is unset (or the URL is not asyncpg) the
return value is empty and behaviour is byte-for-byte the previous behaviour.
"""

from __future__ import annotations

import asyncio
import os
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
    """Resolve the DB URL: env override → app settings → alembic.ini.

    The previous implementation looked up ``settings.DATABASE_URL`` /
    ``settings.database_url`` — attributes that have never existed (the real
    field is ``db_url``, a ``SecretStr``), so every environment silently fell
    through to the alembic.ini placeholder and ``alembic upgrade head`` could
    not reach a real database. ``str(SecretStr)`` would also have returned the
    masked value, so the secret must be unwrapped via ``get_secret_value()``.
    """
    env_url = os.getenv("ALEMBIC_DATABASE_URL") or os.getenv("DB_URL")
    if env_url:
        return env_url
    try:
        from app.core.config import settings  # type: ignore[import-not-found]

        db_url = getattr(settings, "db_url", None)
        if db_url is not None:
            if hasattr(db_url, "get_secret_value"):
                return str(db_url.get_secret_value())
            return str(db_url)
    except Exception:
        # Core / config module not available yet — fall back to alembic.ini.
        pass
    return config.get_main_option("sqlalchemy.url", "")


def _get_session_role() -> str | None:
    """Return the optional ``SET ROLE`` target, or ``None`` when unset."""
    for name in ("ALEMBIC_DB_ROLE", "ALEMBIC_DATABASE_ROLE"):
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return None


def _get_async_connect_args(url: str) -> dict[str, Any]:
    """Build asyncpg ``connect_args`` that ``SET ROLE`` to the schema owner.

    Returns ``{}`` unless ``ALEMBIC_DB_ROLE`` is set *and* the URL is asyncpg,
    so callers that do not opt in keep the exact previous behaviour. Only
    asyncpg is handled: it maps ``server_settings`` entries onto session
    parameters, which is what ``SET ROLE`` needs.
    """
    role = _get_session_role()
    if not role or "+asyncpg" not in url:
        return {}
    return {"server_settings": {"role": role}}


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
        connect_args=_get_async_connect_args(configuration["sqlalchemy.url"]),
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
