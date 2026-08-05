"""協力会社コンプライアンス台帳サービス（許可・社会保険・CCUS・反社・リスクスコア）."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import CurrentUser
from app.models.partner import Partner


def _risk_reasons(partner: Partner, today: date | None = None) -> list[dict[str, str]]:
    today = today or date.today()
    reasons: list[dict[str, str]] = []
    if partner.permit_expiry is not None and partner.permit_expiry < today:
        reasons.append(
            {
                "code": "permit_expired",
                "message": (
                    f"建設業許可の期限が {partner.permit_expiry.isoformat()} に切れています。"
                ),
            }
        )
    if partner.bankruptcy_risk == "high":
        reasons.append({"code": "bankruptcy_risk_high", "message": "倒産リスクが高評価です。"})
    if partner.anti_social_check != "confirmed":
        reasons.append({"code": "antisocial_unconfirmed", "message": "反社チェックが未確認です。"})
    if partner.social_insurance_joined is False:
        reasons.append({"code": "no_social_insurance", "message": "社会保険未加入です。"})
    if partner.permit_expiry is not None and partner.permit_expiry <= today + timedelta(days=90):
        reasons.append(
            {
                "code": "permit_expiring",
                "message": f"許可期限（{partner.permit_expiry.isoformat()}）が 90 日以内です。",
            }
        )
    if partner.ccus_registered is False and partner.partner_type in {"下請", "専門工事"}:
        reasons.append(
            {
                "code": "ccus_missing",
                "message": "CCUS（建設キャリアアップシステム）未登録です。",
            }
        )
    return reasons


def assess_risk(partner: Partner, today: date | None = None) -> tuple[str, list[dict[str, str]]]:
    """許可期限・反社・社会保険・倒産リスクから risk_level を機械判定する。"""
    reasons = _risk_reasons(partner, today=today)
    if any(r["code"] in {"permit_expired", "bankruptcy_risk_high"} for r in reasons):
        level = "critical"
    elif any(
        r["code"] in {"antisocial_unconfirmed", "no_social_insurance", "permit_expiring"}
        for r in reasons
    ):
        level = "high"
    elif any(r["code"] == "ccus_missing" for r in reasons):
        level = "medium"
    else:
        level = "low"
    return level, reasons


async def create_partner(
    session: AsyncSession,
    *,
    actor: CurrentUser,
    data: dict[str, Any],
) -> Partner:
    partner = Partner(
        name=data["name"],
        partner_type=data["partner_type"],
        permit_number=data.get("permit_number"),
        permit_types=data.get("permit_types") or [],
        permit_specific=data.get("permit_specific"),
        permit_expiry=data.get("permit_expiry"),
        social_insurance_joined=data.get("social_insurance_joined"),
        ccus_registered=data.get("ccus_registered"),
        ccus_expiry=data.get("ccus_expiry"),
        supervisor_qualifications=data.get("supervisor_qualifications") or [],
        business_evaluation=data.get("business_evaluation") or {},
        anti_social_check=str(data.get("anti_social_check") or "unconfirmed"),
        anti_social_checked_at=data.get("anti_social_checked_at"),
        bankruptcy_risk=str(data.get("bankruptcy_risk") or "unknown"),
        insurance_joined=data.get("insurance_joined"),
        re_subcontract=data.get("re_subcontract"),
        last_transaction=data.get("last_transaction"),
        risk_level="low",
        notes=data.get("notes"),
        created_by=actor.db_id,
        updated_by=actor.db_id,
    )
    partner.risk_level, _ = assess_risk(partner)
    session.add(partner)
    await session.flush()
    await session.refresh(partner)
    return partner


async def get_partner(
    session: AsyncSession,
    *,
    partner_id: int,
    viewer: CurrentUser,
    include_deleted: bool = False,
) -> Partner | None:
    stmt = select(Partner).where(Partner.id == partner_id)
    if not include_deleted:
        stmt = stmt.where(Partner.deleted_at.is_(None))
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_partners(
    session: AsyncSession,
    *,
    q: str | None = None,
    partner_type: str | None = None,
    risk_level: str | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[Partner], int]:
    stmt = select(Partner).where(Partner.deleted_at.is_(None))
    if q:
        stmt = stmt.where(
            Partner.name.ilike(f"%{q}%")
            | Partner.permit_number.ilike(f"%{q}%")
        )
    if partner_type:
        stmt = stmt.where(Partner.partner_type == partner_type)
    if risk_level:
        stmt = stmt.where(Partner.risk_level == risk_level)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()
    stmt = stmt.order_by(Partner.updated_at.desc()).offset((page - 1) * size).limit(size)
    rows = list((await session.execute(stmt)).scalars().all())
    return rows, total


async def update_partner(
    session: AsyncSession,
    *,
    partner_id: int,
    actor: CurrentUser,
    data: dict[str, Any],
) -> Partner:
    partner = await get_partner(session, partner_id=partner_id, viewer=actor)
    if partner is None:
        raise LookupError(f"Partner {partner_id} not found")
    for field, value in data.items():
        if hasattr(partner, field):
            setattr(partner, field, value)
    partner.risk_level, _ = assess_risk(partner)
    partner.updated_by = actor.db_id
    await session.flush()
    await session.refresh(partner)
    return partner


async def delete_partner(
    session: AsyncSession,
    *,
    partner_id: int,
    actor: CurrentUser,
) -> None:
    partner = await get_partner(session, partner_id=partner_id, viewer=actor)
    if partner is None:
        raise LookupError(f"Partner {partner_id} not found")
    partner.deleted_at = datetime.now(UTC)
    partner.updated_by = actor.db_id
    await session.flush()


async def summary(session: AsyncSession) -> dict[str, Any]:
    """協力会社リスク集計。"""
    rows = list(
        (
            await session.execute(
                select(Partner).where(Partner.deleted_at.is_(None))
            )
        )
        .scalars()
        .all()
    )
    today = date.today()
    cutoff = today + timedelta(days=90)
    by_risk: dict[str, int] = {}
    for row in rows:
        level, _ = assess_risk(row)
        by_risk[level] = by_risk.get(level, 0) + 1
    return {
        "total": len(rows),
        "by_risk_level": by_risk,
        "antisocial_unconfirmed": sum(
            1 for r in rows if r.anti_social_check != "confirmed"
        ),
        "permit_expiring_within_90d": sum(
            1
            for r in rows
            if r.permit_expiry is not None
            and today <= r.permit_expiry <= cutoff
        ),
    }


__all__ = [
    "assess_risk",
    "create_partner",
    "delete_partner",
    "get_partner",
    "list_partners",
    "summary",
    "update_partner",
]
