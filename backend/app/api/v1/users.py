"""ユーザー管理エンドポイント。

- GET `/users` : 一覧 (admin/auditor)
- GET `/users/{id}` : 詳細 (admin/auditor/本人)
- POST `/users` : 新規作成 (admin)
- PATCH `/users/{id}` : 更新 (admin)
- POST `/users/sync` : Microsoft Graph 同期 (admin)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import CurrentUser, get_current_user, require_role
from app.schemas.common import Page
from app.schemas.user import (
    UserCreate,
    UserIdentityLink,
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
    current_user: CurrentUser = Depends(get_current_user),
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
    current_user: CurrentUser = Depends(get_current_user),
) -> UserOut:
    # Compare the resolved DB id — the raw token subject is a UUID/str and
    # would never equal an int path param (Issue #45: self-access was 403).
    if current_user.role not in ("admin", "auditor") and current_user.db_id != user_id:
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
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_role("admin")),
) -> UserOut:
    user = await user_service.create_user(session, data=payload)
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
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
    current_user: CurrentUser = Depends(get_current_user),
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
        actor_id=current_user.db_id,
        action="user.update",
        target_type="users",
        target_id=user.id,
        payload={"after": payload.model_dump(exclude_unset=True)},
        request=request,
    )
    return UserOut.model_validate(user)


@router.post(
    "/{user_id}/identity-link",
    response_model=UserOut,
    summary="Entra ID oid の明示リンク",
    description=(
        "oid 無しトークンで JIT 作成されたユーザーを、後日取得した実 Entra oid に"
        " admin が明示的に紐付ける。自動マージは行わず、現在 oid の一致確認と監査ログを必須にする。"
    ),
)
async def link_user_identity(
    user_id: int,
    payload: UserIdentityLink,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_role("admin")),
) -> UserOut:
    try:
        user = await user_service.link_entra_identity(
            session,
            user_id=user_id,
            expected_current_entra_oid=payload.expected_current_entra_oid,
            new_entra_oid=payload.new_entra_oid,
            reason=payload.reason,
            actor_id=current_user.db_id or 0,
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="user.identity_link",
        target_type="users",
        target_id=user.id,
        payload={
            "expected_current_entra_oid": str(payload.expected_current_entra_oid),
            "new_entra_oid": str(payload.new_entra_oid),
            "reason": payload.reason,
        },
        request=request,
    )
    return UserOut.model_validate(user)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="ユーザー削除 (admin only)",
    description="ユーザーを無効化し、deleted_at を設定する論理削除。admin ロールのみ実行可能。",
)
async def delete_user(
    user_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _admin: None = Depends(require_role("admin")),
) -> None:
    try:
        await user_service.soft_delete_user(
            session,
            user_id=user_id,
            actor_id=current_user.db_id,
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="user.delete",
        target_type="users",
        target_id=user_id,
        payload={"soft_delete": True},
        request=request,
    )


@router.post(
    "/sync",
    response_model=UserSyncJob,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Microsoft Graph ユーザー同期",
    description=(
        "Microsoft Graph ユーザー同期ジョブを受付し、ジョブ ID を返却する。"
        "本番 Graph credentials / worker 承認前は外部通信せず queued として監査する。"
    ),
)
async def sync_users(
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_role("admin")),
) -> UserSyncJob:
    job = await user_service.start_graph_sync(session, triggered_by=current_user.db_id)
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="user.sync",
        target_type="users",
        target_id=None,
        payload={
            "job_id": job.job_id,
            "status": job.status,
            "external_write": False,
        },
        request=request,
    )
    return job
