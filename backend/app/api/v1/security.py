"""セキュリティ・内部統制エンドポイント（P0-6）.

- 案件単位 ACL（外部顧問弁護士等の限定アクセス）
- リーガルホールド
- 保持期間設定（AI 入出力の保存期間・削除）
- 監査ログ WORM 相当外部保存 + Sentinel 転送
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import CurrentUser, get_current_user, require_role
from app.models.legal_hold import LegalHoldCase
from app.schemas.security import (
    AccessGrantCreate,
    AccessGrantOut,
    AuditExportCreate,
    AuditExportJobOut,
    AuditExportOut,
    LegalHoldCreate,
    LegalHoldOut,
    RetentionSettingsIn,
    RetentionSettingsOut,
)
from app.services import (
    access_control,
    audit_export_service,
    audit_service,
    legal_hold_service,
    retention_service,
)

router = APIRouter(prefix="/security", tags=["security"])


@router.get(
    "/access-grants",
    response_model=list[AccessGrantOut],
    summary="契約アクセス権限一覧",
)
async def list_access_grants(
    contract_id: int = Query(..., description="対象契約 ID"),
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[AccessGrantOut]:
    """admin/auditor は全件、それ以外は自分が drafter の契約のみ."""
    if current_user.role not in {"admin", "auditor"}:
        from sqlalchemy import select

        from app.models.contract import Contract

        contract = (
            await session.execute(select(Contract).where(Contract.id == contract_id))
        ).scalar_one_or_none()
        if contract is None or contract.drafter_id != current_user.db_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    grants = await access_control.list_grants(session, contract_id=contract_id)
    return [AccessGrantOut.model_validate(g) for g in grants]


@router.post(
    "/access-grants",
    response_model=AccessGrantOut,
    status_code=status.HTTP_201_CREATED,
    summary="案件限定アクセス付与",
)
async def create_access_grant(
    payload: AccessGrantCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_role("admin", "auditor")),
) -> AccessGrantOut:
    grant = await access_control.grant_access(
        session,
        contract_id=payload.contract_id,
        user_id=payload.user_id,
        access_level=payload.access_level,
        granted_by=current_user.db_id,
        ethical_wall=payload.ethical_wall,
        expires_at=payload.expires_at,
    )
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="access.grant",
        target_type="contracts",
        target_id=payload.contract_id,
        request=request,
        payload={
            "grant_id": grant.id,
            "user_id": payload.user_id,
            "access_level": payload.access_level,
            "ethical_wall": payload.ethical_wall,
        },
    )
    return AccessGrantOut.model_validate(grant)


@router.delete(
    "/access-grants/{grant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="案件限定アクセス取消",
)
async def revoke_access_grant(
    grant_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_role("admin", "auditor")),
) -> None:
    ok = await access_control.revoke_access(
        session,
        grant_id=grant_id,
        actor_id=current_user.db_id or 0,
    )
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="grant not found")
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="access.revoke",
        target_type="contract_access_grants",
        target_id=grant_id,
        request=request,
        payload={},
    )


@router.get("/legal-holds", response_model=list[LegalHoldOut], summary="リーガルホールド一覧")
async def list_legal_holds(
    active: bool = Query(default=False),
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_role("admin", "auditor")),
) -> list[LegalHoldOut]:
    holds = await legal_hold_service.list_legal_holds(session, active_only=active)
    return [LegalHoldOut.model_validate(h) for h in holds]


@router.post(
    "/legal-holds",
    response_model=LegalHoldOut,
    status_code=status.HTTP_201_CREATED,
    summary="リーガルホールド開始",
)
async def start_legal_hold(
    payload: LegalHoldCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_role("admin", "auditor")),
) -> LegalHoldOut:
    try:
        hold = await legal_hold_service.start_legal_hold(
            session,
            contract_id=payload.contract_id,
            reason=payload.reason,
            requested_by=current_user.db_id,
            notes=payload.notes,
        )
    except legal_hold_service.LegalHoldError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="legal_hold.start",
        target_type="contracts",
        target_id=payload.contract_id,
        request=request,
        payload={"hold_id": hold.id},
    )
    return LegalHoldOut.model_validate(hold)


@router.patch(
    "/legal-holds/{hold_id}/end",
    response_model=LegalHoldOut,
    summary="リーガルホールド終了",
)
async def end_legal_hold(
    hold_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_role("admin", "auditor")),
) -> LegalHoldOut:
    ok = await legal_hold_service.end_legal_hold(
        session, hold_id=hold_id, actor_id=current_user.db_id or 0
    )
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="hold not found")
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="legal_hold.end",
        target_type="legal_hold_cases",
        target_id=hold_id,
        request=request,
        payload={},
    )
    hold = await session.get(LegalHoldCase, hold_id)
    return LegalHoldOut.model_validate(hold)


@router.get(
    "/retention-settings",
    response_model=RetentionSettingsOut,
    summary="保持期間設定の取得",
)
async def get_retention_settings(
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_role("admin", "auditor")),
) -> RetentionSettingsOut:
    return RetentionSettingsOut(settings=await retention_service.get_settings(session))


@router.put(
    "/retention-settings",
    response_model=RetentionSettingsOut,
    summary="保持期間設定の更新",
)
async def update_retention_settings(
    payload: RetentionSettingsIn,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_role("admin")),
) -> RetentionSettingsOut:
    try:
        updated = await retention_service.update_settings(
            session, values=payload.settings, actor_id=current_user.db_id
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="security.retention.update",
        target_type="security_settings",
        target_id=None,
        request=request,
        payload={"keys": sorted(payload.settings)},
    )
    return RetentionSettingsOut(settings=updated)


@router.post(
    "/audit-exports",
    response_model=AuditExportOut,
    summary="監査ログ外部保存（WORM 相当）の実行",
)
async def create_audit_export(
    payload: AuditExportCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_role("admin", "auditor")),
) -> AuditExportOut:
    if payload.until <= payload.since:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="until must be after since",
        )
    result = await audit_export_service.export_audit_batch(
        session,
        since=payload.since,
        until=payload.until,
        actor_id=current_user.db_id,
    )
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="audit.export",
        target_type="audit_export_jobs",
        target_id=None,
        request=request,
        payload={
            "job_no": result["job_no"],
            "record_count": result["record_count"],
            "merkle_root": result["merkle_root"],
        },
    )
    return AuditExportOut(**result)


@router.get(
    "/audit-exports",
    response_model=list[AuditExportJobOut],
    summary="監査出力ジョブ一覧",
)
async def list_audit_exports(
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_role("admin", "auditor")),
) -> list[AuditExportJobOut]:
    jobs = await audit_export_service.list_export_jobs(session)
    return [AuditExportJobOut.model_validate(j) for j in jobs]
