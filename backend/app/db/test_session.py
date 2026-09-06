"""PostgreSQL test engine factory.

This module is **only** used by the test suite (``backend/tests/``).
Production code must continue to use ``app.db.session`` which targets
asyncpg/PostgreSQL.

The test suite runs exclusively against a local PostgreSQL instance (the
same engine as production) — no SQLite compatibility layer is maintained.
Running tests against the real database engine catches dialect-specific
bugs (RLS policies, ``server_default`` casts, ``JSONB``/``ARRAY`` columns)
that a SQLite substitute would silently hide.

Each test session drops and recreates the schema from ``Base.metadata`` so
a persistent local database (e.g. ``legalops_test``) never accumulates
stale tables or rows across runs.
"""

from __future__ import annotations

import os
from typing import Final

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

DEFAULT_TEST_DB_URL: Final[str] = (
    "postgresql+asyncpg://legalops:legalops_dev@127.0.0.1:5432/legalops_test"
)


def resolve_test_db_url() -> str:
    """Return the PostgreSQL URL the test engine should use.

    Override with ``PYTEST_DATABASE_URL`` (e.g. in CI, where the service
    container is not reachable at ``127.0.0.1`` under the same credentials).
    """
    return os.getenv("PYTEST_DATABASE_URL", DEFAULT_TEST_DB_URL)


def create_test_engine(url: str | None = None) -> AsyncEngine:
    """Build an :class:`AsyncEngine` suitable for tests.

    ``NullPool`` is required because pytest-asyncio gives every test its own
    event loop, but asyncpg connections are bound to the loop that created
    them. A pooled engine would hand loop-A connections to loop-B tests
    ("Future attached to a different loop"). ``NullPool`` opens a fresh
    connection per checkout on the *current* loop and closes it on release,
    so nothing crosses loops.
    """
    target = url or resolve_test_db_url()
    return create_async_engine(target, future=True, echo=False, poolclass=NullPool)


def _coerce_string_defaults_to_text() -> None:
    """Convert plain-string ``server_default`` args to TextClause for PG DDL.

    In SQLAlchemy 2.x a plain Python string in ``DefaultClause.arg`` is
    emitted by the DDL compiler as a *quoted SQL string literal*, which
    double-escapes single-quotes and breaks PostgreSQL type casts::

        '{}'::jsonb  →  '''{}''::jsonb'  (invalid — PG raises Token "'" is invalid)

    Wrapping in ``text()`` causes the value to be emitted verbatim as raw
    SQL. Idempotent: columns whose ``arg`` is already a ``TextClause`` are
    left unchanged.
    """
    try:
        from app.db.base import Base  # type: ignore
    except Exception:  # pragma: no cover
        return

    from sqlalchemy import text as _sql_text
    from sqlalchemy.schema import DefaultClause

    for table in Base.metadata.tables.values():
        for col in table.columns:
            sd = col.server_default
            if sd is None:
                continue
            arg = getattr(sd, "arg", None)
            if isinstance(arg, str):
                col.server_default = DefaultClause(_sql_text(arg))


def _assert_safe_test_database(engine: AsyncEngine) -> None:
    """Refuse to run a destructive schema reset against a non-test database.

    ``PYTEST_DATABASE_URL`` accepts an arbitrary connection string; pointing
    it at a shared/dev database by mistake would let ``drop_all`` erase real
    data. Requiring "test" in the database name is a cheap guardrail against
    that misconfiguration.
    """
    db_name = engine.url.database or ""
    if "test" not in db_name.lower():
        raise RuntimeError(
            f"Refusing to reset schema against database {db_name!r}: "
            "the test database name must contain 'test' "
            "(check PYTEST_DATABASE_URL)."
        )


async def create_all_for_tests(engine: AsyncEngine) -> None:
    """Reset and (re)create the full schema against the test engine.

    Drops all known tables first so a persistent local database (reused
    across many local test runs) never carries over stale tables or rows
    from a previous schema version. ``_coerce_string_defaults_to_text``
    keeps PostgreSQL-specific ``server_default`` casts (``'{}'::jsonb``
    etc.) intact against SQLAlchemy 2.x's plain-string quoting behaviour.
    """
    _assert_safe_test_database(engine)

    import app.models  # noqa: F401 — register all ORM models on Base.metadata
    from app.db.base import Base  # type: ignore

    _coerce_string_defaults_to_text()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        await _seed_master_rows(conn)


async def _seed_master_rows(conn: AsyncConnection) -> None:
    """Seed master rows API-level tests assume to exist.

    Integration tests POST contracts with ``department_id=1``; PostgreSQL
    rejects the insert (``fk_contracts_department_id_departments``) unless
    the parent row exists. The insert is idempotent (``WHERE NOT EXISTS``)
    and bumps the identity sequence past the explicit id so later ORM
    inserts don't collide with the seed.

    users rows are NOT seeded here: ``get_current_user`` JIT-provisions the
    principal's row on first request (Issue #45), which keeps drafter_id /
    scope filters consistent without any out-of-band id derivation.
    """
    from sqlalchemy import text as _sql_text

    await conn.execute(
        _sql_text(
            "INSERT INTO departments (id, code, name) "
            "SELECT 1, 'TEST-DEPT-1', 'テスト本部' "
            "WHERE NOT EXISTS (SELECT 1 FROM departments WHERE id = 1)"
        )
    )
    await conn.execute(
        _sql_text(
            "SELECT setval(pg_get_serial_sequence('departments', 'id'), "
            "(SELECT GREATEST(COALESCE(MAX(id), 1), 1) FROM departments))"
        )
    )


__all__ = [
    "DEFAULT_TEST_DB_URL",
    "create_all_for_tests",
    "create_test_engine",
    "resolve_test_db_url",
]
