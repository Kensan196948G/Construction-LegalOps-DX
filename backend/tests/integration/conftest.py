"""Integration-test fixtures.

This conftest only fires for tests under ``tests/integration/``. It is
intentionally scoped narrowly so that unit tests in ``tests/unit/``
keep their lightweight in-memory fixtures from the parent
``tests/conftest.py``.

Key fixtures
------------

* ``test_engine`` (session) — SQLite async engine with the full schema
  bootstrapped (PG types fall back via :mod:`app.db.test_session`).
* ``db_session`` (function, override) — async session bound to a fresh
  connection per test.
* ``client`` (function, override) — ASGI ``httpx.AsyncClient`` with the
  application's ``get_db`` dependency rebound to the test session and
  the lifespan handler disabled (the lifespan would otherwise dispose
  the *production* engine on shutdown).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator
from typing import Any

import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# Engine / schema bootstrap
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="session")
async def test_engine() -> AsyncGenerator[Any, None]:
    """Session-scoped async engine with the test schema applied."""
    from app.db.test_session import create_all_for_tests, create_test_engine

    engine = create_test_engine()
    try:
        await create_all_for_tests(engine)
        yield engine
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Per-test session
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def db_session(test_engine: Any) -> AsyncGenerator[Any, None]:
    """Override the parent ``db_session`` fixture with the SQLite engine.

    Each test gets its own session. We do **not** wrap in a SAVEPOINT
    rollback here because SQLite + StaticPool keeps a single shared
    connection — rolling back would also revert schema in some edge
    cases. Instead we let the engine's schema persist for the session
    and rely on test isolation via unique-ish data.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    Session = async_sessionmaker(  # noqa: N806
        bind=test_engine, expire_on_commit=False, class_=AsyncSession
    )
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

    Session = async_sessionmaker(  # noqa: N806
        bind=test_engine, expire_on_commit=False, class_=AsyncSession
    )

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        session = Session()
        try:
            yield session
        finally:
            await session.close()

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)
