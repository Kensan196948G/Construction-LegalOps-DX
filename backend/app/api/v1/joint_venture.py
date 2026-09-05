"""JV（共同企業体）管理エンドポイント（#61〜#70）."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import CurrentUser, require_role
from app.schemas.common import Page
from app.schemas.joint_venture import (
    JvAgreementCreate,
    JvAgreementOut,
    JvCreate,
    JvDashboardOut,
    JvDisputeCreate,
    JvDisputeOut,
    JvDisputeRespond,
    JvMemberCreate,
    JvMemberOut,
    JvOut,
    JvSettlementCreate,
    JvSettlementOut,
    JvStatusIn,
)
from app.services import audit_service, jv_service

router = APIRouter(prefix="/joint-ventures", tags=["joint-ventures"])

_READ_ROLES = ("viewer", "drafter", "reviewer", "approver", "admin", "auditor")
_WRITE_ROLES = ("drafter", "reviewer", "approver", "admin")


async def _audit(
    session: AsyncSession,
    request: Request,
    current_user: CurrentUser,
    *,
    action: str,
    target_id: int,
    payload: dict[str, object] | None = None,
) -> None:
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action=action,
        target_type="joint_ventures",
        target_id=target_id,
        request=request,
        payload=payload,
    )


@router.get("", response_model=Page[JvOut], summary="JV 台帳一覧（#61）")
async def list_jvs(
    status_: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> Page[JvOut]:
    items, total = await jv_service.list_jvs(session, status=status_, page=page, size=size)
    return Page[JvOut](
        items=[JvOut.model_validate(i) for i in items], total=total, page=page, size=size
    )


@router.post(
    "",
    response_model=JvOut,
    status_code=status.HTTP_201_CREATED,
    summary="JV を登録（#61・JV-YYYY-NNNNNN 採番）",
)
async def create_jv(
    body: JvCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> JvOut:
    row = await jv_service.create_jv(
        session,
        actor_id=current_user.db_id,
        name=body.name,
        representative_name=body.representative_name,
        works_title=body.works_title,
        contract_id=body.contract_id,
        start_date=body.start_date,
        end_date=body.end_date,
        notes=body.notes,
    )
    await _audit(
        session,
        request,
        current_user,
        action="jv.create",
        target_id=row.id,
        payload={"jv_no": row.jv_no, "name": row.name},
    )
    return JvOut.model_validate(row)


@router.get("/{jv_id}", response_model=JvOut, summary="JV 詳細")
async def get_jv(
    jv_id: int,
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> JvOut:
    row = await jv_service.get_jv(session, jv_id=jv_id)
    return JvOut.model_validate(row)


@router.post(
    "/{jv_id}/status",
    response_model=JvOut,
    summary="JV の状態遷移（#61・prospecting→active→completed/dissolved）",
)
async def set_status(
    jv_id: int,
    body: JvStatusIn,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> JvOut:
    row = await jv_service.set_jv_status(
        session,
        jv_id=jv_id,
        actor_id=current_user.db_id,
        status=body.status,
    )
    await _audit(
        session,
        request,
        current_user,
        action="jv.status",
        target_id=row.id,
        payload={"jv_no": row.jv_no, "status": row.status},
    )
    return JvOut.model_validate(row)


@router.get(
    "/{jv_id}/members",
    response_model=list[JvMemberOut],
    summary="JV 構成員一覧（#63/#64/#65）",
)
async def list_members(
    jv_id: int,
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> list[JvMemberOut]:
    rows = await jv_service.list_members(session, jv_id=jv_id)
    return [JvMemberOut.model_validate(m) for m in rows]


@router.post(
    "/{jv_id}/members",
    response_model=JvMemberOut,
    status_code=status.HTTP_201_CREATED,
    summary="JV 構成員を追加（#63 代表は 1 社・#64 出資比率合計 100% 検証）",
)
async def add_member(
    jv_id: int,
    body: JvMemberCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> JvMemberOut:
    row = await jv_service.add_member(
        session,
        jv_id=jv_id,
        actor_id=current_user.db_id,
        company_name=body.company_name,
        role=body.role,
        equity_ratio=body.equity_ratio,
        profit_share_ratio=body.profit_share_ratio,
        contact_email=body.contact_email,
        notes=body.notes,
    )
    await _audit(
        session,
        request,
        current_user,
        action="jv.member_add",
        target_id=jv_id,
        payload={"company": row.company_name, "role": row.role},
    )
    return JvMemberOut.model_validate(row)


@router.get(
    "/{jv_id}/agreements",
    response_model=list[JvAgreementOut],
    summary="JV 協定書一覧（#62）",
)
async def list_agreements(
    jv_id: int,
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> list[JvAgreementOut]:
    rows = await jv_service.list_agreements(session, jv_id=jv_id)
    return [JvAgreementOut.model_validate(a) for a in rows]


@router.post(
    "/{jv_id}/agreements",
    response_model=JvAgreementOut,
    status_code=status.HTTP_201_CREATED,
    summary="JV 協定書を登録（#62・signed_at あれば signed）",
)
async def create_agreement(
    jv_id: int,
    body: JvAgreementCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> JvAgreementOut:
    row = await jv_service.create_agreement(
        session,
        jv_id=jv_id,
        actor_id=current_user.db_id,
        title=body.title,
        summary=body.summary,
        signed_at=body.signed_at,
        document_url=body.document_url,
    )
    await _audit(
        session,
        request,
        current_user,
        action="jv.agreement_create",
        target_id=jv_id,
        payload={"agreement_no": row.agreement_no, "status": row.status},
    )
    return JvAgreementOut.model_validate(row)


@router.post(
    "/agreements/{agreement_id}/terminate",
    response_model=JvAgreementOut,
    summary="JV 協定書を終了（#62・signed → terminated）",
)
async def terminate_agreement(
    agreement_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> JvAgreementOut:
    row = await jv_service.terminate_agreement(
        session, agreement_id=agreement_id, actor_id=current_user.db_id
    )
    await _audit(
        session,
        request,
        current_user,
        action="jv.agreement_terminate",
        target_id=row.jv_id,
        payload={"agreement_no": row.agreement_no},
    )
    return JvAgreementOut.model_validate(row)


@router.get(
    "/{jv_id}/disputes",
    response_model=list[JvDisputeOut],
    summary="JV 内紛争・請求一覧（#69）",
)
async def list_disputes(
    jv_id: int,
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> list[JvDisputeOut]:
    rows = await jv_service.list_disputes(session, jv_id=jv_id)
    return [JvDisputeOut.model_validate(d) for d in rows]


@router.post(
    "/{jv_id}/disputes",
    response_model=JvDisputeOut,
    status_code=status.HTTP_201_CREATED,
    summary="JV 内紛争・請求を記録（#69・JVD-YYYY-NNNNNN 採番）",
)
async def create_dispute(
    jv_id: int,
    body: JvDisputeCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> JvDisputeOut:
    row = await jv_service.create_dispute(
        session,
        jv_id=jv_id,
        actor_id=current_user.db_id,
        title=body.title,
        claimant_name=body.claimant_name,
        respondent_name=body.respondent_name,
        amount_claimed_jpy=body.amount_claimed_jpy,
        detail=body.detail,
    )
    await _audit(
        session,
        request,
        current_user,
        action="jv.dispute_create",
        target_id=jv_id,
        payload={"dispute_no": row.dispute_no},
    )
    return JvDisputeOut.model_validate(row)


@router.post(
    "/disputes/{dispute_id}/respond",
    response_model=JvDisputeOut,
    summary="JV 内紛争へ回答（#69・open → responded）",
)
async def respond_dispute(
    dispute_id: int,
    body: JvDisputeRespond,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> JvDisputeOut:
    row = await jv_service.respond_dispute(
        session, dispute_id=dispute_id, actor_id=current_user.db_id,
        response_note=body.response_note,
    )
    await _audit(
        session,
        request,
        current_user,
        action="jv.dispute_respond",
        target_id=row.jv_id,
        payload={"dispute_no": row.dispute_no, "status": row.status},
    )
    return JvDisputeOut.model_validate(row)


@router.get(
    "/{jv_id}/settlements",
    response_model=list[JvSettlementOut],
    summary="JV 終了・清算一覧（#70）",
)
async def list_settlements(
    jv_id: int,
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> list[JvSettlementOut]:
    rows = await jv_service.list_settlements(session, jv_id=jv_id)
    return [JvSettlementOut.model_validate(s) for s in rows]


@router.post(
    "/{jv_id}/settlements",
    response_model=JvSettlementOut,
    status_code=status.HTTP_201_CREATED,
    summary="JV 清算を記録（#70・completed/dissolved のみ・JVS-YYYY-NNNNNN）",
)
async def create_settlement(
    jv_id: int,
    body: JvSettlementCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> JvSettlementOut:
    row = await jv_service.create_settlement(
        session,
        jv_id=jv_id,
        actor_id=current_user.db_id,
        title=body.title,
        settlement_amount_jpy=body.settlement_amount_jpy,
        detail=body.detail,
    )
    await _audit(
        session,
        request,
        current_user,
        action="jv.settlement_create",
        target_id=jv_id,
        payload={"settlement_no": row.settlement_no},
    )
    return JvSettlementOut.model_validate(row)


@router.post(
    "/settlements/{settlement_id}/settle",
    response_model=JvSettlementOut,
    summary="JV 清算を完了（#70・pending → settled）",
)
async def settle(
    settlement_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_role(*_WRITE_ROLES)),
) -> JvSettlementOut:
    row = await jv_service.settle(
        session, settlement_id=settlement_id, actor_id=current_user.db_id
    )
    await _audit(
        session,
        request,
        current_user,
        action="jv.settle",
        target_id=row.jv_id,
        payload={"settlement_no": row.settlement_no, "status": row.status},
    )
    return JvSettlementOut.model_validate(row)


@router.get(
    "/dashboard/summary",
    response_model=JvDashboardOut,
    summary="JV サマリー（状態別集計・協定/紛争/清算件数）",
)
async def dashboard(
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> JvDashboardOut:
    result = await jv_service.dashboard_summary(session)
    return JvDashboardOut(**result)
