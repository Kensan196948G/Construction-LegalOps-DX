"""Legal Matter Management エンドポイント（Issue #101・#71〜#84）."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import CurrentUser, require_role
from app.models.contract import Contract
from app.schemas.common import Page
from app.schemas.matter import (
    MatterAssignIn,
    MatterContractIn,
    MatterContractOut,
    MatterCreate,
    MatterEventOut,
    MatterLegalHoldIn,
    MatterNoteIn,
    MatterOut,
    MatterStatusIn,
    MatterUpdate,
)
from app.services import audit_service, matter_service

router = APIRouter(prefix="/matters", tags=["matters"])

_READ_ROLES = ("viewer", "drafter", "reviewer", "approver", "admin", "auditor")
_WRITE_ROLES = ("drafter", "reviewer", "approver", "admin")


async def _audit(
    session: AsyncSession,
    request: Request,
    current_user: CurrentUser,
    *,
    action: str,
    target_id: int,
) -> None:
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action=action,
        target_type="legal_matters",
        target_id=target_id,
        request=request,
        payload=None,
    )


@router.get(
    "",
    response_model=Page[MatterOut],
    summary="法務案件一覧（Matter 台帳・#71）",
)
async def list_matters(
    status_: str | None = Query(default=None, alias="status"),
    matter_type: str | None = Query(default=None, alias="type"),
    assignee_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> Page[MatterOut]:
    items, total = await matter_service.list_matters(
        session,
        status=status_,
        matter_type=matter_type,
        assignee_id=assignee_id,
        page=page,
        size=size,
    )
    return Page[MatterOut](
        items=[MatterOut.model_validate(m) for m in items], total=total, page=page, size=size
    )


@router.post(
    "",
    response_model=MatterOut,
    status_code=status.HTTP_201_CREATED,
    summary="Matter 作成（ID 採番 MT-YYYY-NNNNNN・#72）",
)
async def create_matter(
    body: MatterCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> MatterOut:
    matter = await matter_service.create_matter(
        session,
        actor_id=current_user.db_id,
        title=body.title,
        matter_type=body.matter_type.value
        if hasattr(body.matter_type, "value")
        else str(body.matter_type),
        description=body.description,
        priority=body.priority.value if hasattr(body.priority, "value") else str(body.priority),
        assignee_id=body.assignee_id,
        source_type=body.source_type,
        source_id=body.source_id,
        contract_ids=body.contract_ids,
        legal_hold_case_id=body.legal_hold_case_id,
    )
    await _audit(session, request, current_user, action="matter.create", target_id=matter.id)
    return MatterOut.model_validate(matter)


@router.get(
    "/{matter_id}",
    response_model=MatterOut,
    summary="Matter 詳細",
)
async def get_matter(
    matter_id: int,
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> MatterOut:
    matter = await matter_service.get_matter(session, matter_id=matter_id)
    return MatterOut.model_validate(matter)


@router.patch(
    "/{matter_id}",
    response_model=MatterOut,
    summary="Matter 基本情報更新",
)
async def update_matter(
    matter_id: int,
    body: MatterUpdate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> MatterOut:
    matter = await matter_service.get_matter(session, matter_id=matter_id)
    if matter.status == "closed":
        raise HTTPException(status_code=409, detail="CLOSED の Matter は更新できません。")
    if body.title is not None:
        matter.title = body.title
    if body.description is not None:
        matter.description = body.description
    if body.priority is not None:
        from app.models.enums import MatterPriority

        matter.priority = (
            body.priority.value
            if hasattr(body.priority, "value")
            else MatterPriority(body.priority).value
        )
    matter.updated_by = current_user.db_id
    await session.flush()
    await session.refresh(matter)
    await _audit(session, request, current_user, action="matter.update", target_id=matter.id)
    return MatterOut.model_validate(matter)


@router.post(
    "/{matter_id}/status",
    response_model=MatterOut,
    summary="Matter 状態遷移（open/in_progress/waiting/on_hold/closed）",
)
async def set_status(
    matter_id: int,
    body: MatterStatusIn,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> MatterOut:
    matter = await matter_service.set_status(
        session,
        matter_id=matter_id,
        actor_id=current_user.db_id,
        status=body.status.value if hasattr(body.status, "value") else str(body.status),
        note=body.note,
    )
    await _audit(session, request, current_user, action="matter.status", target_id=matter.id)
    return MatterOut.model_validate(matter)


@router.post(
    "/{matter_id}/assign",
    response_model=MatterOut,
    summary="担当法務アサイン（#74・null で解除）",
)
async def assign_assignee(
    matter_id: int,
    body: MatterAssignIn,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> MatterOut:
    matter = await matter_service.assign_assignee(
        session,
        matter_id=matter_id,
        actor_id=current_user.db_id,
        assignee_id=body.assignee_id,
        note=body.note,
    )
    await _audit(session, request, current_user, action="matter.assign", target_id=matter.id)
    return MatterOut.model_validate(matter)


@router.post(
    "/{matter_id}/contracts",
    response_model=MatterOut,
    summary="関係契約をリンク（#79）",
)
async def link_contract(
    matter_id: int,
    body: MatterContractIn,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> MatterOut:
    matter = await matter_service.link_contract(
        session,
        matter_id=matter_id,
        actor_id=current_user.db_id,
        contract_id=body.contract_id,
    )
    await _audit(session, request, current_user, action="matter.contract_link", target_id=matter.id)
    return MatterOut.model_validate(matter)


@router.delete(
    "/{matter_id}/contracts/{contract_id}",
    response_model=MatterOut,
    summary="関係契約リンクを解除",
)
async def unlink_contract(
    matter_id: int,
    contract_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> MatterOut:
    matter = await matter_service.unlink_contract(
        session,
        matter_id=matter_id,
        actor_id=current_user.db_id,
        contract_id=contract_id,
    )
    await _audit(
        session, request, current_user, action="matter.contract_unlink", target_id=matter.id
    )
    return MatterOut.model_validate(matter)


@router.get(
    "/{matter_id}/contracts",
    response_model=list[MatterContractOut],
    summary="関係契約一覧（#79）",
)
async def list_contracts(
    matter_id: int,
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> list[MatterContractOut]:
    # lazy relationship は async では使わず、association table を直接参照する。
    from app.models.matter import matter_contracts_table

    await matter_service.get_matter(session, matter_id=matter_id)
    link_rows = (
        (
            await session.execute(
                select(matter_contracts_table.c.contract_id).where(
                    matter_contracts_table.c.matter_id == matter_id
                )
            )
        )
        .scalars()
        .all()
    )
    if not link_rows:
        return []
    rows = (
        (await session.execute(select(Contract).where(Contract.id.in_(list(link_rows)))))
        .scalars()
        .all()
    )
    by_id = {c.id: c for c in rows}
    return [
        MatterContractOut(
            contract_id=cid,
            contract_no=by_id[cid].contract_no,
            title=by_id[cid].title,
        )
        for cid in link_rows
        if cid in by_id
    ]


@router.post(
    "/{matter_id}/legal-hold",
    response_model=MatterOut,
    summary="Legal Hold 連動（#82・body 空/null で解除）",
)
async def set_legal_hold(
    matter_id: int,
    body: MatterLegalHoldIn,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> MatterOut:
    matter = await matter_service.set_legal_hold(
        session,
        matter_id=matter_id,
        actor_id=current_user.db_id,
        legal_hold_case_id=body.legal_hold_case_id,
    )
    await _audit(session, request, current_user, action="matter.legal_hold", target_id=matter.id)
    return MatterOut.model_validate(matter)


@router.get(
    "/{matter_id}/events",
    response_model=list[MatterEventOut],
    summary="Matter タイムライン（#78・追記専用）",
)
async def list_events(
    matter_id: int,
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> list[MatterEventOut]:
    events = await matter_service.list_events(session, matter_id=matter_id)
    return [MatterEventOut.model_validate(e) for e in events]


@router.post(
    "/{matter_id}/notes",
    response_model=MatterEventOut,
    status_code=status.HTTP_201_CREATED,
    summary="タイムラインへメモ追記（#78）",
)
async def add_note(
    matter_id: int,
    body: MatterNoteIn,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> MatterEventOut:
    event = await matter_service.add_note(
        session, matter_id=matter_id, actor_id=current_user.db_id, note=body.note
    )
    await _audit(session, request, current_user, action="matter.note", target_id=matter_id)
    return MatterEventOut.model_validate(event)
