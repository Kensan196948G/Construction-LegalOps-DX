"""RLS コンテキスト設定のテスト（PostgreSQL の SET LOCAL 経由）."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.services.rls_context import set_rls_context


async def test_set_rls_context_sets_session_variables(db_session) -> None:
    """actor_id/role が PostgreSQL のセッション変数へ反映される."""
    await set_rls_context(db_session, actor_id=1, role="admin")
    result = await db_session.execute(
        text("SELECT current_setting('app.actor_id', true), current_setting('app.role', true)")
    )
    actor_id, role = result.one()
    assert actor_id == "1"
    assert role == "admin"


@pytest.mark.parametrize(
    ("actor_id", "role"),
    [(None, None), (42, "drafter"), (1, "auditor")],
)
async def test_set_rls_context_argument_variants(db_session, actor_id, role) -> None:
    await set_rls_context(db_session, actor_id=actor_id, role=role)
    result = await db_session.execute(text("SELECT 1 AS v"))
    assert result.scalar_one() == 1
