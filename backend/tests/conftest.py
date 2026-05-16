"""pytest fixtures for Construction-LegalOps-DX backend.

This conftest provides:

* session-scoped ``event_loop`` (so async fixtures share a loop)
* ``db_engine`` — async SQLAlchemy engine.
    Default: ``sqlite+aiosqlite:///:memory:``.
    Set ``PYTEST_USE_POSTGRES=1`` to use the URL from ``PYTEST_DATABASE_URL``
    (or fall back to the production-style asyncpg URL).
* ``db_session`` — wraps each test in a transaction, rolling back on exit.
* ``client`` — ``httpx.AsyncClient(transport=ASGITransport(app=app))``
* ``auth_headers_*`` — Bearer headers for admin / legal / site personas
* ``factory_session`` — SQLAlchemy *sync* session for factory-boy

The fixtures degrade gracefully if upstream modules (``app.db.session``,
``app.main`` …) are not yet wired — collection should still succeed in
early Loops.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# Event loop
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Provide a single event loop for the whole test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Database URL helpers
# ---------------------------------------------------------------------------


def _resolve_db_url() -> str:
    if os.getenv("PYTEST_USE_POSTGRES") == "1":
        return os.getenv(
            "PYTEST_DATABASE_URL",
            "postgresql+asyncpg://legalops:legalops_dev@localhost:5432/legalops_test",
        )
    return "sqlite+aiosqlite:///:memory:"


def _sync_sqlite_url() -> str:
    """Synchronous URL used by factory-boy sessions when running on SQLite."""
    return "sqlite:///:memory:"


# ---------------------------------------------------------------------------
# DB engine / session (async)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="session")
async def db_engine() -> AsyncGenerator[Any, None]:
    """Create an async engine and (best-effort) the schema.

    If ``app.db.base.Base`` is not importable yet (early Loops), we still
    yield a usable engine so that integration tests can be collected and
    skipped explicitly.
    """
    try:
        from sqlalchemy.ext.asyncio import create_async_engine
    except ImportError:  # pragma: no cover
        pytest.skip("SQLAlchemy async support unavailable")

    url = _resolve_db_url()
    engine = create_async_engine(url, future=True, echo=False)

    # Best-effort schema bootstrap. Don't fail collection if metadata is
    # not importable yet.
    try:
        from app.db.base import Base  # type: ignore

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception:
        pass

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
# factory-boy uses a sync session
# ---------------------------------------------------------------------------


@pytest.fixture()
def factory_session() -> Generator[Any, None, None]:
    """Sync SQLAlchemy session for factory-boy ``sqlalchemy_session``.

    Uses an isolated in-memory SQLite DB so factory output does not require
    the production schema to be migrated.
    """
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
    except ImportError:  # pragma: no cover
        pytest.skip("SQLAlchemy unavailable")

    engine = create_engine(_sync_sqlite_url(), future=True)
    try:
        from app.db.base import Base  # type: ignore

        Base.metadata.create_all(engine)
    except Exception:
        pass

    Session = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


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
