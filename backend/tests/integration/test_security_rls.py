"""PostgreSQL RLS 統合テスト.

DB セッションは共有 ``test_engine``（``tests/integration/conftest.py``）に
対する短寿命の接続・トランザクションで持ち、テスト終了時にロールバックする。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.rls import policy_sql_statements
from app.services.rls_context import set_rls_context


async def test_set_rls_context_visible_on_postgres(test_engine: Any) -> None:
    async with test_engine.connect() as conn:
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


async def test_contracts_rls_policy_exists(test_engine: Any) -> None:
    async with test_engine.connect() as conn:
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
