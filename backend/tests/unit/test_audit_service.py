"""Unit tests for audit_service.py.

Covers:
- AuditService.log() — persister callback invoked, HMAC chain linking
- AuditService.verify_chain() — intact / corrupted / empty / partial-range
- Module-level list_logs() / list_for_target() — filtering and pagination
- Module-level verify_chain() wrapper — returns AuditVerifyResponse
- Module-level export_csv() — yields header and rows
- GENESIS_HASH constant and _json_default serialiser edge cases
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from app.models.enums import AuditAction
from app.services import audit_service as svc_module
from app.services.audit_service import (
    GENESIS_HASH,
    AuditRecord,
    AuditService,
    _json_default,
    list_for_target,
    list_logs,
    verify_chain,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service(*, persister=None, fetcher=None) -> AuditService:
    """Return an AuditService with a fixed HMAC secret for determinism."""
    return AuditService(
        secret=b"test-secret-32-bytes-pad-pad-pad!",
        persister=persister,
        fetcher=fetcher,
    )


async def _log_n(service: AuditService, n: int, target_type: str = "contract") -> list[AuditRecord]:
    """Append *n* records in-memory and return them."""
    records = []
    for i in range(n):
        r = await service.log(
            action=AuditAction.CONTRACT_CREATE,
            target_type=target_type,
            target_id=str(i),
            user_id=uuid4(),
            before=None,
            after={"index": i},
            session=None,
        )
        records.append(r)
    return records


# ---------------------------------------------------------------------------
# AuditService.log — in-memory path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_log_returns_audit_record():
    """log() must return an AuditRecord with the correct fields."""
    service = _make_service()
    uid = uuid4()
    rec = await service.log(
        action=AuditAction.CONTRACT_CREATE,
        target_type="contract",
        target_id="42",
        user_id=uid,
        before=None,
        after={"title": "test"},
        session=None,
    )
    assert isinstance(rec, AuditRecord)
    assert rec.action == AuditAction.CONTRACT_CREATE.value
    assert rec.target_type == "contract"
    assert rec.target_id == "42"
    assert rec.user_id == uid
    assert rec.after == {"title": "test"}
    assert len(rec.event_hash) == 64


@pytest.mark.asyncio
async def test_log_chains_prev_hash():
    """Each successive record's prev_hash must equal the previous event_hash."""
    service = _make_service()
    records = await _log_n(service, 3)
    assert records[0].prev_hash == GENESIS_HASH
    assert records[1].prev_hash == records[0].event_hash
    assert records[2].prev_hash == records[1].event_hash


@pytest.mark.asyncio
async def test_log_accepts_enum_action():
    """log() must accept an AuditAction enum and store its .value."""
    service = _make_service()
    rec = await service.log(
        action=AuditAction.USER_LOGIN,
        target_type="user",
        target_id=None,
        user_id=None,
        before=None,
        after=None,
        session=None,
    )
    assert rec.action == "user.login"


@pytest.mark.asyncio
async def test_log_accepts_string_action():
    """log() must accept a plain string action."""
    service = _make_service()
    rec = await service.log(
        action="custom.action",
        target_type="thing",
        target_id=None,
        user_id=None,
        before=None,
        after=None,
        session=None,
    )
    assert rec.action == "custom.action"


@pytest.mark.asyncio
async def test_log_calls_persister_when_provided():
    """When a persister is supplied, it must be awaited with (record, session)."""
    captured: list[tuple] = []

    async def fake_persister(record: AuditRecord, session):
        captured.append((record, session))

    service = _make_service(persister=fake_persister)
    fake_session = MagicMock()
    rec = await service.log(
        action=AuditAction.CONTRACT_UPDATE,
        target_type="contract",
        target_id="7",
        user_id=None,
        before={"x": 1},
        after={"x": 2},
        session=fake_session,
    )
    assert len(captured) == 1
    assert captured[0][0] is rec
    assert captured[0][1] is fake_session


