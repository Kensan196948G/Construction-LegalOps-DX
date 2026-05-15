"""ひな形・条項ライブラリエンドポイント。

- GET `/templates` : 契約類型ごとのひな形一覧
- GET `/templates/{id}` : ひな形詳細
- POST `/templates` : ひな形作成 (admin/legal)
- GET `/clauses-library` : 条項ライブラリ検索 (category / recommendation / tag / q)
- POST `/clauses-library` : 条項追加 (admin/legal)
- PATCH `/clauses-library/{id}` : 条項更新
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import Page
from app.schemas.template import (
    ClauseLibraryCreate,
    ClauseLibraryOut,
    ClauseLibraryUpdate,
    TemplateCreate,
    TemplateOut,
)
from app.services import audit_service, template_service

router = APIRouter(tags=["templates"])


@router.get(
    "/templates",
    response_model=Page[TemplateOut],
    summary="ひな形一覧",
)
async def list_templates(
    contract_type: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Page[TemplateOut]:
    items, total = await template_service.list_templates(
        session, contract_type=contract_type, q=q, page=page, size=size
    )
    return Page[TemplateOut](items=items, total=total, page=page, size=size)


@router.get(
    "/templates/{template_id}",
    response_model=TemplateOut,
    summary="ひな形詳細",
)
async def get_template(
    template_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TemplateOut:
    template = await template_service.get_template(session, template_id=template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="template not found")
    return TemplateOut.model_validate(template)


@router.post(
    "/templates",
    response_model=TemplateOut,
    status_code=status.HTTP_201_CREATED,
    summary="ひな形作成",
)
async def create_template(
    payload: TemplateCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_role("legal", "admin")),
) -> TemplateOut:
    template = await template_service.create_template(session, data=payload, creator=current_user)
    await audit_service.log(
        session,
        actor_id=current_user.id,
        action="template.create",
        target_type="templates",
        target_id=template.id,
        request=request,
    )
    return TemplateOut.model_validate(template)


@router.get(
    "/clauses-library",
    response_model=Page[ClauseLibraryOut],
    summary="条項ライブラリ検索",
    description="カテゴリ・推奨度 (must/should/avoid)・タグ・全文検索で条項を取得。",
)
async def list_clauses_library(
    category: Optional[str] = Query(default=None),
    recommendation: Optional[str] = Query(default=None, description="must/should/avoid"),
    tag: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Page[ClauseLibraryOut]:
    items, total = await template_service.list_clauses(
        session,
        category=category,
        recommendation=recommendation,
        tag=tag,
        q=q,
        page=page,
        size=size,
    )
    return Page[ClauseLibraryOut](items=items, total=total, page=page, size=size)


@router.post(
    "/clauses-library",
    response_model=ClauseLibraryOut,
    status_code=status.HTTP_201_CREATED,
    summary="条項ライブラリへの追加",
)
async def create_clause(
    payload: ClauseLibraryCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_role("legal", "admin")),
) -> ClauseLibraryOut:
    clause = await template_service.create_clause(session, data=payload, creator=current_user)
    await audit_service.log(
        session,
        actor_id=current_user.id,
        action="clause_library.create",
        target_type="clause_library",
        target_id=clause.id,
        request=request,
    )
    return ClauseLibraryOut.model_validate(clause)


@router.patch(
    "/clauses-library/{clause_id}",
    response_model=ClauseLibraryOut,
    summary="条項ライブラリ更新",
)
async def update_clause(
    clause_id: int,
    payload: ClauseLibraryUpdate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_role("legal", "admin")),
) -> ClauseLibraryOut:
    try:
        clause = await template_service.update_clause(
            session, clause_id=clause_id, data=payload, editor=current_user
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="clause not found")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    await audit_service.log(
        session,
        actor_id=current_user.id,
        action="clause_library.update",
        target_type="clause_library",
        target_id=clause.id,
        request=request,
    )
    return ClauseLibraryOut.model_validate(clause)
