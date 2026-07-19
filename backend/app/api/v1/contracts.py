"""契約管理エンドポイント。

- CRUD `/contracts`
- ページング・絞り込み (status, contract_type, department_id, risk_level, q)
- バージョン履歴 `/contracts/{id}/versions`
- 論理削除 DELETE
- 状態遷移 `POST /contracts/{id}/submit`
- 条項取得 `/contracts/{id}/clauses`
- 監査証跡 `/contracts/{id}/audit-trail`
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import CurrentUser, get_current_user, require_role
from app.schemas.audit_log import AuditLogOut
from app.schemas.clause import ClauseOut
from app.schemas.common import Page
from app.schemas.contract import (
    ContractCreate,
    ContractOut,
    ContractUpdate,
    ContractVersionOut,
)
from app.services import audit_service, contract_service

router = APIRouter(prefix="/contracts", tags=["contracts"])


@router.get(
    "",
    response_model=Page[ContractOut],
    summary="契約一覧",
    description=(
        "検索・絞り込み (status/contract_type/department_id/risk_level/q)"
        "・ページング対応。RLS 適用。"
    ),
)
async def list_contracts(
    q: str | None = Query(default=None, description="タイトル/相手方/契約番号の部分一致"),
    status_: str | None = Query(default=None, alias="status"),
    contract_type: str | None = Query(default=None),
    department_id: int | None = Query(default=None),
    risk_level: str | None = Query(default=None, description="low/medium/high/critical"),
    confidentiality: str | None = Query(default=None),
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    sort: str | None = Query(default="-updated_at"),
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Page[ContractOut]:
    items, total = await contract_service.list_contracts(
        session,
        viewer=current_user,
        q=q,
        status=status_,
        contract_type=contract_type,
        department_id=department_id,
        risk_level=risk_level,
        confidentiality=confidentiality,
        date_from=date_from,
        date_to=date_to,
        page=page,
        size=size,
        sort=sort,
    )
    return Page[ContractOut](items=items, total=total, page=page, size=size)


@router.post(
    "",
    response_model=ContractOut,
    status_code=status.HTTP_201_CREATED,
    summary="契約新規作成",
)
async def create_contract(
    payload: ContractCreate,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_role("drafter", "reviewer", "admin")),
) -> ContractOut:
    contract = await contract_service.create_contract(
        session,
        creator=current_user,
        data=payload,
        idempotency_key=idempotency_key,
    )
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="contract.create",
        target_type="contracts",
        target_id=contract.id,
        payload={"after": payload.model_dump()},
        request=request,
    )
    return ContractOut.model_validate(contract)


@router.get(
    "/{contract_id}",
    response_model=ContractOut,
    summary="契約詳細取得",
)
async def get_contract(
    contract_id: int,
    include_deleted: bool = Query(
        default=False, description="論理削除済み契約を含める (admin/auditor)"
    ),
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ContractOut:
    contract = await contract_service.get_contract(
        session, contract_id=contract_id, viewer=current_user, include_deleted=include_deleted
    )
    if contract is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="contract not found")
    return ContractOut.model_validate(contract)


@router.patch(
    "/{contract_id}",
    response_model=ContractOut,
    summary="契約更新",
    description="差分項目のみ。version 必須 (楽観ロック)。",
)
async def update_contract(
    contract_id: int,
    payload: ContractUpdate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ContractOut:
    try:
        contract = await contract_service.update_contract(
            session,
            contract_id=contract_id,
            data=payload,
            editor=current_user,
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="contract not found")
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="contract.update",
        target_type="contracts",
        target_id=contract.id,
        payload={"after": payload.model_dump(exclude_unset=True)},
        request=request,
    )
    return ContractOut.model_validate(contract)


@router.delete(
    "/{contract_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="契約削除 (論理削除)",
)
async def delete_contract(
    contract_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_role("admin")),
) -> None:
    try:
        await contract_service.soft_delete_contract(
            session,
            contract_id=contract_id,
            actor=current_user,
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="contract not found")
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="contract.delete",
        target_type="contracts",
        target_id=contract_id,
        request=request,
    )


@router.post(
    "/{contract_id}/submit",
    response_model=ContractOut,
    summary="契約レビュー提出",
    description=(
        "status を draft → in_review に遷移する。"
        "承認ワークフローは /contracts/{id}/workflows で開始する。"
    ),
)
async def submit_contract(
    contract_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_role("drafter", "reviewer", "admin")),
) -> ContractOut:
    try:
        contract = await contract_service.submit_for_review(
            session,
            contract_id=contract_id,
            actor=current_user,
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="contract not found")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="contract.submit",
        target_type="contracts",
        target_id=contract.id,
        request=request,
    )
    return ContractOut.model_validate(contract)


@router.get(
    "/{contract_id}/versions",
    response_model=Page[ContractVersionOut],
    summary="契約バージョン履歴",
)
async def list_versions(
    contract_id: int,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Page[ContractVersionOut]:
    try:
        items, total = await contract_service.list_versions(
            session,
            contract_id=contract_id,
            viewer=current_user,
            page=page,
            size=size,
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="contract not found")
    return Page[ContractVersionOut](items=items, total=total, page=page, size=size)


@router.get(
    "/{contract_id}/clauses",
    response_model=list[ClauseOut],
    summary="契約条項一覧 (seq 昇順)",
)
async def list_clauses(
    contract_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[ClauseOut]:
    try:
        return await contract_service.list_clauses(
            session,
            contract_id=contract_id,
            viewer=current_user,
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="contract not found")


@router.get(
    "/{contract_id}/audit-trail",
    response_model=Page[AuditLogOut],
    summary="契約監査証跡",
)
async def contract_audit_trail(
    contract_id: int,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_role("admin", "auditor")),
) -> Page[AuditLogOut]:
    items, total = await audit_service.list_for_target(
        session,
        target_type="contracts",
        target_id=contract_id,
        page=page,
        size=size,
    )
    return Page[AuditLogOut](items=items, total=total, page=page, size=size)
