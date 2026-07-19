"""Integration tests for the DB-backed notification center API."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select

from app.models.enums import NotificationChannel, NotificationStatus
from app.models.notification import Notification
from app.models.user import User

CONTRACTS = "/api/v1/contracts"
NOTIFICATIONS = "/api/v1/notifications"


def _headers(role: str, subject: str) -> dict[str, str]:
    from app.core.security import create_access_token

    token = create_access_token(subject=subject, extra_claims={"role": role})
    return {"Authorization": f"Bearer {token}"}


def _session_for(engine: Any) -> Any:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    return async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)()


async def _user_by_email(engine: Any, email: str) -> User:
    session = _session_for(engine)
    try:
        return (await session.execute(select(User).where(User.email == email))).scalar_one()
    finally:
        await session.close()


async def _insert_notification(
    engine: Any,
    *,
    recipient_id: int,
    subject: str,
    channel: str = NotificationChannel.IN_APP.value,
) -> int:
    session = _session_for(engine)
    try:
        notification = Notification(
            recipient_id=recipient_id,
            channel=channel,
            category="workflow",
            subject=subject,
            body="Please review",
            status=NotificationStatus.SENT.value,
        )
        session.add(notification)
        await session.commit()
        return notification.id
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_notification_list_read_and_read_all_flow(client: Any, test_engine: Any) -> None:
    """A caller can list and mark only their own notifications as read."""
    email = "notify-flow@example.com"
    headers = _headers("reviewer", email)

    provision = await client.get(CONTRACTS, headers=headers)
    assert provision.status_code == 200
    user = await _user_by_email(test_engine, email)

    first_id = await _insert_notification(test_engine, recipient_id=user.id, subject="First")
    await _insert_notification(
        test_engine,
        recipient_id=user.id,
        subject="Mail item",
        channel=NotificationChannel.MAIL.value,
    )

    listed = await client.get(NOTIFICATIONS, headers=headers)
    assert listed.status_code == 200, listed.text
    payload = listed.json()
    assert payload["total"] == 2
    assert {item["title"] for item in payload["items"]} == {"First", "Mail item"}
    assert all(item["status"] == "unread" for item in payload["items"])

    mail_only = await client.get(f"{NOTIFICATIONS}?channel=email", headers=headers)
    assert mail_only.status_code == 200
    assert mail_only.json()["total"] == 1
    assert mail_only.json()["items"][0]["channel"] == NotificationChannel.MAIL.value

    read = await client.patch(f"{NOTIFICATIONS}/{first_id}/read", headers=headers)
    assert read.status_code == 200, read.text
    assert read.json()["status"] == "read"
    assert read.json()["read_at"] is not None

    unread = await client.get(f"{NOTIFICATIONS}?status=unread", headers=headers)
    assert unread.status_code == 200
    assert unread.json()["total"] == 1

    read_all = await client.post(f"{NOTIFICATIONS}/read-all", headers=headers)
    assert read_all.status_code == 200, read_all.text
    assert read_all.json()["updated"] == 1

    read_items = await client.get(f"{NOTIFICATIONS}?status=read", headers=headers)
    assert read_items.status_code == 200
    assert read_items.json()["total"] == 2


@pytest.mark.asyncio
async def test_notification_read_is_owner_scoped(client: Any, test_engine: Any) -> None:
    """A notification row cannot be marked read by a different authenticated user."""
    owner_email = "notify-owner@example.com"
    owner_headers = _headers("reviewer", owner_email)
    assert (await client.get(CONTRACTS, headers=owner_headers)).status_code == 200
    owner = await _user_by_email(test_engine, owner_email)
    notification_id = await _insert_notification(
        test_engine,
        recipient_id=owner.id,
        subject="Private notification",
    )

    other_headers = _headers("reviewer", "notify-other@example.com")
    assert (await client.get(CONTRACTS, headers=other_headers)).status_code == 200

    response = await client.patch(f"{NOTIFICATIONS}/{notification_id}/read", headers=other_headers)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_notification_filters_reject_unknown_values(client: Any) -> None:
    """Unknown status/channel filters fail closed with 400."""
    headers = _headers("reviewer", "notify-filter@example.com")
    assert (await client.get(CONTRACTS, headers=headers)).status_code == 200

    bad_status = await client.get(f"{NOTIFICATIONS}?status=archived", headers=headers)
    bad_channel = await client.get(f"{NOTIFICATIONS}?channel=sms", headers=headers)

    assert bad_status.status_code == 400
    assert bad_channel.status_code == 400
