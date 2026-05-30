"""Unit tests for notification_service.py.

Covers:
- NotificationService.send_email() — success, empty-recipient error, stub vs queued mode
- NotificationService.send_teams_card() — default kind, explicit kind, metadata
- NotificationService.send_desknets() — stub mode, queued mode
- NotificationService.sent() / clear() — introspection helpers
- Module-level list_for_user() — always returns empty (stub)
- Module-level mark_read() — always raises LookupError (stub)
- Module-level mark_all_read() — always returns 0 (stub)
"""

from __future__ import annotations

import pytest

from app.models.enums import NotificationChannel, NotificationStatus
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
# Module-level stubs: list_for_user / mark_read / mark_all_read
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_for_user_returns_empty():
    """list_for_user() stub must return ([], 0) unconditionally."""
    items, total = await list_for_user(None, user_id=1)
    assert items == []
    assert total == 0


@pytest.mark.asyncio
async def test_list_for_user_ignores_filters():
    """list_for_user() stub must ignore status/channel/page/size filters."""
    items, total = await list_for_user(
        None,
        user_id=99,
        status="unread",
        channel="mail",
        page=3,
        size=10,
    )
    assert items == []
    assert total == 0


@pytest.mark.asyncio
async def test_mark_read_raises_lookup_error():
    """mark_read() stub must raise LookupError for any notification_id."""
    with pytest.raises(LookupError):
        await mark_read(None, notification_id=42, user_id=1)


@pytest.mark.asyncio
async def test_mark_all_read_returns_zero():
    """mark_all_read() stub must return 0."""
    count = await mark_all_read(None, user_id=1)
    assert count == 0