@pytest.mark.asyncio
async def test_log_with_persister_uses_fetcher_for_prev_hash():
    """When persister + fetcher are set, prev_hash comes from fetcher's latest."""
    existing_hash = "a" * 64
    existing_rec = AuditRecord(
        id=uuid4(),
        timestamp=datetime.now(UTC),
        action="contract.create",
        target_type="contract",
        target_id="1",
        user_id=None,
        before=None,
        after=None,
        prev_hash=GENESIS_HASH,
        event_hash=existing_hash,
    )

    async def fake_fetcher(from_date, to_date, session):
        return [existing_rec]

    async def fake_persister(record, session):
        pass

    service = _make_service(persister=fake_persister, fetcher=fake_fetcher)
    rec = await service.log(
        action=AuditAction.CONTRACT_UPDATE,
        target_type="contract",
        target_id="2",
        user_id=None,
        before=None,
        after=None,
        session=None,
    )
    assert rec.prev_hash == existing_hash


@pytest.mark.asyncio
async def test_log_with_persister_genesis_when_fetcher_returns_empty():
    """Fetcher returning [] means GENESIS_HASH is used as prev."""

    async def fake_fetcher(from_date, to_date, session):
        return []

    async def fake_persister(record, session):
        pass

    service = _make_service(persister=fake_persister, fetcher=fake_fetcher)
    rec = await service.log(
        action=AuditAction.CONTRACT_CREATE,
        target_type="contract",
        target_id=None,
        user_id=None,
        before=None,
        after=None,
        session=None,
    )
    assert rec.prev_hash == GENESIS_HASH


# ---------------------------------------------------------------------------
# AuditService.verify_chain
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_chain_empty_returns_ok():
    """verify_chain on an empty store must return ok=True, total=0."""
    service = _make_service()
    result = await service.verify_chain(session=None)
    assert result.ok is True
    assert result.total == 0
    assert result.first_broken_event_id is None
    assert result.first_broken_index is None


@pytest.mark.asyncio
async def test_verify_chain_intact():
    """verify_chain on a correctly built chain must return ok=True."""
    service = _make_service()
    await _log_n(service, 5)
    result = await service.verify_chain(session=None)
    assert result.ok is True
    assert result.total == 5


@pytest.mark.asyncio
async def test_verify_chain_detects_corrupted_event_hash():
    """Mutating a record's event_hash must cause verify_chain to report broken."""
    service = _make_service()
    await _log_n(service, 4)
    # Tamper with the third record's event_hash directly.
    service._records[2] = AuditRecord(
        id=service._records[2].id,
        timestamp=service._records[2].timestamp,
        action=service._records[2].action,
        target_type=service._records[2].target_type,
        target_id=service._records[2].target_id,
        user_id=service._records[2].user_id,
        before=service._records[2].before,
        after=service._records[2].after,
        prev_hash=service._records[2].prev_hash,
        event_hash="badhash" + "0" * 57,  # 64 chars, but wrong
    )
    result = await service.verify_chain(session=None)
    assert result.ok is False
    assert result.first_broken_index == 2


@pytest.mark.asyncio
async def test_verify_chain_detects_broken_prev_hash_link():
    """Mutating a record's prev_hash must cause verify_chain to report broken."""
    service = _make_service()
    await _log_n(service, 3)
    # Break the chain at index 1 by mutating prev_hash.
    r = service._records[1]
    service._records[1] = AuditRecord(
        id=r.id,
        timestamp=r.timestamp,
        action=r.action,
        target_type=r.target_type,
        target_id=r.target_id,
        user_id=r.user_id,
        before=r.before,
        after=r.after,
        prev_hash="0" * 64,  # wrong: should link to records[0].event_hash
        event_hash=r.event_hash,
    )
    result = await service.verify_chain(session=None)
    assert result.ok is False
    assert result.first_broken_index == 1


@pytest.mark.asyncio
async def test_verify_chain_date_range_filters_records():
    """verify_chain respects from_date / to_date."""
    service = _make_service()
    await _log_n(service, 4)
    # Filter to just the first two records.
    ts0 = service._records[0].timestamp
    ts1 = service._records[1].timestamp
    result = await service.verify_chain(from_date=ts0, to_date=ts1, session=None)
    assert result.ok is True
    assert result.total == 2


