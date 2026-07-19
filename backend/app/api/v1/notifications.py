"""通知エンドポイント。

- GET `/notifications` : 自身宛て通知一覧 (status/channel)
- PATCH `/notifications/{id}/read` : 既読化
- POST `/notifications/read-all` : 全件既読
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import CurrentUser, get_current_user
from app.schemas.common import Page
from app.schemas.notification import NotificationOut, NotificationReadResult
from app.services import audit_service, notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get(
    "",
    response_model=Page[NotificationOut],
    summary="通知一覧 (本人のみ)",
)
async def list_notifications(
    status_: str | None = Query(default=None, alias="status", description="unread/read"),
    channel: str | None = Query(default=None, description="inapp/email/teams"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Page[NotificationOut]:
    try:
        items, total = await notification_service.list_for_user(
            session,
            user_id=current_user.db_id,
            status=status_,
            channel=channel,
            page=page,
            size=size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return Page[NotificationOut](items=items, total=total, page=page, size=size)


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationOut,
    summary="通知既読化",
)
async def mark_read(
    notification_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> NotificationOut:
    try:
        notification = await notification_service.mark_read(
            session, notification_id=notification_id, user_id=current_user.db_id
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="notification not found")
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="notification.read",
        target_type="notifications",
        target_id=notification.id,
        request=request,
    )
    return notification


@router.post(
    "/read-all",
    response_model=NotificationReadResult,
    summary="全通知既読化",
)
async def mark_all_read(
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> NotificationReadResult:
    updated = await notification_service.mark_all_read(session, user_id=current_user.db_id)
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="notification.read_all",
        target_type="notifications",
        target_id=None,
        payload={"updated": updated},
        request=request,
    )
    return NotificationReadResult(updated=updated)
