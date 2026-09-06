"""Unit tests for notification_service.py.

Covers:
- NotificationService.send_email() — success, empty-recipient error, stub vs queued mode
- NotificationService.send_teams_card() — default kind, explicit kind, metadata
- NotificationService.send_desknets() — stub mode, queued mode
- NotificationService.sent() / clear() — introspection helpers
- Module-level notification center helpers — DB-backed mapping / read state behavior
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.enums import NotificationChannel, NotificationStatus
from app.models.notification import Notification
from app.services.notification_service import (
    NotificationError,
    NotificationRecord,
    NotificationService,
    TeamsCardKind,
    list_for_user,
    mark_all_read,
    mark_read,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stub_service() -> NotificationService:
    """Return a NotificationService in stub mode (default)."""
    return NotificationService(mode="stub")


def _queued_service() -> NotificationService:
    """Return a NotificationService in queued mode."""
    return NotificationService(mode="queued")


class _FakeResponse:
    def __init__(self, payload: dict[str, Any] | None = None) -> None:
        self._payload = payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def read(self) -> bytes:
        if self._payload is None:
            return b""
        return json.dumps(self._payload).encode("utf-8")


@pytest_asyncio.fixture()
async def notification_db_session(db_session: Any) -> AsyncGenerator[Any, None]:
    """Alias for the shared, transaction-isolated ``db_session`` fixture.

    Kept as a separate name since this module's tests historically requested
    ``notification_db_session`` explicitly. Previously this fixture owned a
    dedicated engine and ran ``create_all_for_tests`` (drop/create) against
    it — since that targets the same shared PostgreSQL database as every
    other test, it would wipe tables out from under whichever other test
    happened to be mid-transaction. Using the shared ``db_session`` avoids
    a second schema reset entirely.
    """
    yield db_session


@pytest_asyncio.fixture()
async def notification_actors(notification_db_session: Any) -> dict[str, int]:
    """Seed a department + three users + a contract; return their ids.

    PostgreSQL enforces the FK from ``notifications.recipient_id``/
    ``contract_id`` to ``users``/``contracts``, so tests can no longer
    reference hardcoded ids (1, 2, 99, 7) that may not exist in the shared
    test database.
    """
    from uuid import uuid4

    from app.models.contract import Contract
    from app.models.department import Department
    from app.models.user import User

    dept = Department(code=f"D-{uuid4().hex[:8]}", name="通知テスト部")
    notification_db_session.add(dept)
    await notification_db_session.flush()

    users = {}
    for key in ("user1", "user2", "user99"):
        user = User(
            entra_oid=uuid4(),
            email=f"{uuid4().hex[:10]}@test.example",
            display_name=f"利用者-{key}",
            role="viewer",
            department_id=dept.id,
            is_active=True,
        )
        notification_db_session.add(user)
        await notification_db_session.flush()
        users[key] = user.id

    contract = Contract(
        contract_no=f"C-NOTIFY-{uuid4().hex[:8]}",
        title="通知テスト契約",
        counterparty="株式会社テスト",
        contract_type="請負",
        department_id=dept.id,
        drafter_id=users["user1"],
    )
    notification_db_session.add(contract)
    await notification_db_session.flush()

    return {**users, "contract": contract.id}


# ---------------------------------------------------------------------------
# send_email — basic cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_email_returns_notification_record():
    """send_email() must return a NotificationRecord with correct fields."""
    svc = _stub_service()
    rec = await svc.send_email(
        to=["alice@example.com"],
        subject="Test subject",
        body="Hello",
    )
    assert isinstance(rec, NotificationRecord)
    assert rec.channel == NotificationChannel.MAIL
    assert rec.to == ("alice@example.com",)
    assert rec.subject == "Test subject"
    assert rec.body == "Hello"


@pytest.mark.asyncio
async def test_send_email_stub_mode_sets_status_sent():
    """In stub mode, send_email() must set status=SENT."""
    svc = _stub_service()
    rec = await svc.send_email(to=["a@example.com"], subject="s", body="b")
    assert rec.status == NotificationStatus.SENT


@pytest.mark.asyncio
async def test_send_email_queued_mode_sets_status_queued():
    """In non-stub mode, send_email() must set status=QUEUED."""
    svc = _queued_service()
    rec = await svc.send_email(to=["a@example.com"], subject="s", body="b")
    assert rec.status == NotificationStatus.QUEUED


@pytest.mark.asyncio
async def test_send_email_raises_for_empty_recipients():
    """send_email() must raise NotificationError when 'to' is empty."""
    svc = _stub_service()
    with pytest.raises(NotificationError, match="recipient"):
        await svc.send_email(to=[], subject="s", body="b")


@pytest.mark.asyncio
async def test_send_email_stores_cc_in_metadata():
    """send_email() must persist cc list inside record.metadata."""
    svc = _stub_service()
    rec = await svc.send_email(
        to=["a@example.com"],
        subject="s",
        body="b",
        cc=["cc1@example.com", "cc2@example.com"],
    )
    assert rec.metadata["cc"] == ["cc1@example.com", "cc2@example.com"]


@pytest.mark.asyncio
async def test_send_email_extra_metadata_merged():
    """send_email() must merge extra metadata kwarg into record.metadata."""
    svc = _stub_service()
    rec = await svc.send_email(
        to=["a@example.com"],
        subject="s",
        body="b",
        metadata={"ref_id": 99},
    )
    assert rec.metadata["ref_id"] == 99


@pytest.mark.asyncio
async def test_send_email_appends_to_sent_list():
    """send_email() must append the record to the internal sent list."""
    svc = _stub_service()
    await svc.send_email(to=["a@example.com"], subject="s", body="b")
    await svc.send_email(to=["b@example.com"], subject="s2", body="b2")
    assert len(svc.sent()) == 2


@pytest.mark.asyncio
async def test_send_email_real_mode_calls_graph_send_mail():
    """Real email mode uses Graph sendMail and marks the record sent."""
    requests = []

    def fake_urlopen(req: Any, timeout: float) -> _FakeResponse:
        requests.append((req, timeout))
        if "oauth2/v2.0/token" in req.full_url:
            return _FakeResponse({"access_token": "graph-token"})
        return _FakeResponse(None)

    svc = NotificationService(mode="real", graph_sender="legalops@example.com")

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        rec = await svc.send_email(
            to=["approver@example.com"],
            subject="Approval",
            body="Please approve",
            cc=["legal@example.com"],
        )

    assert rec.status == NotificationStatus.SENT
    assert len(requests) == 2
    token_req = requests[0][0]
    send_req = requests[1][0]
    assert token_req.get_method() == "POST"
    assert "oauth2/v2.0/token" in token_req.full_url
    assert send_req.get_method() == "POST"
    assert "/users/legalops%40example.com/sendMail" in send_req.full_url
    assert send_req.headers["Authorization"] == "Bearer graph-token"
    payload = json.loads(send_req.data.decode("utf-8"))
    to_address = payload["message"]["toRecipients"][0]["emailAddress"]["address"]
    assert to_address == "approver@example.com"
    assert payload["message"]["ccRecipients"][0]["emailAddress"]["address"] == "legal@example.com"


@pytest.mark.asyncio
async def test_send_email_real_mode_requires_sender():
    """Real email mode fails closed before network when sender is missing."""
    svc = NotificationService(mode="real", graph_sender="")
    with pytest.raises(NotificationError, match="EXCHANGE_SENDER_UPN"):
        await svc.send_email(to=["a@example.com"], subject="s", body="b")


# ---------------------------------------------------------------------------
# send_teams_card
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_teams_card_returns_notification_record():
    """send_teams_card() must return a NotificationRecord."""
    svc = _stub_service()
    rec = await svc.send_teams_card(
        channel_or_user="general",
        title="Approval needed",
        body="Please review contract #42",
    )
    assert isinstance(rec, NotificationRecord)
    assert rec.channel == NotificationChannel.TEAMS
    assert rec.to == ("general",)
    assert rec.subject == "Approval needed"


@pytest.mark.asyncio
async def test_send_teams_card_stub_mode_sets_status_sent():
    """In stub mode, send_teams_card() must set status=SENT."""
    svc = _stub_service()
    rec = await svc.send_teams_card("user@example.com", "t", "b")
    assert rec.status == NotificationStatus.SENT


@pytest.mark.asyncio
async def test_send_teams_card_queued_mode_sets_status_queued():
    """In non-stub mode, send_teams_card() must set status=QUEUED."""
    svc = _queued_service()
    rec = await svc.send_teams_card("user@example.com", "t", "b")
    assert rec.status == NotificationStatus.QUEUED


@pytest.mark.asyncio
async def test_send_teams_card_default_kind_is_info():
    """send_teams_card() must default to TeamsCardKind.INFO."""
    svc = _stub_service()
    rec = await svc.send_teams_card("ch", "title", "body")
    assert rec.metadata["kind"] == TeamsCardKind.INFO.value


@pytest.mark.asyncio
async def test_send_teams_card_explicit_kind():
    """send_teams_card() must store the explicit kind in metadata."""
    svc = _stub_service()
    rec = await svc.send_teams_card(
        "ch",
        "Approval",
        "body",
        kind=TeamsCardKind.APPROVAL_REQUEST,
    )
    assert rec.metadata["kind"] == "approval_request"


@pytest.mark.asyncio
async def test_send_teams_card_deep_link_stored_in_metadata():
    """send_teams_card() must persist deep_link in metadata."""
    svc = _stub_service()
    rec = await svc.send_teams_card(
        "ch",
        "t",
        "b",
        deep_link="https://app.example.com/contracts/42",
    )
    assert rec.metadata["deep_link"] == "https://app.example.com/contracts/42"


@pytest.mark.asyncio
async def test_send_teams_card_extra_metadata_merged():
    """send_teams_card() must merge extra metadata kwarg into record.metadata."""
    svc = _stub_service()
    rec = await svc.send_teams_card("ch", "t", "b", metadata={"contract_id": 7})
    assert rec.metadata["contract_id"] == 7


@pytest.mark.asyncio
async def test_send_teams_card_real_mode_posts_adaptive_card():
    """Real Teams mode posts an adaptive card payload to the configured webhook."""
    captured: dict[str, Any] = {}

    def fake_urlopen(req: Any, timeout: float) -> _FakeResponse:
        captured["req"] = req
        return _FakeResponse(None)

    svc = NotificationService(mode="real", teams_webhook_url="https://teams.example/webhook")
    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        rec = await svc.send_teams_card(
            "legalops",
            "SLA warning",
            "Please review",
            deep_link="https://legalops.example/reviews/1",
        )

    assert rec.status == NotificationStatus.SENT
    req = captured["req"]
    assert req.get_method() == "POST"
    assert req.full_url == "https://teams.example/webhook"
    payload = json.loads(req.data.decode("utf-8"))
    card = payload["attachments"][0]["content"]
    assert card["body"][0]["text"] == "SLA warning"
    assert card["actions"][0]["url"] == "https://legalops.example/reviews/1"


@pytest.mark.asyncio
async def test_send_teams_card_real_mode_requires_webhook():
    """Real Teams mode fails closed when TEAMS_WEBHOOK_URL is missing."""
    svc = NotificationService(mode="real", teams_webhook_url="")
    with pytest.raises(NotificationError, match="TEAMS_WEBHOOK_URL"):
        await svc.send_teams_card("legalops", "title", "body")


# ---------------------------------------------------------------------------
# send_desknets
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_desknets_returns_notification_record():
    """send_desknets() must return a NotificationRecord with channel=DESKNETS."""
    svc = _stub_service()
    rec = await svc.send_desknets(
        upn="user@corp.example.com",
        subject="承認依頼",
        body="契約書 #5 をご確認ください",
    )
    assert isinstance(rec, NotificationRecord)
    assert rec.channel == NotificationChannel.DESKNETS
    assert rec.to == ("user@corp.example.com",)


@pytest.mark.asyncio
async def test_send_desknets_stub_mode_sets_status_sent():
    """In stub mode, send_desknets() must set status=SENT."""
    svc = _stub_service()
    rec = await svc.send_desknets("u@c.jp", "s", "b")
    assert rec.status == NotificationStatus.SENT


@pytest.mark.asyncio
async def test_send_desknets_queued_mode_sets_status_queued():
    """In non-stub mode, send_desknets() must set status=QUEUED."""
    svc = _queued_service()
    rec = await svc.send_desknets("u@c.jp", "s", "b")
    assert rec.status == NotificationStatus.QUEUED


@pytest.mark.asyncio
async def test_send_desknets_metadata_stored():
    """send_desknets() must preserve extra metadata."""
    svc = _stub_service()
    rec = await svc.send_desknets("u@c.jp", "s", "b", metadata={"workflow_id": 123})
    assert rec.metadata["workflow_id"] == 123


@pytest.mark.asyncio
async def test_send_desknets_real_mode_posts_webhook_payload():
    """Real DeskNet's mode posts a minimal workflow payload to its webhook."""
    captured: dict[str, Any] = {}

    def fake_urlopen(req: Any, timeout: float) -> _FakeResponse:
        captured["req"] = req
        return _FakeResponse(None)

    svc = NotificationService(mode="real", desknets_webhook_url="https://desknets.example/hook")
    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        rec = await svc.send_desknets(
            "approver@example.com",
            "承認依頼",
            "契約書を確認してください",
            metadata={"workflow_id": 123},
        )

    assert rec.status == NotificationStatus.SENT
    req = captured["req"]
    assert req.get_method() == "POST"
    assert req.full_url == "https://desknets.example/hook"
    payload = json.loads(req.data.decode("utf-8"))
    assert payload["to"] == "approver@example.com"
    assert payload["metadata"]["workflow_id"] == 123


