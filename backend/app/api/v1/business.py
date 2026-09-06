"""高優先業務機能の API（変更契約 / 文書パッケージ / 支払 / 協力会社 / 紛争）."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import CurrentUser, get_current_user, require_role
from app.models.contract import Contract
from app.models.contract_document import ContractDocument
from app.schemas.business import (
    ChangeOrderCreate,
    ChangeOrderEvidenceCreate,
    ChangeOrderEvidenceOut,
    ChangeOrderOut,
    ChangeOrderUpdate,
    ContractDocumentCreate,
    ContractDocumentOut,
    ContractDocumentUpdate,
    DisputeCreate,
    DisputeEvidenceCreate,
    DisputeEvidenceOut,
    DisputeExposureOut,
    DisputeOut,
    DisputeTimelineEventCreate,
    DisputeTimelineEventOut,
    DisputeUpdate,
    DocumentConsistencyOut,
    PartnerCreate,
    PartnerOut,
    PartnerSummaryOut,
    PartnerUpdate,
    PaymentComplianceOut,
)
from app.schemas.common import Page
from app.services import audit_service, change_order_service, dispute_service, partner_service
from app.services.document_consistency import (
    DocumentSnapshot,
    check_consistency,
)
from app.services.document_consistency import (
    to_dict as consistency_to_dict,
)
from app.services.payment_compliance import assess as assess_payment

router = APIRouter(tags=["business"])


async def _get_contract(
    session: AsyncSession,
    contract_id: int,
) -> Contract:
    contract = await session.get(Contract, contract_id)
    if contract is None or contract.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="contract not found")
    return contract


_WRITE_ROLE = require_role("drafter", "reviewer", "approver", "admin")
_ADMIN_ROLE = require_role("admin")


# ---------------------------------------------------------------------------
# 変更契約・クレーム
# ---------------------------------------------------------------------------

change_orders_router = APIRouter(prefix="/change-orders", tags=["change-orders"])


@change_orders_router.get(
    "/impact/{contract_id}",
    summary="原契約＋変更契約の累積影響分析",
)
async def change_order_impact(
    contract_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, object]:
    try:
        return await change_order_service.impact_analysis(
            session, contract_id=contract_id, viewer=current_user
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="contract not found")


@change_orders_router.get(
    "",
    response_model=Page[ChangeOrderOut],
    summary="変更契約・クレーム一覧",
)
async def list_change_orders(
    contract_id: int | None = Query(default=None),
    status_: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Page[ChangeOrderOut]:
    items, total = await change_order_service.list_change_orders(
        session,
        contract_id=contract_id,
        status=status_,
        page=page,
        size=size,
    )
    return Page[ChangeOrderOut](
        items=[ChangeOrderOut.model_validate(i) for i in items],
        total=total,
        page=page,
        size=size,
    )


@change_orders_router.post(
    "",
    response_model=ChangeOrderOut,
    status_code=status.HTTP_201_CREATED,
    summary="変更契約・クレーム登録",
)
async def create_change_order(
    payload: ChangeOrderCreate,
    request: Request,
    contract_id: int = Query(..., description="対象契約 ID"),
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(_WRITE_ROLE),
) -> ChangeOrderOut:
    try:
        order = await change_order_service.create_change_order(
            session,
            contract_id=contract_id,
            actor=current_user,
            data=payload.model_dump(),
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="contract not found")
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="change_order.create",
        target_type="change_orders",
        target_id=order.id,
        payload={"after": payload.model_dump()},
        request=request,
    )
    return ChangeOrderOut.model_validate(order)


@change_orders_router.patch(
    "/{change_order_id}",
    response_model=ChangeOrderOut,
    summary="変更契約・クレーム更新",
)
async def update_change_order(
    change_order_id: int,
    payload: ChangeOrderUpdate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(_WRITE_ROLE),
) -> ChangeOrderOut:
    try:
        order = await change_order_service.update_change_order(
            session,
            change_order_id=change_order_id,
            actor=current_user,
            data=payload.model_dump(exclude_none=True),
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="change order not found")
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="change_order.update",
        target_type="change_orders",
        target_id=order.id,
        payload={"after": payload.model_dump(exclude_unset=True)},
        request=request,
    )
    return ChangeOrderOut.model_validate(order)


@change_orders_router.post(
    "/{change_order_id}/evidence",
    response_model=ChangeOrderEvidenceOut,
    status_code=status.HTTP_201_CREATED,
    summary="変更契約の証拠紐付け",
)
async def add_change_order_evidence(
    change_order_id: int,
    payload: ChangeOrderEvidenceCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(_WRITE_ROLE),
) -> ChangeOrderEvidenceOut:
    try:
        evidence = await change_order_service.add_evidence(
            session,
            change_order_id=change_order_id,
            actor=current_user,
            data=payload.model_dump(),
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="change order not found")
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="change_order.update",
        target_type="change_order_evidence",
        target_id=evidence.id,
        payload={"after": payload.model_dump()},
        request=request,
    )
    return ChangeOrderEvidenceOut.model_validate(evidence)


# ---------------------------------------------------------------------------
# 契約パッケージ文書
# ---------------------------------------------------------------------------

documents_router = APIRouter(prefix="/contracts/{contract_id}/documents", tags=["documents"])


@documents_router.get(
    "",
    response_model=list[ContractDocumentOut],
    summary="契約パッケージ文書一覧",
)
async def list_documents(
    contract_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[ContractDocumentOut]:
    await _get_contract(session, contract_id)
    rows = (
        (
            await session.execute(
                select(ContractDocument)
                .where(
                    ContractDocument.contract_id == contract_id,
                    ContractDocument.deleted_at.is_(None),
                )
                .order_by(ContractDocument.priority.asc(), ContractDocument.id.asc())
            )
        )
        .scalars()
        .all()
    )
    return [ContractDocumentOut.model_validate(r) for r in rows]


@documents_router.post(
    "",
    response_model=ContractDocumentOut,
    status_code=status.HTTP_201_CREATED,
    summary="契約パッケージ文書追加",
)
async def create_document(
    contract_id: int,
    payload: ContractDocumentCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(_WRITE_ROLE),
) -> ContractDocumentOut:
    await _get_contract(session, contract_id)
    doc = ContractDocument(
        contract_id=contract_id,
        doc_type=payload.doc_type,
        title=payload.title,
        priority=payload.priority,
        doc_date=payload.doc_date,
        amount_jpy=payload.amount_jpy,
        start_date=payload.start_date,
        end_date=payload.end_date,
        content=payload.content,
        source_attachment_id=payload.source_attachment_id,
        created_by=current_user.db_id,
        updated_by=current_user.db_id,
    )
    session.add(doc)
    await session.flush()
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="document.create",
        target_type="contract_documents",
        target_id=doc.id,
        payload={"after": payload.model_dump()},
        request=request,
    )
    return ContractDocumentOut.model_validate(doc)


@documents_router.patch(
    "/{document_id}",
    response_model=ContractDocumentOut,
    summary="契約パッケージ文書更新",
)
async def update_document(
    contract_id: int,
    document_id: int,
    payload: ContractDocumentUpdate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(_WRITE_ROLE),
) -> ContractDocumentOut:
    await _get_contract(session, contract_id)
    doc = await session.get(ContractDocument, document_id)
    if doc is None or doc.contract_id != contract_id or doc.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found")
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(doc, key, value)
    doc.updated_by = current_user.db_id
    await session.flush()
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="document.update",
        target_type="contract_documents",
        target_id=doc.id,
        payload={"after": payload.model_dump(exclude_unset=True)},
        request=request,
    )
    return ContractDocumentOut.model_validate(doc)


@documents_router.get(
    "/consistency",
    response_model=DocumentConsistencyOut,
    summary="契約パッケージ文書間の矛盾検出",
)
async def check_document_consistency(
    contract_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> DocumentConsistencyOut:
    contract = await _get_contract(session, contract_id)
    rows = (
        (
            await session.execute(
                select(ContractDocument)
                .where(
                    ContractDocument.contract_id == contract_id,
                    ContractDocument.deleted_at.is_(None),
                )
                .order_by(ContractDocument.priority.asc(), ContractDocument.id.asc())
            )
        )
        .scalars()
        .all()
    )
    snapshots = [
        DocumentSnapshot(
            id=doc.id,
            doc_type=doc.doc_type,
            title=doc.title,
            priority=doc.priority,
            amount_jpy=doc.amount_jpy,
            start_date=doc.start_date,
            end_date=doc.end_date,
            content=doc.content,
        )
        for doc in rows
    ]
    if not snapshots and contract.amount is not None:
        snapshots.append(
            DocumentSnapshot(
                id=None,
                doc_type="contract",
                title="契約台帳",
                priority=1,
                amount_jpy=int(contract.amount),
            )
        )
    findings = check_consistency(snapshots)
    return DocumentConsistencyOut(
        contract_id=contract_id,
        overall_status=(
            "fail"
            if any(f.severity == "block" for f in findings)
            else "warning"
            if any(f.severity == "warn" for f in findings)
            else "pass"
        ),
        findings=consistency_to_dict(findings),
    )


# ---------------------------------------------------------------------------
# 支払・出来高・検収コンプライアンス
# ---------------------------------------------------------------------------

payment_router = APIRouter(prefix="/contracts/{contract_id}/payment-compliance", tags=["payment"])


@payment_router.get(
    "",
    response_model=PaymentComplianceOut,
    summary="支払・出来高・検収コンプライアンス判定",
)
async def payment_compliance(
    contract_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> PaymentComplianceOut:
    contract = await _get_contract(session, contract_id)
    meta = contract.extra_metadata or {}
    body = str(meta.get("body") or meta.get("text") or meta.get("description") or "")
    result = assess_payment(
        contract_id=contract_id,
        order_date=contract.order_date,
        receipt_date=contract.receipt_date,
        inspection_date=contract.inspection_date,
        payment_date=contract.payment_date,
        amount_jpy=contract.amount,
        transaction_kind=contract.transaction_kind,
        is_public_work=bool(contract.is_public_work),
        text=body,
        counterparty_capital_jpy=contract.counterparty_capital_jpy,
        counterparty_employees=contract.counterparty_employees,
        our_capital_jpy=contract.our_capital_jpy,
        our_employees=contract.our_employees,
    )
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="payment_compliance.run",
        target_type="contracts",
        target_id=contract_id,
        payload={"overall_status": result.to_dict()["overall_status"]},
        request=request,
    )
    return PaymentComplianceOut(**result.to_dict())


# ---------------------------------------------------------------------------
# 協力会社台帳
# ---------------------------------------------------------------------------

partners_router = APIRouter(prefix="/partners", tags=["partners"])


@partners_router.get(
    "",
    response_model=Page[PartnerOut],
    summary="協力会社一覧",
)
async def list_partners(
    q: str | None = Query(default=None),
    partner_type: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Page[PartnerOut]:
    items, total = await partner_service.list_partners(
        session,
        q=q,
        partner_type=partner_type,
        risk_level=risk_level,
        page=page,
        size=size,
    )
    out: list[PartnerOut] = []
    for partner in items:
        _, reasons = partner_service.assess_risk(partner)
        out.append(PartnerOut.model_validate(partner).model_copy(update={"risk_reasons": reasons}))
    return Page[PartnerOut](items=out, total=total, page=page, size=size)


@partners_router.get(
    "/summary",
    response_model=PartnerSummaryOut,
    summary="協力会社リスク集計",
)
async def partners_summary(
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> PartnerSummaryOut:
    return PartnerSummaryOut(**await partner_service.summary(session))


@partners_router.post(
    "",
    response_model=PartnerOut,
    status_code=status.HTTP_201_CREATED,
    summary="協力会社登録",
)
async def create_partner(
    payload: PartnerCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _role: None = Depends(_WRITE_ROLE),
) -> PartnerOut:
    partner = await partner_service.create_partner(
        session,
        actor=current_user,
        data=payload.model_dump(),
    )
    _, reasons = partner_service.assess_risk(partner)
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="partner.create",
        target_type="partners",
        target_id=partner.id,
        payload={"after": payload.model_dump()},
        request=request,
    )
    return PartnerOut.model_validate(partner).model_copy(update={"risk_reasons": reasons})


@partners_router.patch(
    "/{partner_id}",
    response_model=PartnerOut,
    summary="協力会社更新",
)
async def update_partner(
    partner_id: int,
    payload: PartnerUpdate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _role: None = Depends(_WRITE_ROLE),
) -> PartnerOut:
    try:
        partner = await partner_service.update_partner(
            session,
            partner_id=partner_id,
            actor=current_user,
            data=payload.model_dump(exclude_none=True),
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="partner not found")
    _, reasons = partner_service.assess_risk(partner)
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="partner.update",
        target_type="partners",
        target_id=partner.id,
        payload={"after": payload.model_dump(exclude_unset=True)},
        request=request,
    )
    return PartnerOut.model_validate(partner).model_copy(update={"risk_reasons": reasons})


# ---------------------------------------------------------------------------
# 紛争・事故・債権管理
# ---------------------------------------------------------------------------

disputes_router = APIRouter(prefix="/disputes", tags=["disputes"])


@disputes_router.get(
    "",
    response_model=Page[DisputeOut],
    summary="紛争・クレーム一覧",
)
async def list_disputes(
    q: str | None = Query(default=None),
    status_: str | None = Query(default=None, alias="status"),
    dispute_type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Page[DisputeOut]:
    items, total = await dispute_service.list_disputes(
        session,
        viewer=current_user,
        q=q,
        status=status_,
        dispute_type=dispute_type,
        page=page,
        size=size,
    )
    return Page[DisputeOut](
        items=[DisputeOut.model_validate(i) for i in items],
        total=total,
        page=page,
        size=size,
    )


@disputes_router.get(
    "/exposure",
    response_model=DisputeExposureOut,
    summary="紛争エクスポージャー集計",
)
async def disputes_exposure(
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> DisputeExposureOut:
    return DisputeExposureOut(**await dispute_service.exposure_summary(session))


@disputes_router.post(
    "",
    response_model=DisputeOut,
    status_code=status.HTTP_201_CREATED,
    summary="紛争案件登録",
)
async def create_dispute(
    payload: DisputeCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(_WRITE_ROLE),
) -> DisputeOut:
    dispute = await dispute_service.create_dispute(
        session,
        actor=current_user,
        data=payload.model_dump(),
    )
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="dispute.create",
        target_type="disputes",
        target_id=dispute.id,
        payload={"after": payload.model_dump()},
        request=request,
    )
    return DisputeOut.model_validate(dispute)


@disputes_router.patch(
    "/{dispute_id}",
    response_model=DisputeOut,
    summary="紛争案件更新",
)
async def update_dispute(
    dispute_id: int,
    payload: DisputeUpdate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(_WRITE_ROLE),
) -> DisputeOut:
    try:
        dispute = await dispute_service.update_dispute(
            session,
            dispute_id=dispute_id,
            actor=current_user,
            data=payload.model_dump(exclude_none=True),
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="dispute not found")
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="dispute.update",
        target_type="disputes",
        target_id=dispute.id,
        payload={"after": payload.model_dump(exclude_unset=True)},
        request=request,
    )
    return DisputeOut.model_validate(dispute)


@disputes_router.post(
    "/{dispute_id}/timeline",
    response_model=DisputeTimelineEventOut,
    status_code=status.HTTP_201_CREATED,
    summary="紛争タイムライン追加",
)
async def add_timeline_event(
    dispute_id: int,
    payload: DisputeTimelineEventCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(_WRITE_ROLE),
) -> DisputeTimelineEventOut:
    try:
        event = await dispute_service.add_timeline_event(
            session,
            dispute_id=dispute_id,
            actor=current_user,
            data=payload.model_dump(exclude_none=True),
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="dispute not found")
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="dispute.timeline.add",
        target_type="dispute_timeline_events",
        target_id=event.id,
        payload={"after": payload.model_dump()},
        request=request,
    )
    return DisputeTimelineEventOut.model_validate(event)


@disputes_router.post(
    "/{dispute_id}/evidence",
    response_model=DisputeEvidenceOut,
    status_code=status.HTTP_201_CREATED,
    summary="紛争証拠の登録・保全",
)
async def add_dispute_evidence(
    dispute_id: int,
    payload: DisputeEvidenceCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(_WRITE_ROLE),
) -> DisputeEvidenceOut:
    try:
        evidence = await dispute_service.add_evidence(
            session,
            dispute_id=dispute_id,
            actor=current_user,
            data=payload.model_dump(),
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="dispute not found")
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="dispute.evidence.add",
        target_type="dispute_evidence",
        target_id=evidence.id,
        payload={"after": payload.model_dump()},
        request=request,
    )
    return DisputeEvidenceOut.model_validate(evidence)
