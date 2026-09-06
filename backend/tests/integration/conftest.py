"""Integration-test fixtures.

This conftest only fires for tests under ``tests/integration/``.

Key fixtures
------------

* ``test_engine`` (session) — thin alias for the parent ``tests/conftest.py``
  ``db_engine`` fixture (same PostgreSQL engine, same schema bootstrap run
  once per test session). Kept as a separate name since many integration
  tests request ``test_engine`` explicitly; aliasing avoids a second
  ``drop_all``/``create_all`` pass racing the unit-test schema.
* ``db_session`` (function, override) — transaction-isolated session bound
  to ``test_engine``, rolled back on teardown (same contract as the parent
  ``db_session``).
* ``client`` (function, override) — ASGI ``httpx.AsyncClient`` with the
  application's ``get_db`` dependency rebound to the test session and
  the lifespan handler disabled (the lifespan would otherwise dispose
  the *production* engine on shutdown).
* ``api_db_session`` (function) — bound directly to ``test_engine`` (same
  bind target as ``client``'s own session), for tests that need to seed
  rows via the ORM and then have ``client`` read them back over HTTP.
  ``db_session`` cannot be used for that: its rows live inside a
  connection-level transaction that ``client``'s separate connection
  never sees, even after ``session.commit()``.

``client`` and ``api_db_session`` commit directly to the shared
``test_engine`` (unlike ``db_session``, which rolls back on teardown), so
rows they commit remain visible to later tests in the same session.
Per-test ``TRUNCATE`` of the full schema was measured (~2.5s/test — a
~2.7x slowdown across the ~260 integration tests, from fsync cost on
~60 tables) and rejected as disproportionate; affected tests instead
scope assertions to their own rows (filter by the id they created, or
compare before/after counts) — see individual test files.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator
from typing import Any

import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# Engine (aliases the parent conftest's session-scoped engine)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="session")
async def test_engine(db_engine: Any) -> AsyncGenerator[Any, None]:
    """Alias for the shared session-scoped PostgreSQL engine."""
    yield db_engine


# ---------------------------------------------------------------------------
# Per-test session
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def db_session(test_engine: Any) -> AsyncGenerator[Any, None]:
    """Override the parent ``db_session`` fixture, bound to ``test_engine``.

    Same transaction-rollback contract as the parent fixture — kept as a
    separate override only because integration tests request ``test_engine``
    (not ``db_engine``) as the bind target.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    connection = await test_engine.connect()
    trans = await connection.begin()
    Session = async_sessionmaker(bind=connection, expire_on_commit=False, class_=AsyncSession)
    session = Session()
    try:
        yield session
    finally:
        await session.close()
        if trans.is_active:
            await trans.rollback()
        await connection.close()


@pytest_asyncio.fixture()
async def api_db_session(test_engine: Any) -> AsyncGenerator[Any, None]:
    """Session bound directly to ``test_engine``, visible to ``client``.

    Use this (not ``db_session``) to seed rows via the ORM that a
    subsequent ``client`` HTTP call must read back — ``client`` opens its
    own connection to ``test_engine`` and cannot see rows still held
    inside ``db_session``'s rolled-back-on-teardown transaction.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    Session = async_sessionmaker(bind=test_engine, expire_on_commit=False, class_=AsyncSession)
    session = Session()
    try:
        yield session
    finally:
        await session.close()


# ---------------------------------------------------------------------------
# ASGI client with overridden DB dependency
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def client(test_engine: Any) -> AsyncGenerator[Any, None]:
    """Async HTTPX client with the production ``get_db`` rebound.

    The application's ``lifespan`` is bypassed by using
    ``ASGITransport`` directly without the ``with`` lifespan manager,
    which prevents ``dispose_engine`` from tearing down the (production)
    pool at teardown.
    """
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    try:
        from app.main import app  # type: ignore
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"FastAPI app not importable: {exc}")

    try:
        from app.db.session import get_db  # type: ignore
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"get_db not importable: {exc}")

    Session = async_sessionmaker(bind=test_engine, expire_on_commit=False, class_=AsyncSession)

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        session = Session()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)
