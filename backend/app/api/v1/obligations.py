"""契約義務（Obligations Calendar）エンドポイント（Issue #99・#9〜#13）.

- ``GET  /obligations`` … カレンダー一覧（contract/type/status/bucket/期間絞り込み）
- ``PATCH /obligations/{id}`` … 内容・期限・担当更新（open/in_progress のみ）
- ``POST  /obligations/{id}/complete`` … 完了
- ``POST  /obligations/{id}/waive`` … 放棄
- ``GET   /obligations/renewal-check`` … 自動更新・解約通知期限チェック（#12）
- ``POST  /contracts/{contract_id}/obligations`` … 義務登録
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import CurrentUser, require_role
from app.schemas.common import Page
from app.schemas.obligation import (
    ObligationCreate,
    ObligationOut,
    ObligationUpdate,
    RenewalCheckOut,
)
from app.services import audit_service, obligation_service

obligations_router = APIRouter(prefix="/obligations", tags=["obligations"])
contract_obligations_router = APIRouter(
    prefix="/contracts/{contract_id}/obligations", tags=["obligations"]
)

_READ_ROLES = ("viewer", "drafter", "reviewer", "approver", "admin", "auditor")
_WRITE_ROLES = ("drafter", "reviewer", "approver", "admin")


async def _audit(
    session: AsyncSession,
    request: Request,
    current_user: CurrentUser,
    *,
    action: str,
    obligation_id: int,
) -> None:
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action=action,
        target_type="contract_obligations",
        target_id=obligation_id,
        request=request,
        payload=None,
    )


@obligations_router.get(
    "",
    response_model=Page[ObligationOut],
    summary="契約義務一覧（Obligations Calendar）",
)
async def list_obligations(
    contract_id: int | None = Query(default=None),
    obligation_type: str | None = Query(default=None, alias="type"),
    status_: str | None = Query(default=None, alias="status"),
    bucket: str | None = Query(
        default=None,
        description="overdue / within_30 / within_60 / future（未完了・due_date ありのみ）",
    ),
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> Page[ObligationOut]:
    items, total = await obligation_service.list_obligations(
        session,
        contract_id=contract_id,
        obligation_type=obligation_type,
        status=status_,
        bucket=bucket,
        date_from=date_from,
        date_to=date_to,
        page=page,
        size=size,
    )
    return Page[ObligationOut](
        items=[ObligationOut.model_validate(o) for o in items],
        total=total,
        page=page,
        size=size,
    )


@obligations_router.get(
    "/renewal-check",
    response_model=list[RenewalCheckOut],
    summary="自動更新・解約通知期限チェック（#12）",
)
async def renewal_check(
    contract_id: int | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> list[RenewalCheckOut]:
    rows = await obligation_service.renewal_check(session, contract_id=contract_id)
    return [RenewalCheckOut(**row) for row in rows]


@obligations_router.patch(
    "/{obligation_id}",
    response_model=ObligationOut,
    summary="契約義務の更新",
)
async def update_obligation(
    obligation_id: int,
    body: ObligationUpdate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> ObligationOut:
    obligation = await obligation_service.update_obligation(
        session,
        obligation_id=obligation_id,
        actor_id=current_user.db_id,
        title=body.title,
        description=body.description,
        due_date=body.due_date,
        assignee_id=body.assignee_id,
        status=body.status.value if body.status is not None else None,
    )
    await _audit(
        session, request, current_user, action="obligation.update", obligation_id=obligation.id
    )
    return ObligationOut.model_validate(obligation)


@obligations_router.post(
    "/{obligation_id}/complete",
    response_model=ObligationOut,
    summary="契約義務の完了",
)
async def complete_obligation(
    obligation_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> ObligationOut:
    obligation = await obligation_service.complete_obligation(
        session, obligation_id=obligation_id, actor_id=current_user.db_id
    )
    await _audit(
        session, request, current_user, action="obligation.complete", obligation_id=obligation.id
    )
    return ObligationOut.model_validate(obligation)


@obligations_router.post(
    "/{obligation_id}/waive",
    response_model=ObligationOut,
    summary="契約義務の放棄",
)
async def waive_obligation(
    obligation_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> ObligationOut:
    obligation = await obligation_service.waive_obligation(
        session, obligation_id=obligation_id, actor_id=current_user.db_id
    )
    await _audit(
        session, request, current_user, action="obligation.waive", obligation_id=obligation.id
    )
    return ObligationOut.model_validate(obligation)


@contract_obligations_router.post(
    "",
    response_model=ObligationOut,
    status_code=status.HTTP_201_CREATED,
    summary="契約へ義務を登録",
)
async def create_contract_obligation(
    contract_id: int,
    body: ObligationCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> ObligationOut:
    obligation = await obligation_service.create_obligation(
        session,
        contract_id=contract_id,
        actor_id=current_user.db_id,
        obligation_type=body.obligation_type.value
        if hasattr(body.obligation_type, "value")
        else str(body.obligation_type),
        title=body.title,
        description=body.description,
        due_date=body.due_date,
        assignee_id=body.assignee_id,
        status=body.status.value if hasattr(body.status, "value") else str(body.status),
    )
    await _audit(
        session, request, current_user, action="obligation.create", obligation_id=obligation.id
    )
    return ObligationOut.model_validate(obligation)
