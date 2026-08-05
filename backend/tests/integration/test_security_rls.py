"""PostgreSQL RLS 統合テスト（PG 環境のみ有効）.

SQLite では RLS が効かないため、dialect ガード付きでスキップする。
DB セッションはテスト本体内の短寿命セッションで持ち、fixture の
イベントループ跨ぎ（asyncpg + pytest-asyncio）を回避する。
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.test_session import create_all_for_tests, create_test_engine
from app.services.rls import policy_sql_statements
from app.services.rls_context import set_rls_context


def _test_url() -> str:
    return os.getenv(
        "PYTEST_DATABASE_URL",
        "postgresql+asyncpg://legalops:legalops_dev@localhost:5432/legalops_test",
    )


@pytest.mark.skipif(
    os.getenv("PYTEST_USE_POSTGRES") != "1",
    reason="RLS assertions require PostgreSQL",
)
async def test_set_rls_context_visible_on_postgres() -> None:
    engine = create_test_engine(_test_url())
    await create_all_for_tests(engine)
    try:
        async with engine.connect() as conn:
            trans = await conn.begin()
            try:
                session = async_sessionmaker(
                    bind=conn,
                    expire_on_commit=False,
                    class_=AsyncSession,
                )()
                await set_rls_context(session, actor_id=12345, role="drafter")
                rows = (
                    await session.execute(
                        text(
                            "SELECT current_setting('app.actor_id', true), "
                            "current_setting('app.role', true)"
                        )
                    )
                ).one()
                assert rows[0] == "12345"
                assert rows[1] == "drafter"
            finally:
                await trans.rollback()
    finally:
        await engine.dispose()


@pytest.mark.skipif(
    os.getenv("PYTEST_USE_POSTGRES") != "1",
    reason="RLS assertions require PostgreSQL",
)
async def test_contracts_rls_policy_exists() -> None:
    engine = create_test_engine(_test_url())
    await create_all_for_tests(engine)
    try:
        async with engine.connect() as conn:
            trans = await conn.begin()
            try:
                for statement in policy_sql_statements():
                    await conn.execute(text(statement))
                rows = (
                    await conn.execute(
                        text(
                            "SELECT policyname FROM pg_policies "
                            "WHERE tablename = 'contracts' "
                            "AND policyname IN "
                            "('contracts_app_access', 'contracts_tenant_isolation')"
                        )
                    )
                ).all()
                names = {r[0] for r in rows}
                assert "contracts_app_access" in names
                assert "contracts_tenant_isolation" in names
            finally:
                await trans.rollback()
    finally:
        await engine.dispose()
