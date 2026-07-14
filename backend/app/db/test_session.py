"""SQLite-compatible test engine factory.

This module is **only** used by the test suite (``backend/tests/``).
Production code must continue to use ``app.db.session`` which targets
asyncpg/PostgreSQL.

Strategy
--------
The production models reference several PostgreSQL-only types:

* ``sqlalchemy.dialects.postgresql.JSONB``
* ``sqlalchemy.dialects.postgresql.UUID``
* ``sqlalchemy.dialects.postgresql.INET``
* ``sqlalchemy.dialects.postgresql.ARRAY``

and PG-specific ``server_default`` literals such as ``'{}'::jsonb``.

To run the metadata against SQLite we:

1. Register ``@compiles(..., 'sqlite')`` shims so each PG type emits a
   reasonable SQLite-compatible DDL (``JSON``, ``CHAR(36)``,
   ``VARCHAR(45)``).
2. Walk ``Base.metadata`` once and rewrite PG-specific
   ``server_default`` text (``'{}'::jsonb``, ``'{}'`` for ARRAY)
   to neutral defaults that SQLite can parse.
3. Drop ``postgresql_where`` partial index predicates — SQLAlchemy
   already ignores dialect-namespaced kwargs for SQLite so this is
   a no-op safety net.

The shims only fire when the target dialect is SQLite, so the production
PostgreSQL DDL is untouched.
"""

from __future__ import annotations

import json as _json
import os
from typing import Final

from sqlalchemy import BigInteger
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.ext.compiler import compiles

# ---------------------------------------------------------------------------
# Dialect compile-time shims (SQLite only)
# ---------------------------------------------------------------------------


@compiles(JSONB, "sqlite")  # type: ignore[misc, no-untyped-call]
def _compile_jsonb_sqlite(_type_: object, _compiler: object, **_: object) -> str:
    return "JSON"


@compiles(PG_UUID, "sqlite")  # type: ignore[misc, no-untyped-call]
def _compile_uuid_sqlite(_type_: object, _compiler: object, **_: object) -> str:
    return "CHAR(36)"


@compiles(INET, "sqlite")  # type: ignore[misc, no-untyped-call]
def _compile_inet_sqlite(_type_: object, _compiler: object, **_: object) -> str:
    return "VARCHAR(45)"


@compiles(ARRAY, "sqlite")  # type: ignore[misc, no-untyped-call]
def _compile_array_sqlite(_type_: object, _compiler: object, **_: object) -> str:
    # Represent PG ARRAY as JSON text on SQLite for DDL.
    return "JSON"


def _sqlite_array_bind_processor(self: object, dialect: object) -> object:  # type: ignore[override]
    """Serialize Python lists to JSON strings for SQLite ARRAY columns.

    Without this, SQLite raises "type 'list' is not supported" because it
    has no native array type.  The companion result_processor decodes them
    back so reads are transparent.
    """
    if getattr(dialect, "name", "") == "sqlite":

        def _bind(value: object) -> object:
            if isinstance(value, list):
                return _json.dumps(value, ensure_ascii=False)
            return value

        return _bind
    return ARRAY.bind_processor(self, dialect)  # type: ignore[arg-type, no-untyped-call]


def _sqlite_array_result_processor(self: object, dialect: object, coltype: object) -> object:  # type: ignore[override]
    """Decode JSON strings back to Python lists on SQLite reads."""
    if getattr(dialect, "name", "") == "sqlite":

        def _result(value: object) -> object:
            if isinstance(value, str):
                try:
                    decoded = _json.loads(value)
                    return decoded if isinstance(decoded, list) else value
                except (ValueError, TypeError):
                    return value
            return value

        return _result
    return ARRAY.result_processor(self, dialect, coltype)  # type: ignore[arg-type, no-untyped-call]


# Monkey-patch ARRAY so the SQLite processor fires without altering production.
ARRAY.bind_processor = _sqlite_array_bind_processor  # type: ignore[method-assign, assignment]
ARRAY.result_processor = _sqlite_array_result_processor  # type: ignore[method-assign, assignment]


@compiles(BigInteger, "sqlite")  # type: ignore[misc, no-untyped-call]
def _compile_bigint_sqlite(_type_: object, _compiler: object, **_: object) -> str:
    # SQLite only auto-increments INTEGER PRIMARY KEY (ROWID alias).
    # BigInteger emits "BIGINT" which breaks autoincrement for PK columns.
    return "INTEGER"


# ---------------------------------------------------------------------------
# server_default rewriting
# ---------------------------------------------------------------------------


_PG_DEFAULT_REWRITES: Final[dict[str, str]] = {
    "'{}'::jsonb": "'{}'",
    "'[]'::jsonb": "'[]'",
    "'{}'::json": "'{}'",
    "'[]'::json": "'[]'",
    # Note: ARRAY(Text) columns use "'{}'", which is also a valid SQLite string.
    # Do NOT add a "'{}'": "'[]'" mapping here — that would corrupt TEXT[] DEFAULT
    # on PostgreSQL runs sharing the same Base.metadata singleton.
}