@pytest.mark.asyncio
async def test_send_desknets_real_mode_requires_webhook():
    """Real DeskNet's mode fails closed when DESKNETS_WEBHOOK_URL is missing."""
    svc = NotificationService(mode="real", desknets_webhook_url="")
    with pytest.raises(NotificationError, match="DESKNETS_WEBHOOK_URL"):
        await svc.send_desknets("u@c.jp", "s", "b")


# ---------------------------------------------------------------------------
# sent() and clear()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sent_returns_copy_of_records():
    """sent() must return all records sent so far (as a copy)."""
    svc = _stub_service()
    await svc.send_email(to=["a@example.com"], subject="s1", body="b")
    await svc.send_teams_card("ch", "t", "b")
    records = svc.sent()
    assert len(records) == 2
    # Modifying the returned list must not affect internal state.
    records.clear()
    assert len(svc.sent()) == 2


@pytest.mark.asyncio
async def test_clear_empties_sent_list():
    """clear() must remove all accumulated records."""
    svc = _stub_service()
    await svc.send_email(to=["a@example.com"], subject="s", body="b")
    assert len(svc.sent()) == 1
    svc.clear()
    assert len(svc.sent()) == 0


# ---------------------------------------------------------------------------
# Module-level DB helpers: list_for_user / mark_read / mark_all_read
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_for_user_returns_owned_unread_notifications(
    notification_db_session, notification_actors
):
    """list_for_user() maps persisted notifications to the public schema."""
    u1, u2, contract_id = (
        notification_actors["user1"],
        notification_actors["user2"],
        notification_actors["contract"],
    )
    notification_db_session.add_all(
        [
            Notification(
                recipient_id=u1,
                channel=NotificationChannel.IN_APP.value,
                category="workflow",
                subject="Review needed",
                body="Please review contract",
                contract_id=contract_id,
                status=NotificationStatus.SENT.value,
            ),
            Notification(
                recipient_id=u2,
                channel=NotificationChannel.IN_APP.value,
                category="workflow",
                subject="Other user",
                body=None,
                status=NotificationStatus.SENT.value,
            ),
        ]
    )
    await notification_db_session.flush()

    items, total = await list_for_user(notification_db_session, user_id=u1, status="unread")

    assert total == 1
    assert len(items) == 1
    assert items[0].user_id == u1
    assert items[0].title == "Review needed"
    assert items[0].status == "unread"
    assert items[0].related_type == "contract"
    assert items[0].related_id == contract_id


