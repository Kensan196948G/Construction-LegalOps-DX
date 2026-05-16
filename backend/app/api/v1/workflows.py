"""承認ワークフローエンドポイント。

- POST `/contracts/{id}/workflows` : ワークフロー開始
- GET `/workflows/{id}` : ワークフローインスタンス詳細
- POST `/workflows/{id}/actions` : approve / reject / return / delegate
- GET `/workflows/{id}/steps` : ステップ一覧
- GET `/workflows` : 定義一覧 (admin)
- POST `/workflows` : 定義作成 (admin)
"""

from __future__ import annotations

from typing import Optional, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import Page
from app.schemas.workflow import (
    WorkflowActionRequest,
    WorkflowDefinitionCreate,
    WorkflowDefinitionOut,
    WorkflowInstanceOut,
    WorkflowStartRequest,
    WorkflowStepOut,
)
from app.services import audit_service, workflow_service

router = APIRouter(tags=["workflows"])


@router.get(
    "/workflows",
    response_model=Page[WorkflowDefinitionOut],
    summary="ワークフロー定義一覧",
)
async def list_workflow_definitions(
    contract_type: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Page[WorkflowDefinitionOut]:
    items, total = await workflow_service.list_definitions(
        session, contract_type=contract_type, page=page, size=size
    )
    return Page[WorkflowDefinitionOut](items=items, total=total, page=page, size=size)


@router.post(
    "/workflows",
    response_model=WorkflowDefinitionOut,
    status_code=status.HTTP_201_CREATED,
    summary="ワークフロー定義作成",
)
async def create_workflow_definition(
    payload: WorkflowDefinitionCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_role("admin")),
) -> WorkflowDefinitionOut:
    definition = await workflow_service.create_definition(session, data=payload)
    await audit_service.log(
        session,
        actor_id=current_user.id,
        action="workflow.definition.create",
        target_type="workflow_definitions",
        target_id=definition.id,
        request=request,
    )
    return WorkflowDefinitionOut.model_validate(definition)


@router.post(
    "/contracts/{contract_id}/workflows",
    response_model=WorkflowInstanceOut,
    status_code=status.HTTP_201_CREATED,
    summary="ワークフローインスタンス開始",
    description="契約に対し指定の定義でワークフローインスタンスを生成し、ステップ 1 を活性化する。",
)
async def start_workflow(
    contract_id: int,
    payload: WorkflowStartRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_role("site", "legal", "admin")),
) -> WorkflowInstanceOut:
    try:
        instance = await workflow_service.start_workflow(
            session,
            contract_id=contract_id,
            definition_code=payload.definition_code,
            actor=current_user,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    await audit_service.log(
        session,
        actor_id=current_user.id,
        action="workflow.start",
        target_type="workflow_instances",
        target_id=instance.id,
        payload={"contract_id": contract_id, "definition": payload.definition_code},
        request=request,
    )
    return WorkflowInstanceOut.model_validate(instance)


@router.get(
    "/workflows/{instance_id}",
    response_model=WorkflowInstanceOut,
    summary="ワークフローインスタンス詳細",
)
async def get_workflow_instance(
    instance_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkflowInstanceOut:
    instance = await workflow_service.get_instance(
        session, instance_id=instance_id, viewer=current_user
    )
    if instance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="workflow not found")
    return WorkflowInstanceOut.model_validate(instance)


@router.get(
    "/workflows/{instance_id}/steps",
    response_model=list[WorkflowStepOut],
    summary="ワークフローステップ一覧",
)
async def list_workflow_steps(
    instance_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[WorkflowStepOut]:
    return cast(list[WorkflowStepOut], await workflow_service.list_steps(
        session, instance_id=instance_id, viewer=current_user
    ))


@router.post(
    "/workflows/{instance_id}/actions",
    response_model=WorkflowInstanceOut,
    summary="ワークフローアクション実行",
    description=(
        "approve / reject / return / delegate を指定し、現在の active step を遷移させる。"
        " 承認・差戻はロール権限と assignee 権限の双方を検証。"
    ),
)
async def execute_workflow_action(
    instance_id: int,
    payload: WorkflowActionRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkflowInstanceOut:
    if payload.action not in ("approve", "reject", "return", "delegate"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="action must be one of approve/reject/return/delegate",
        )
    try:
        instance = await workflow_service.execute_action(
            session,
            instance_id=instance_id,
            actor=current_user,
            payload=payload,
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="workflow not found")
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    await audit_service.log(
        session,
        actor_id=current_user.id,
        action=f"workflow.{payload.action}",
        target_type="workflow_instances",
        target_id=instance.id,
        payload=payload.model_dump(),
        request=request,
    )
    return WorkflowInstanceOut.model_validate(instance)
