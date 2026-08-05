"""案件単位 ACL・倫理壁・契約アクセス判定サービス."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case_access import ContractAccessGrant
from app.models.contract import Contract

# 倫理壁対象の機密案件カテゴリ（人事・談合調査・内部通報等）
SENSITIVE_CASE_CATEGORIES: frozenset[str] = frozenset(
    {"hr_labor", "bid_rigging", "whistleblower", "harassment", "investigation"}
)

# 倫理壁を通過できる特権ロール
_ETHICAL_WALL_PRIVILEGED_ROLES: frozenset[str] = frozenset({"admin", "auditor"})


def is_sensitive_case(contract: Any) -> bool:
    """契約が倫理壁対象の機密案件かを判定."""
    meta = getattr(contract, "extra_metadata", None) or {}
    if isinstance(meta, dict):
        category = str(meta.get("case_category", "")).strip().lower()
        return category in SENSITIVE_CASE_CATEGORIES
    return False


async def grant_access(
    session: AsyncSession,
    *,
    contract_id: int,
    user_id: int,
    access_level: str,
    granted_by: int | None,
    ethical_wall: bool = False,
    expires_at: datetime | None = None,
) -> ContractAccessGrant:
    """権限を付与する。既存付与があれば更新（revoked_at を解除して上書き）。"""
    row = (
        await session.execute(
            select(ContractAccessGrant).where(
                ContractAccessGrant.contract_id == contract_id,
                ContractAccessGrant.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = ContractAccessGrant(
            contract_id=contract_id,
            user_id=user_id,
            access_level=access_level,
            ethical_wall=ethical_wall,
            granted_by=granted_by,
            expires_at=expires_at,
            revoked_at=None,
        )
        session.add(row)
    else:
        row.access_level = access_level
        row.ethical_wall = ethical_wall
        row.granted_by = granted_by
        row.expires_at = expires_at
        row.revoked_at = None
    await session.flush()
    return row


async def revoke_access(session: AsyncSession, *, grant_id: int, actor_id: int) -> bool:
    """権限を取り消す（revoked_at を設定）。存在しなければ False。"""
    result = await session.execute(
        update(ContractAccessGrant)
        .where(ContractAccessGrant.id == grant_id, ContractAccessGrant.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    return bool(result.rowcount)


async def list_grants(session: AsyncSession, *, contract_id: int) -> list[ContractAccessGrant]:
    rows = await session.execute(
        select(ContractAccessGrant)
        .where(ContractAccessGrant.contract_id == contract_id)
        .order_by(ContractAccessGrant.id)
    )
    return list(rows.scalars().all())


async def get_active_grant(
    session: AsyncSession, *, contract_id: int, user_id: int
) -> ContractAccessGrant | None:
    """未失効・未取消・期限切れでない付与を返す."""
    now = datetime.now(UTC)
    row = await session.execute(
        select(ContractAccessGrant).where(
            ContractAccessGrant.contract_id == contract_id,
            ContractAccessGrant.user_id == user_id,
            ContractAccessGrant.revoked_at.is_(None),
        )
    )
    grant = row.scalar_one_or_none()
    if grant is None:
        return None
    expires_at = grant.expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at is not None and expires_at <= now:
        return None
    return grant


async def can_access(
    session: AsyncSession,
    *,
    viewer: Any,
    contract: Contract | None,
) -> bool:
    """サービス層のアクセス判定（RLS の補助・SQLite 環境の代替）.

    - admin/auditor は全件可
    - drafter 本人は可
    - 有効な ContractAccessGrant があれば可（ただし倫理壁案件は特権ロールのみ）
    """
    if contract is None:
        return False
    role = getattr(viewer, "role", "guest")
    if role in _ETHICAL_WALL_PRIVILEGED_ROLES:
        return True
    if getattr(contract, "drafter_id", None) == getattr(viewer, "db_id", None):
        return True

    grant = await get_active_grant(
        session,
        contract_id=int(contract.id),
        user_id=int(viewer.db_id or 0),
    )
    # 倫理壁付与は機密案件では特権ロール以外に効かない（fail-closed）
    return not (
        grant is None or (grant.ethical_wall and is_sensitive_case(contract))
    )
