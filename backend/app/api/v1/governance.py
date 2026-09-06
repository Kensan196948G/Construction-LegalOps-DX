"""P0-6 ガバナンス API（ACL / Legal Hold / Retention / 監査アンカー / Sentinel）."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import CurrentUser, get_current_user, require_role
from app.models.access_control import AccessControlEntry, LegalHold
from app.models.retention import RetentionRule
from app.schemas.business import (
    AccessControlEntryOut,
    AccessControlGrantRequest,
    AuditAnchorOut,
    AuditAnchorVerifyOut,
    LegalHoldCreate,
    LegalHoldOut,
    LegalHoldReleaseRequest,
    RetentionRuleOut,
    RetentionRuleUpdate,
    RetentionRunOut,
    SentinelStatusOut,
)
from app.services import audit_service, evidence_service, retention_service, sentinel_forwarder
from app.services.audit_anchor import create_daily_anchor, verify_anchor

router = APIRouter(tags=["governance"])

_ADMIN = require_role("admin")
_ADMIN_OR_AUDITOR = require_role("admin", "auditor")


# ---------------------------------------------------------------------------
# 案件単位 ACL
# ---------------------------------------------------------------------------

acl_router = APIRouter(prefix="/contracts/{contract_id}/access-control", tags=["access-control"])


@acl_router.get(
    "",
    response_model=list[AccessControlEntryOut],
    summary="案件 ACL 一覧",
)
async def list_acl(
    contract_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(_ADMIN_OR_AUDITOR),
) -> list[AccessControlEntryOut]:
    rows = (
        (
            await session.execute(
                select(AccessControlEntry)
                .where(AccessControlEntry.contract_id == contract_id)
                .order_by(AccessControlEntry.id.asc())
            )
        )
        .scalars()
        .all()
    )
    return [AccessControlEntryOut.model_validate(r) for r in rows]


@acl_router.post(
    "",
    response_model=AccessControlEntryOut,
    status_code=status.HTTP_201_CREATED,
    summary="案件 ACL 付与",
)
async def grant_acl(
    contract_id: int,
    payload: AccessControlGrantRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(_ADMIN),
) -> AccessControlEntryOut:
    existing = (
        await session.execute(
            select(AccessControlEntry).where(
                AccessControlEntry.contract_id == contract_id,
                AccessControlEntry.principal_type == payload.principal_type,
                AccessControlEntry.principal_id == payload.principal_id,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        entry = AccessControlEntry(
            contract_id=contract_id,
            principal_type=payload.principal_type,
            principal_id=payload.principal_id,
            access_level=payload.access_level,
            granted_by=current_user.db_id,
            expires_at=payload.expires_at,
        )
        session.add(entry)
    else:
        existing.access_level = payload.access_level
        existing.granted_by = current_user.db_id
        existing.expires_at = payload.expires_at
        entry = existing
    await session.flush()
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="access.grant",
        target_type="contracts",
        target_id=contract_id,
        payload={"after": payload.model_dump()},
        request=request,
    )
    return AccessControlEntryOut.model_validate(entry)


@acl_router.delete(
    "/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="案件 ACL 失効",
)
async def revoke_acl(
    contract_id: int,
    entry_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(_ADMIN),
) -> None:
    entry = await session.get(AccessControlEntry, entry_id)
    if entry is None or entry.contract_id != contract_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="acl entry not found")
    payload = {
        "principal_type": entry.principal_type,
        "principal_id": entry.principal_id,
        "access_level": entry.access_level,
    }
    await session.delete(entry)
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="access.revoke",
        target_type="contracts",
        target_id=contract_id,
        payload={"before": payload},
        request=request,
    )


# ---------------------------------------------------------------------------
# Legal Hold
# ---------------------------------------------------------------------------

legal_holds_router = APIRouter(prefix="/legal-holds", tags=["legal-holds"])


@legal_holds_router.get(
    "",
    response_model=list[LegalHoldOut],
    summary="Legal Hold 一覧",
)
async def list_legal_holds(
    status_: str | None = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(_ADMIN_OR_AUDITOR),
) -> list[LegalHoldOut]:
    stmt = select(LegalHold)
    if status_:
        stmt = stmt.where(LegalHold.status == status_)
    rows = (await session.execute(stmt.order_by(LegalHold.id.desc()))).scalars().all()
    return [LegalHoldOut.model_validate(r) for r in rows]


@legal_holds_router.post(
    "",
    response_model=LegalHoldOut,
    status_code=status.HTTP_201_CREATED,
    summary="Legal Hold 発動",
)
async def create_legal_hold(
    payload: LegalHoldCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(_ADMIN),
) -> LegalHoldOut:
    hold = LegalHold(
        target_type=payload.target_type,
        target_id=payload.target_id,
        reason=payload.reason,
        status="active",
        started_by=current_user.db_id,
        evidence_ids=payload.evidence_ids,
        ethical_wall=payload.ethical_wall,
    )
    session.add(hold)
    await session.flush()

    # target_type="evidence" の場合、evidence_ids は Issue #124 の証拠管理
    # （app.models.evidence.Evidence）を指す。Evidence.legal_hold_id と
    # is_under_hold を同期しておかないと、後続の Legal Hold 解除承認
    # （evidence_service.decide_hold_release）の一括更新がこれらの証拠を
    # 見逃す（CodeRabbit指摘）。
    if payload.target_type == "evidence":
        for raw_id in payload.evidence_ids:
            try:
                evidence_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            await evidence_service.link_legal_hold(
                session,
                evidence_id=evidence_id,
                legal_hold_id=hold.id,
                actor_id=current_user.db_id,
            )

    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="legal_hold.create",
        target_type=payload.target_type,
        target_id=payload.target_id,
        payload={"after": payload.model_dump()},
        request=request,
    )
    return LegalHoldOut.model_validate(hold)


@legal_holds_router.post(
    "/{hold_id}/release",
    response_model=LegalHoldOut,
    summary="Legal Hold 解除",
)
async def release_legal_hold(
    hold_id: int,
    payload: LegalHoldReleaseRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(_ADMIN),
) -> LegalHoldOut:
    from datetime import UTC, datetime

    hold = await session.get(LegalHold, hold_id)
    if hold is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="legal hold not found")
    hold.status = "released"
    hold.released_at = datetime.now(UTC)
    hold.released_by = current_user.db_id
    hold.release_reason = payload.reason
    await session.flush()
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="legal_hold.release",
        target_type="legal_holds",
        target_id=hold.id,
        payload={"after": {"reason": payload.reason}},
        request=request,
    )
    return LegalHoldOut.model_validate(hold)


# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------

retention_router = APIRouter(prefix="/retention", tags=["retention"])


@retention_router.get(
    "/rules",
    response_model=list[RetentionRuleOut],
    summary="保存期間ルール一覧",
)
async def list_retention_rules(
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(_ADMIN_OR_AUDITOR),
) -> list[RetentionRuleOut]:
    await retention_service.ensure_default_rules(session)
    rows = (
        (await session.execute(select(RetentionRule).order_by(RetentionRule.id.asc())))
        .scalars()
        .all()
    )
    return [RetentionRuleOut.model_validate(r) for r in rows]


@retention_router.patch(
    "/rules/{rule_id}",
    response_model=RetentionRuleOut,
    summary="保存期間ルール更新",
)
async def update_retention_rule(
    rule_id: int,
    payload: RetentionRuleUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(_ADMIN),
) -> RetentionRuleOut:
    rule = await session.get(RetentionRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="rule not found")
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(rule, key, value)
    rule.updated_by = current_user.db_id
    await session.flush()
    return RetentionRuleOut.model_validate(rule)


@retention_router.post(
    "/run",
    response_model=RetentionRunOut,
    summary="保存期間ポリシー適用（即時実行）",
)
async def run_retention(
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(_ADMIN),
) -> RetentionRunOut:
    await retention_service.ensure_default_rules(session)
    stats = await retention_service.enforce_ai_retention(
        session,
        actor_id=current_user.db_id,
    )
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="retention.delete",
        target_type="retention",
        target_id=None,
        payload={"after": stats},
        request=request,
    )
    return RetentionRunOut(**stats)


# ---------------------------------------------------------------------------
# 監査アンカー（WORM 相当）
# ---------------------------------------------------------------------------

anchor_router = APIRouter(prefix="/audit/anchor", tags=["audit-anchor"])


@anchor_router.post(
    "/create",
    response_model=AuditAnchorOut,
    status_code=status.HTTP_201_CREATED,
    summary="日次監査アンカー作成",
)
async def create_anchor(
    request: Request,
    anchor_date: date | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(_ADMIN_OR_AUDITOR),
) -> AuditAnchorOut:
    try:
        anchor = await create_daily_anchor(
            session,
            anchor_date=anchor_date,
            actor_id=current_user.db_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="audit.anchor.create",
        target_type="audit_anchors",
        target_id=anchor.id,
        payload={"after": {"anchor_date": anchor.anchor_date.isoformat()}},
        request=request,
    )
    return AuditAnchorOut(
        id=anchor.id,
        anchor_date=anchor.anchor_date,
        start_event_id=anchor.start_event_id,
        end_event_id=anchor.end_event_id,
        event_count=anchor.event_count,
        aggregate_hash=anchor.aggregate_hash,
        signature=anchor.signature,
        external_sink=anchor.external_sink,
        external_ref=anchor.external_ref,
        anchored_at=anchor.anchored_at,
    )


@anchor_router.get(
    "/verify",
    response_model=AuditAnchorVerifyOut,
    summary="監査アンカー検証",
)
async def verify_anchor_endpoint(
    anchor_date: date,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(_ADMIN_OR_AUDITOR),
) -> AuditAnchorVerifyOut:
    return AuditAnchorVerifyOut(**await verify_anchor(session, anchor_date=anchor_date))


# ---------------------------------------------------------------------------
# Sentinel / 外部転送状態
# ---------------------------------------------------------------------------

admin_router = APIRouter(prefix="/admin", tags=["admin"])


@admin_router.get(
    "/sentinel/status",
    response_model=SentinelStatusOut,
    summary="Sentinel 転送設定状態",
)
async def sentinel_status(
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(_ADMIN_OR_AUDITOR),
) -> SentinelStatusOut:
    return SentinelStatusOut(
        enabled=sentinel_forwarder.is_configured() or _sentinel_enabled_raw(),
        configured=sentinel_forwarder.is_configured(),
        configuration_errors=sentinel_forwarder.configuration_errors(),
    )


def _sentinel_enabled_raw() -> bool:
    from app.core.config import get_settings

    return get_settings().sentinel_enabled
