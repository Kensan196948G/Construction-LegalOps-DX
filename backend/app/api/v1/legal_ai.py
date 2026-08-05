"""適用法令自動判定 / 一次情報 RAG / 法令改正影響分析 API."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import CurrentUser, get_current_user
from app.models.contract import Contract
from app.schemas.business import (
    ApplicableLawResultOut,
    EvidenceLookupOut,
    LawChangeImpactOut,
)
from app.services import audit_service
from app.services.applicable_law import determine as determine_laws
from app.services.evidence_lookup import search_primary_sources, verify_citations
from app.services.law_change_impact import analyze as analyze_law_change

router = APIRouter(tags=["legal-ai"])


applicable_laws_router = APIRouter(prefix="/compliance/applicable-laws", tags=["applicable-laws"])


@applicable_laws_router.get(
    "",
    response_model=ApplicableLawResultOut,
    summary="契約への適用法令自動判定",
)
async def applicable_laws(
    contract_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ApplicableLawResultOut:
    contract = await session.get(Contract, contract_id)
    if contract is None or contract.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="contract not found")
    result = determine_laws(
        contract_id=contract_id,
        contract_type=contract.contract_type,
        order_date=contract.order_date,
        transaction_kind=contract.transaction_kind,
        is_public_work=bool(contract.is_public_work),
        handles_personal_data=bool(contract.handles_personal_data),
        our_capital_jpy=contract.our_capital_jpy,
        our_employees=contract.our_employees,
        counterparty_capital_jpy=contract.counterparty_capital_jpy,
        counterparty_employees=contract.counterparty_employees,
        amount_jpy=(int(contract.amount) if contract.amount is not None else None),
    )
    return ApplicableLawResultOut(**result.to_dict())


evidence_router = APIRouter(prefix="/ai/evidence", tags=["evidence"])


@evidence_router.get(
    "",
    response_model=EvidenceLookupOut,
    summary="一次情報限定の根拠検索（RAG）",
)
async def evidence_lookup(
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(default=8, ge=1, le=20),
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> EvidenceLookupOut:
    hits = await search_primary_sources(session, query=q, limit=limit)
    verification = await verify_citations(
        session,
        urls=[h.source_url for h in hits],
    )
    return EvidenceLookupOut(
        query=q,
        hits=[h.to_dict() for h in hits],
        citation_verification=verification,
    )


@evidence_router.post(
    "/verify",
    response_model=dict[str, object],
    summary="引用 URL の一次情報検証",
)
async def verify_citation_urls(
    payload: dict[str, object],
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, object]:
    urls = payload.get("urls", [])
    if not isinstance(urls, list):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="urls must be a list",
        )
    return await verify_citations(session, urls=[str(u) for u in urls if u])


impact_router = APIRouter(prefix="/compliance/law-change-impact", tags=["law-change-impact"])


@impact_router.get(
    "",
    response_model=LawChangeImpactOut,
    summary="法令改正影響分析",
)
async def law_change_impact(
    request: Request,
    effective_date: date | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> LawChangeImpactOut:
    result = await analyze_law_change(
        session,
        effective_date=effective_date,
    )
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="compliance.run",
        target_type="contracts",
        target_id=None,
        payload={"after": {"impacted_count": result["impacted_count"]}},
        request=request,
    )
    return LawChangeImpactOut(**result)