@pytest.mark.asyncio
async def test_verify_chain_uses_fetcher_when_provided():
    """verify_chain uses the external fetcher when provided."""
    service = _make_service()
    # Pre-build a valid 2-record chain in a temporary service to get real hashes.
    tmp = _make_service()
    recs = await _log_n(tmp, 2)

    async def fake_fetcher(from_date, to_date, session):
        return recs

    service._fetcher = fake_fetcher
    result = await service.verify_chain(session=None)
    assert result.ok is True
    assert result.total == 2


# ---------------------------------------------------------------------------
# Module-level list_logs() and list_for_target()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_logs_returns_all_records(monkeypatch):
    """list_logs() without filters should return all stored records."""
    fresh_svc = AuditService(secret=b"test-secret-32-bytes-pad-pad-pad!")
    monkeypatch.setattr(svc_module, "_svc", fresh_svc)
    for i in range(3):
        await fresh_svc.log(
            action=AuditAction.CONTRACT_CREATE,
            target_type="contract",
            target_id=str(i),
            user_id=None,
            before=None,
            after={"i": i},
            session=None,
        )
    items, total = await list_logs(None)
    assert total == 3
    assert len(items) == 3


@pytest.mark.asyncio
async def test_list_logs_filters_by_target_type(monkeypatch):
    """list_logs() must filter records by target_type."""
    fresh_svc = AuditService(secret=b"test-secret-32-bytes-pad-pad-pad!")
    monkeypatch.setattr(svc_module, "_svc", fresh_svc)
    await fresh_svc.log(
        action=AuditAction.CONTRACT_CREATE,
        target_type="contract",
        target_id="1",
        user_id=None,
        before=None,
        after=None,
        session=None,
    )
    await fresh_svc.log(
        action=AuditAction.USER_LOGIN,
        target_type="user",
        target_id="99",
        user_id=None,
        before=None,
        after=None,
        session=None,
    )
    items, total = await list_logs(None, target_type="contract")
    assert total == 1
    assert items[0]["target_type"] == "contract"


@pytest.mark.asyncio
async def test_list_logs_filters_by_action(monkeypatch):
    """list_logs() must filter records by action string."""
    fresh_svc = AuditService(secret=b"test-secret-32-bytes-pad-pad-pad!")
    monkeypatch.setattr(svc_module, "_svc", fresh_svc)
    await fresh_svc.log(
        action=AuditAction.CONTRACT_CREATE,
        target_type="contract",
        target_id="1",
        user_id=None,
        before=None,
        after=None,
        session=None,
    )
    await fresh_svc.log(
        action=AuditAction.CONTRACT_DELETE,
        target_type="contract",
        target_id="1",
        user_id=None,
        before=None,
        after=None,
        session=None,
    )
    items, total = await list_logs(None, action="contract.create")
    assert total == 1
    assert items[0]["action"] == "contract.create"


@pytest.mark.asyncio
async def test_list_logs_pagination(monkeypatch):
    """list_logs() must respect page and size parameters."""
    fresh_svc = AuditService(secret=b"test-secret-32-bytes-pad-pad-pad!")
    monkeypatch.setattr(svc_module, "_svc", fresh_svc)
    for i in range(5):
        await fresh_svc.log(
            action=AuditAction.CONTRACT_UPDATE,
            target_type="contract",
            target_id=str(i),
            user_id=None,
            before=None,
            after=None,
            session=None,
        )
    items_p1, total = await list_logs(None, page=1, size=2)
    items_p2, _ = await list_logs(None, page=2, size=2)
    assert total == 5
    assert len(items_p1) == 2
    assert len(items_p2) == 2


@pytest.mark.asyncio
async def test_list_for_target_delegates_to_list_logs(monkeypatch):
    """list_for_target() must delegate to list_logs with correct args."""
    fresh_svc = AuditService(secret=b"test-secret-32-bytes-pad-pad-pad!")
    monkeypatch.setattr(svc_module, "_svc", fresh_svc)
    await fresh_svc.log(
        action=AuditAction.CONTRACT_CREATE,
        target_type="contract",
        target_id="55",
        user_id=None,
        before=None,
        after=None,
        session=None,
    )
    items, total = await list_for_target(None, target_type="contract", target_id="55")
    assert total == 1
    assert items[0]["target_type"] == "contract"


