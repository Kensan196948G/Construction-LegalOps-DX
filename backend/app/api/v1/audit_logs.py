"""監査ログエンドポイント。

- GET `/audit-logs` : ページング・絞り込み (target_type/target_id/action/actor_id/from/to)
- POST `/audit-logs/verify` : ハッシュチェーン整合性検証
- GET `/audit-logs/export` : CSV エクスポート

監査ログ自体への書込は API では行わない。各 API ハンドラ内で `audit_service.log(...)` 経由で記録。
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.user import User
from app.schemas.audit_log import (
    AuditLogOut,
    AuditVerifyResponse,
)
from app.schemas.common import Page
from app.services import audit_service

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


@router.get(
    "",
    response_model=Page[AuditLogOut],
    summary="監査ログ一覧",
    description="auditor / admin のみ。target_type/action/actor_id/期間で絞り込み。",
)
async def list_audit_logs(
    target_type: Optional[str] = Query(default=None),
    target_id: Optional[int] = Query(default=None),
    action: Optional[str] = Query(default=None),
    actor_id: Optional[int] = Query(default=None),
    date_from: Optional[datetime] = Query(default=None, alias="from"),
    date_to: Optional[datetime] = Query(default=None, alias="to"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_role("admin", "auditor")),
) -> Page[AuditLogOut]:
    items, total = await audit_service.list_logs(
        session,
        target_type=target_type,
        target_id=target_id,
        action=action,
        actor_id=actor_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        size=size,
    )
    return Page[AuditLogOut](items=items, total=total, page=page, size=size)


@router.post(
    "/verify",
    response_model=AuditVerifyResponse,
    summary="ハッシュチェーン整合性検証",
    description="全件 (もしくは期間指定) でハッシュチェーンを再計算し、改ざんを検出する。",
)
async def verify_audit_chain(
    request: Request,
    date_from: Optional[datetime] = Query(default=None, alias="from"),
    date_to: Optional[datetime] = Query(default=None, alias="to"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_role("admin", "auditor")),
) -> AuditVerifyResponse:
    result = await audit_service.verify_chain(
        session, date_from=date_from, date_to=date_to
    )
    await audit_service.log(
        session,
        actor_id=current_user.id,
        action="audit.verify",
        target_type="audit_logs",
        target_id=None,
        payload={"verified": result.verified, "broken_at": result.broken_at},
        request=request,
    )
    return result


@router.get(
    "/export",
    summary="監査ログ CSV エクスポート",
    description="auditor のみ。期間で絞った監査ログを text/csv でストリーミング。",
    response_class=StreamingResponse,
)
async def export_audit_logs(
    date_from: Optional[datetime] = Query(default=None, alias="from"),
    date_to: Optional[datetime] = Query(default=None, alias="to"),
    target_type: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_role("auditor", "admin")),
) -> StreamingResponse:
    iterator = audit_service.export_csv(
        session,
        date_from=date_from,
        date_to=date_to,
        target_type=target_type,
    )
    headers = {"Content-Disposition": "attachment; filename=audit_logs.csv"}
    return StreamingResponse(iterator, media_type="text/csv", headers=headers)
