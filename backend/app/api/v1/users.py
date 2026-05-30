"""ユーザー管理エンドポイント。

- GET `/users` : 一覧 (admin/auditor)
- GET `/users/{id}` : 詳細 (admin/auditor/本人)
- POST `/users` : 新規作成 (admin)
- PATCH `/users/{id}` : 更新 (admin)
- POST `/users/sync` : Microsoft Graph 同期 (admin)
"""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import get_current_user, require_role
from app.models.user import User
from app.schemas.common import Page
from app.schemas.user import (
    UserCreate,
    UserOut,
    UserSyncJob,
    UserUpdate,
)
from app.services import audit_service, user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "",
    response_model=Page[UserOut],
    summary="ユーザー一覧",
    description="ロール・部署・有効状態でフィルタしページングしたユーザー一覧を返す。",
)
async def list_users(
    q: str | None = Query(default=None, description="氏名/メール部分一致"),
    role: str | None = Query(default=None, description="ロールでフィルタ"),
    department_id: int | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_role("admin", "auditor")),
) -> Page[UserOut]:
    items, total = await user_service.list_users(
        session,
        q=q,
        role=role,
        department_id=department_id,
        is_active=is_active,
        page=page,
        size=size,
    )
    return Page[UserOut](items=items, total=total, page=page, size=size)


@router.get(
    "/{user_id}",
    response_model=UserOut,
    summary="ユーザー詳細",
    description="admin/auditor は全件、それ以外は本人のみ取得可能。",
)
async def get_user(
    user_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserOut:
    if current_user.role not in ("admin", "auditor") and current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    user = await user_service.get_user(session, user_id=user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    return UserOut.model_validate(user)


@router.post(
    "",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="ユーザー作成",
    description="通常は Microsoft Graph 同期で行うが、緊急時の手動作成を許可。",
)
async def create_user(
    payload: UserCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_role("admin")),
) -> UserOut:
    user = await user_service.create_user(session, data=payload)
    await audit_service.log(
        session,
        actor_id=current_user.id,
        action="user.create",
        target_type="users",
        target_id=user.id,
        payload={"after": payload.model_dump()},
        request=request,
    )
    return UserOut.model_validate(user)


@router.patch(
    "/{user_id}",
    response_model=UserOut,
    summary="ユーザー更新",
    description="ロール・部署・有効状態を更新する。version 不一致時 409。",
)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_role("admin")),
) -> UserOut:
    try:
        user = await user_service.update_user(session, user_id=user_id, data=payload)
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    await audit_service.log(
        session,
        actor_id=current_user.id,
        action="user.update",
        target_type="users",
        target_id=user.id,
        payload={"after": payload.model_dump(exclude_unset=True)},
        request=request,
    )
    return UserOut.model_validate(user)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="ユーザー削除 (admin only / stub)",
    description="論理削除。admin ロールのみ実行可能。実装は Sprint 1 で完成予定。",
)
async def delete_user(
    user_id: int,
    _current: User = Depends(get_current_user),
    _admin: None = Depends(require_role("admin")),
) -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="user deletion not yet implemented",
    )


@router.post(
    "/sync",
    response_model=UserSyncJob,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Microsoft Graph ユーザー同期",
    description="非同期でジョブを起動し、ジョブ ID を返却する。",
)
async def sync_users(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_role("admin")),
) -> UserSyncJob:
    result = await user_service.start_graph_sync(session, triggered_by=current_user.id)
    return cast(UserSyncJob, result)
