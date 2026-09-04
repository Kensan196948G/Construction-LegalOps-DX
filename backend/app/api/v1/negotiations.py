"""契約交渉・Redline 管理エンドポイント（ロードマップ #5〜#8 / Issue #98）.

- ``POST /contracts/{contract_id}/negotiations`` … 交渉イベント記録
  （redline=修正提案 / demand / concession / comment）
- ``GET  /contracts/{contract_id}/negotiations`` … 交渉履歴タイムライン
- ``POST /contracts/{contract_id}/clauses/{clause_id}/status`` … 条項ステータス
- ``POST /contracts/{contract_id}/clauses/{clause_id}/owner`` … 条項オーナー割当
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import CurrentUser, require_role
from app.schemas.common import Page
from app.schemas.negotiation import (
    ClauseNegotiationStateOut,
    ClauseOwnerIn,
    ClauseStatusIn,
    NegotiationEventIn,
    NegotiationEventOut,
)
from app.services import audit_service, negotiation_service

negotiations_router = APIRouter(
    prefix="/contracts/{contract_id}/negotiations", tags=["negotiations"]
)
clauses_router = APIRouter(
    prefix="/contracts/{contract_id}/clauses", tags=["negotiations"]
)

_READ_ROLES = ("viewer", "drafter", "reviewer", "approver", "admin", "auditor")
_WRITE_ROLES = ("drafter", "reviewer", "approver", "admin")


async def _audit(
    session: AsyncSession,
    request: Request,
    current_user: CurrentUser,
    *,
    action: str,
    target_type: str,
    target_id: Any,
    payload: dict[str, Any] | None,
) -> None:
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        request=request,
        payload=payload,
    )


@negotiations_router.get(
    "",
    response_model=Page[NegotiationEventOut],
    summary="交渉履歴タイムライン（新しい順）",
)
async def list_negotiations(
    contract_id: int,
    clause_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> Page[NegotiationEventOut]:
    items, total = await negotiation_service.list_events(
        session, contract_id=contract_id, clause_id=clause_id, page=page, size=size
    )
    return Page[NegotiationEventOut](
        items=[NegotiationEventOut.model_validate(i) for i in items],
        total=total,
        page=page,
        size=size,
    )


@negotiations_router.post(
    "",
    response_model=NegotiationEventOut,
    status_code=status.HTTP_201_CREATED,
    summary="交渉イベント記録（redline / demand / concession / comment）",
)
async def add_negotiation_event(
    contract_id: int,
    body: NegotiationEventIn,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> NegotiationEventOut:
    event = await negotiation_service.add_event(
        session,
        contract_id=contract_id,
        actor_id=current_user.db_id,
        action=body.action.value if hasattr(body.action, "value") else str(body.action),
        clause_id=body.clause_id,
        round_no=body.round_no,
        note=body.note,
        proposed_text=body.proposed_text,
    )
    await _audit(
        session,
        request,
        current_user,
        action="negotiation.add",
        target_type="contracts",
        target_id=contract_id,
        payload={
            "event_id": event.id,
            "action": event.action,
            "clause_id": event.clause_id,
        },
    )
    return NegotiationEventOut.model_validate(event)


@clauses_router.post(
    "/{clause_id}/status",
    response_model=ClauseNegotiationStateOut,
    summary="条項ステータス更新（Accepted / Rejected / Negotiating）",
)
async def update_clause_status(
    contract_id: int,
    clause_id: int,
    body: ClauseStatusIn,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> ClauseNegotiationStateOut:
    clause = await negotiation_service.set_clause_status(
        session,
        contract_id=contract_id,
        clause_id=clause_id,
        actor_id=current_user.db_id,
        status=body.status.value if hasattr(body.status, "value") else str(body.status),
        note=body.note,
    )
    await _audit(
        session,
        request,
        current_user,
        action="clause.status",
        target_type="clauses",
        target_id=clause.id,
        payload={"status": clause.negotiation_status},
    )
    return ClauseNegotiationStateOut.model_validate(clause)


@clauses_router.post(
    "/{clause_id}/owner",
    response_model=ClauseNegotiationStateOut,
    summary="条項オーナー割当（法務・工事・営業・購買 等）",
)
async def assign_clause_owner(
    contract_id: int,
    clause_id: int,
    body: ClauseOwnerIn,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> ClauseNegotiationStateOut:
    clause = await negotiation_service.assign_owner(
        session,
        contract_id=contract_id,
        clause_id=clause_id,
        actor_id=current_user.db_id,
        owner=body.owner.value if hasattr(body.owner, "value") else str(body.owner),
        note=body.note,
    )
    await _audit(
        session,
        request,
        current_user,
        action="clause.owner",
        target_type="clauses",
        target_id=clause.id,
        payload={"owner": clause.clause_owner},
    )
    return ClauseNegotiationStateOut.model_validate(clause)
