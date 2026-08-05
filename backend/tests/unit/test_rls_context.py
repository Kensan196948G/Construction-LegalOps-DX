"""RLS コンテキスト設定のテスト（SQLite では no-op を検証）."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.services.rls_context import set_rls_context


async def test_set_rls_context_sqlite_is_noop(db_session) -> None:
    """SQLite では何も実行せず例外も出さない."""
    await set_rls_context(db_session, actor_id=1, role="admin")
    # SQLite ではセッション変数が無いため、クエリ結果は通常どおり
    result = await db_session.execute(text("SELECT 1 AS v"))
    assert result.scalar_one() == 1


@pytest.mark.parametrize(
    ("actor_id", "role"),
    [(None, None), (42, "drafter"), (1, "auditor")],
)
async def test_set_rls_context_argument_variants(db_session, actor_id, role) -> None:
    await set_rls_context(db_session, actor_id=actor_id, role=role)
    result = await db_session.execute(text("SELECT 1 AS v"))
    assert result.scalar_one() == 1