# ---------------------------------------------------------------------------
# Module-level verify_chain() wrapper
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_module_verify_chain_returns_audit_verify_response(monkeypatch):
    """Module-level verify_chain() must return AuditVerifyResponse."""
    from app.schemas.audit_log import AuditVerifyResponse

    fresh_svc = AuditService(secret=b"test-secret-32-bytes-pad-pad-pad!")
    monkeypatch.setattr(svc_module, "_svc", fresh_svc)
    await fresh_svc.log(
        action=AuditAction.CONTRACT_CREATE,
        target_type="contract",
        target_id="1",
        user_id=None,
        before=None,
        after=None,
        session=None,
    )
    response = await verify_chain(None)
    assert isinstance(response, AuditVerifyResponse)
    assert response.verified is True
    assert response.total == 1
    assert response.ok is True


# ---------------------------------------------------------------------------
# export_csv()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_csv_yields_header_and_rows(monkeypatch):
    """export_csv() must yield a CSV header followed by one row per record."""
    from app.services.audit_service import export_csv

    fresh_svc = AuditService(secret=b"test-secret-32-bytes-pad-pad-pad!")
    monkeypatch.setattr(svc_module, "_svc", fresh_svc)
    await fresh_svc.log(
        action=AuditAction.CONTRACT_CREATE,
        target_type="contract",
        target_id="10",
        user_id=None,
        before=None,
        after=None,
        session=None,
    )
    lines = list(export_csv(None))
    assert len(lines) == 2  # header + 1 row
    reader = csv.reader(io.StringIO("".join(lines)))
    rows = list(reader)
    assert rows[0][0] == "id"
    assert rows[1][3] == "contract"  # target_type column


# ---------------------------------------------------------------------------
# _json_default serialiser
# ---------------------------------------------------------------------------


def test_json_default_handles_datetime():

    from datetime import datetime

    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    assert _json_default(now) == now.isoformat()


def test_json_default_handles_uuid():
    uid = UUID("12345678-1234-5678-1234-567812345678")
    assert _json_default(uid) == str(uid)


def test_json_default_handles_decimal():
    import decimal

    d = decimal.Decimal("3.14")
    assert _json_default(d) == pytest.approx(3.14)


def test_json_default_handles_enum_with_value():
    """Objects with a .value attribute (Enum-like) must return .value."""
    assert _json_default(AuditAction.CONTRACT_CREATE) == "contract.create"


def test_json_default_raises_for_unknown_type():
    with pytest.raises(TypeError):
        _json_default(object())


# ---------------------------------------------------------------------------
# Module-level log() convenience wrapper
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_module_log_appends_record(monkeypatch):
    """Module-level log() must call _svc.log() and persist a record."""
    from app.services.audit_service import log as module_log

    fresh_svc = AuditService(secret=b"test-secret-32-bytes-pad-pad-pad!")
    monkeypatch.setattr(svc_module, "_svc", fresh_svc)
    await module_log(
        None,
        actor_id=1,
        action=AuditAction.CONTRACT_CREATE,
        target_type="contract",
        target_id=42,
        payload={"title": "hello"},
    )
    assert len(fresh_svc._records) == 1
    assert fresh_svc._records[0].target_id == "42"
    assert fresh_svc._records[0].after == {"title": "hello"}
    # [P2 audit fix] The wrapper must forward actor_id -> user_id so the
    # audit trail records WHO performed the change (J-SOX / ISO27001 要件).
    assert fresh_svc._records[0].user_id == 1


@pytest.mark.asyncio
async def test_module_log_records_to_dict_surfaces_actor(monkeypatch):
    """_record_to_dict() must surface the captured actor as actor_id."""
    from app.services.audit_service import _record_to_dict
    from app.services.audit_service import log as module_log

    fresh_svc = AuditService(secret=b"test-secret-32-bytes-pad-pad-pad!")
    monkeypatch.setattr(svc_module, "_svc", fresh_svc)
    await module_log(
        None,
        actor_id=7,
        action=AuditAction.CONTRACT_UPDATE,
        target_type="contract",
        target_id=99,
        payload={"k": "v"},
    )
    as_dict = _record_to_dict(0, fresh_svc._records[0])
    assert as_dict["actor_id"] == 7
    assert as_dict["target_id"] == 99
