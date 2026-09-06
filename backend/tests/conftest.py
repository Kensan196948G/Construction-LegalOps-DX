"""pytest fixtures for Construction-LegalOps-DX backend.

This conftest provides:

* ``db_engine`` — session-scoped async SQLAlchemy engine against the local
    PostgreSQL test database (see ``app.db.test_session.resolve_test_db_url``).
    Schema is dropped and recreated once per test session.
* ``db_session`` — wraps each test in a transaction, rolling back on exit.
* ``client`` — ``httpx.AsyncClient(transport=ASGITransport(app=app))``
* ``auth_headers_*`` — Bearer headers for admin / legal / site personas

Tests run exclusively against PostgreSQL (the same engine as production) —
there is no SQLite fallback. See ``app/db/test_session.py`` for why.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# DB engine / session (async)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="session")
async def db_engine() -> AsyncGenerator[Any, None]:
    """Session-scoped engine with the schema created once for the whole run.

    Function-scoped drop/create against real PostgreSQL would be far too slow
    across 1000+ tests, so the schema is bootstrapped once here; each test
    gets isolation via ``db_session``'s per-test transaction rollback instead.
    """
    from app.db.test_session import create_all_for_tests, create_test_engine

    engine = create_test_engine()
    await create_all_for_tests(engine)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture()
async def db_session(db_engine: Any) -> AsyncGenerator[Any, None]:
    """Per-test transactional session that rolls back on teardown."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    connection = await db_engine.connect()
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


# ---------------------------------------------------------------------------
# FastAPI ASGI client
# ---------------------------------------------------------------------------


def _try_import_app() -> Any | None:
    """Try several known locations for the FastAPI app instance."""
    candidates = ("app.main", "app.asgi", "app")
    for modname in candidates:
        try:
            mod = __import__(modname, fromlist=["app"])
        except Exception:
            continue
        for attr in ("app", "application", "api"):
            obj = getattr(mod, attr, None)
            if obj is not None:
                return obj
    return None


@pytest_asyncio.fixture()
async def client() -> AsyncGenerator[Any, None]:
    """Async HTTPX client bound to the FastAPI ASGI app.

    Skips the test if the ASGI app is not yet importable.
    """
    try:
        from httpx import ASGITransport, AsyncClient
    except ImportError:  # pragma: no cover
        pytest.skip("httpx unavailable")

    app = _try_import_app()
    if app is None:
        pytest.skip("FastAPI app not yet wired (app.main:app missing)")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


# ---------------------------------------------------------------------------
# JWT auth helpers
# ---------------------------------------------------------------------------


def _make_token(subject: str, role: str, extra: dict[str, Any] | None = None) -> str | None:
    try:
        from app.core.security import create_access_token  # type: ignore
    except Exception:
        return None
    claims: dict[str, Any] = {"role": role}
    if extra:
        claims.update(extra)
    try:
        return create_access_token(subject=subject, extra_claims=claims)
    except Exception:
        return None


def _headers_for(role: str, subject: str) -> dict[str, str]:
    token = _make_token(subject, role)
    if not token:
        pytest.skip("JWT helper unavailable (app.core.security.create_access_token missing)")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def auth_headers_admin() -> dict[str, str]:
    return _headers_for("admin", subject="admin-user@example.com")


@pytest.fixture()
def auth_headers_legal() -> dict[str, str]:
    """Reviewer/approver persona for the legal department."""
    return _headers_for("reviewer", subject="legal-user@example.com")


@pytest.fixture()
def auth_headers_site() -> dict[str, str]:
    """Drafter persona for site (現場) personnel."""
    return _headers_for("drafter", subject="site-user@example.com")


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def anyio_backend() -> str:  # pragma: no cover - support anyio decorators
    return "asyncio"
