"""コンプライアンスチェックエンドポイント。

- GET `/compliance/checks/{contract_id}` : 建設業法・下請法等の機械的チェック結果
- GET `/compliance/checklists` : 適用可能なチェックリスト一覧
- POST `/compliance/checks/{contract_id}/run` : チェックリスト適用 (即時実行 + job-shaped response)
"""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import CurrentUser, get_current_user, require_role
from app.schemas.compliance import (
    ComplianceChecklist,
    ComplianceCheckResult,
    ComplianceRunResponse,
)
from app.services import audit_service, compliance_service

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.get(
    "/checklists",
    response_model=list[ComplianceChecklist],
    summary="チェックリスト一覧",
    description="契約類型・取引区分に応じた適用可能なチェックリスト定義を返す。",
)
async def list_checklists(
    contract_type: str | None = Query(default=None),
    category: str | None = Query(
        default=None, description="construction_law / subcontract_act / others"
    ),
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[ComplianceChecklist]:
    return cast(
        list[ComplianceChecklist],
        await compliance_service.list_checklists(
            session, contract_type=contract_type, category=category
        ),
    )


@router.get(
    "/checks/{contract_id}",
    response_model=ComplianceCheckResult,
    summary="契約のコンプライアンスチェック結果",
    description=(
        "建設業法 (請負代金・下請選定・許可業種等)・下請法 (60 日支払・書面交付等)"
        " の機械チェック結果を返す。複数チェックを横断統合した最終ビュー。"
    ),
)
async def get_compliance_result(
    contract_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ComplianceCheckResult:
    result = await compliance_service.get_result(
        session, contract_id=contract_id, viewer=current_user
    )
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    return cast(ComplianceCheckResult, result)


@router.post(
    "/checks/{contract_id}/run",
    response_model=ComplianceRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="チェックリスト適用 (即時実行)",
)
async def run_compliance_check(
    contract_id: int,
    request: Request,
    checklist_codes: list[str] | None = Query(default=None, description="未指定時は全件"),
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_role("legal", "admin")),
) -> ComplianceRunResponse:
    try:
        run = await compliance_service.start_run(
            session,
            contract_id=contract_id,
            checklist_codes=checklist_codes,
            actor=current_user,
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="contract not found")

    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="compliance.run",
        target_type="contracts",
        target_id=contract_id,
        payload={"checklist_codes": checklist_codes},
        request=request,
    )
    return cast(ComplianceRunResponse, run)