@pytest.mark.asyncio
async def test_list_for_user_filters_channel_alias_and_paginates(
    notification_db_session, notification_actors
):
    """The API's email alias is mapped to the MAIL channel and pagination is applied."""
    u99 = notification_actors["user99"]
    for idx in range(3):
        notification_db_session.add(
            Notification(
                recipient_id=u99,
                channel=NotificationChannel.MAIL.value,
                category="mail",
                subject=f"Mail {idx}",
                body=None,
                status=NotificationStatus.SENT.value,
            )
        )
    notification_db_session.add(
        Notification(
            recipient_id=u99,
            channel=NotificationChannel.TEAMS.value,
            category="teams",
            subject="Teams",
            body=None,
            status=NotificationStatus.SENT.value,
        )
    )
    await notification_db_session.flush()

    items, total = await list_for_user(
        notification_db_session,
        user_id=u99,
        status="unread",
        channel="email",
        page=2,
        size=2,
    )

    assert total == 3
    assert len(items) == 1
    assert items[0].channel == NotificationChannel.MAIL.value


@pytest.mark.asyncio
async def test_mark_read_sets_read_at_and_status(notification_db_session, notification_actors):
    """mark_read() marks only the owning user's notification as read."""
    u1 = notification_actors["user1"]
    notification = Notification(
        recipient_id=u1,
        channel=NotificationChannel.IN_APP.value,
        category="workflow",
        subject="Read me",
        body=None,
        status=NotificationStatus.SENT.value,
    )
    notification_db_session.add(notification)
    await notification_db_session.flush()

    out = await mark_read(notification_db_session, notification_id=notification.id, user_id=u1)

    assert out.status == "read"
    assert out.read_at is not None
    refreshed = (
        await notification_db_session.execute(
            select(Notification).where(Notification.id == notification.id)
        )
    ).scalar_one()
    assert refreshed.status == NotificationStatus.READ.value
    assert refreshed.read_at is not None


