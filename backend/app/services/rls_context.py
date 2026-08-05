"""RLS 実行時コンテキスト設定（deps.py から利用する薄いラッパー）."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.rls import set_actor_context


async def set_rls_context(
    session: AsyncSession,
    *,
    actor_id: int | None,
    role: str | None = None,
    email: str | None = None,
) -> None:
    """認証済みユーザーの RLS コンテキストを現在のトランザクションに設定する。"""
    await set_actor_context(
        session,
        actor_id=actor_id,
        role=role,
        email=email,
    )


__all__ = ["set_rls_context"]