# Tracks columns already rewritten to prevent double-rewrite across multiple
# create_all_for_tests() calls in one pytest session (Base.metadata is shared).
_rewrites_applied: set[str] = set()


def _rewrite_pg_server_defaults() -> None:
    """Strip PG-specific casts from ``server_default`` so SQLite accepts them.

    Idempotent: safe to call multiple times (tracks processed columns via
    ``_rewrites_applied``).  Only call this for SQLite engines — for
    PostgreSQL use ``_coerce_string_defaults_to_text()`` instead.
    """
    try:
        from app.db.base import Base  # type: ignore
    except Exception:  # pragma: no cover - model layer must be importable
        return

    from sqlalchemy import text as _sql_text
    from sqlalchemy.schema import DefaultClause

    for table in Base.metadata.tables.values():
        for col in table.columns:
            key = f"{table.name}.{col.name}"
            if key in _rewrites_applied:
                continue
            sd = col.server_default
            if sd is None:
                continue
            # DefaultClause.arg is either a TextClause (created via text()) or
            # a plain Python str (SQLAlchemy 2.x stores plain-string
            # server_default values directly as str in DefaultClause.arg).
            arg = getattr(sd, "arg", None)
            if isinstance(arg, str):
                text_val: str | None = arg
            else:
                text_val = getattr(arg, "text", None)
            if not isinstance(text_val, str):
                continue
            replacement: str | None = None
            for needle, repl in _PG_DEFAULT_REWRITES.items():
                if needle in text_val:
                    replacement = text_val.replace(needle, repl)
                    break
            if replacement is not None and replacement != text_val:
                col.server_default = DefaultClause(_sql_text(replacement))
                _rewrites_applied.add(key)


def _coerce_string_defaults_to_text() -> None:
    """Convert plain-string ``server_default`` args to TextClause for PG DDL.

    In SQLAlchemy 2.x a plain Python string in ``DefaultClause.arg`` is
    emitted by the DDL compiler as a *quoted SQL string literal*, which
    double-escapes single-quotes and breaks PostgreSQL type casts::

        '{}'::jsonb  →  '''{}''::jsonb'  (invalid — PG raises Token "'" is invalid)

    Wrapping in ``text()`` causes the value to be emitted verbatim as raw
    SQL.  This function is idempotent: columns whose ``arg`` is already a
    TextClause are left unchanged.
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


# ---------------------------------------------------------------------------
# Engine factory
# ---------------------------------------------------------------------------


DEFAULT_SQLITE_URL: Final[str] = "sqlite+aiosqlite:///:memory:"


def resolve_test_db_url() -> str:
    """Return the URL the test engine should use.

    Set ``PYTEST_USE_POSTGRES=1`` together with ``PYTEST_DATABASE_URL`` to
    bypass SQLite and exercise the full PostgreSQL surface (recommended
    in CI once a Postgres service is wired into the workflow).
    """
    if os.getenv("PYTEST_USE_POSTGRES") == "1":
        return os.getenv(
            "PYTEST_DATABASE_URL",
            "postgresql+asyncpg://legalops:legalops_dev@localhost:5432/legalops_test",
        )
    return DEFAULT_SQLITE_URL


def create_test_engine(url: str | None = None) -> AsyncEngine:
    """Build an :class:`AsyncEngine` suitable for tests.

    For SQLite (the default) a shared :memory: connection is required so
    multiple async sessions see the same schema. We use ``StaticPool``
    via the ``connect_args`` + ``poolclass`` recipe.

    For PostgreSQL we use ``NullPool``: pytest-asyncio gives every test its
    own event loop, but asyncpg connections are bound to the loop that
    created them, so a session-scoped engine with a default ``QueuePool``
    hands loop-A connections to loop-B tests ("Future attached to a
    different loop"). ``NullPool`` opens a fresh connection per checkout on
    the *current* loop and closes it on release, so nothing crosses loops.
    """
    target = url or resolve_test_db_url()

    if target.startswith("sqlite"):
        from sqlalchemy.pool import StaticPool

        engine = create_async_engine(
            target,
            future=True,
            echo=False,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        from sqlalchemy.pool import NullPool

        engine = create_async_engine(target, future=True, echo=False, poolclass=NullPool)

    return engine


async def create_all_for_tests(engine: AsyncEngine) -> None:
    """Create the full schema against the test engine.

    For SQLite engines, applies PG → SQLite ``server_default`` rewrites so
    ``create_all`` succeeds without modifying production model definitions.
    For PostgreSQL engines, coerces plain-string ``server_default`` values
    to ``text()`` so the DDL compiler emits them verbatim instead of quoting
    them as SQL string literals (which would corrupt casts like ``'{}'::jsonb``).
    """
    import app.models  # noqa: F401 — register all ORM models on Base.metadata
    from app.db.base import Base  # type: ignore

    if engine.dialect.name == "sqlite":
        _rewrite_pg_server_defaults()
    else:
        _coerce_string_defaults_to_text()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


__all__ = [
    "DEFAULT_SQLITE_URL",
    "_coerce_string_defaults_to_text",
    "_rewrite_pg_server_defaults",
    "create_all_for_tests",
    "create_test_engine",
    "resolve_test_db_url",
]