@pytest.mark.asyncio
async def test_mark_read_rejects_other_user(notification_db_session, notification_actors):
    """A user cannot mark another user's notification as read."""
    u1, u2 = notification_actors["user1"], notification_actors["user2"]
    notification = Notification(
        recipient_id=u1,
        channel=NotificationChannel.IN_APP.value,
        category="workflow",
        subject="Private",
        body=None,
        status=NotificationStatus.SENT.value,
    )
    notification_db_session.add(notification)
    await notification_db_session.flush()

    with pytest.raises(PermissionError):
        await mark_read(notification_db_session, notification_id=notification.id, user_id=u2)


@pytest.mark.asyncio
async def test_mark_read_raises_lookup_error(notification_db_session, notification_actors):
    """mark_read() raises LookupError for a missing notification."""
    with pytest.raises(LookupError):
        await mark_read(
            notification_db_session, notification_id=42, user_id=notification_actors["user1"]
        )


@pytest.mark.asyncio
async def test_mark_all_read_marks_only_unread_owned_rows(
    notification_db_session, notification_actors
):
    """mark_all_read() updates unread notifications belonging to the caller."""
    u1, u2 = notification_actors["user1"], notification_actors["user2"]
    notification_db_session.add_all(
        [
            Notification(
                recipient_id=u1,
                channel=NotificationChannel.IN_APP.value,
                category="workflow",
                subject="One",
                body=None,
                status=NotificationStatus.SENT.value,
            ),
            Notification(
                recipient_id=u1,
                channel=NotificationChannel.MAIL.value,
                category="mail",
                subject="Two",
                body=None,
                status=NotificationStatus.SENT.value,
            ),
            Notification(
                recipient_id=u2,
                channel=NotificationChannel.IN_APP.value,
                category="workflow",
                subject="Other",
                body=None,
                status=NotificationStatus.SENT.value,
            ),
        ]
    )
    await notification_db_session.flush()

    count = await mark_all_read(notification_db_session, user_id=u1)

    assert count == 2
    items, total = await list_for_user(notification_db_session, user_id=u1, status="read")
    assert total == 2
    assert all(item.status == "read" for item in items)
