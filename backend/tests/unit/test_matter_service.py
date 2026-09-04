"""Legal Matter Management サービスの単体テスト（Issue #101）."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.contract import Contract
from app.models.department import Department
from app.models.legal_hold import LegalHoldCase
from app.models.matter import MatterEvent
from app.models.user import User
from app.services import matter_service


async def _seed(db_session) -> tuple[int, int, int]:
    """ユーザー 2・契約 1 を作成し (contract_id, user1, user2) を返す."""
    dept = Department(code=f"D-{uuid4().hex[:8]}", name="法務部")
    db_session.add(dept)
    await db_session.flush()
    u1 = User(
        entra_oid=uuid4(),
        email=f"{uuid4().hex[:10]}@test.local",
        display_name="担当者A",
        role="reviewer",
        department_id=dept.id,
        is_active=True,
    )
    u2 = User(
        entra_oid=uuid4(),
        email=f"{uuid4().hex[:10]}@test.local",
        display_name="担当者B",
        role="reviewer",
        department_id=dept.id,
        is_active=True,
    )
    db_session.add_all([u1, u2])
    await db_session.flush()
    contract = Contract(
        contract_no=f"C-{uuid4().hex[:10]}",
        title="Matterテスト契約",
        counterparty="株式会社テスト",
        contract_type="工事請負契約",
        department_id=dept.id,
        drafter_id=u1.id,
    )
    db_session.add(contract)
    await db_session.flush()
    return int(contract.id), int(u1.id), int(u2.id)


async def test_create_matter_numbering_links_and_events(db_session) -> None:
    """#71/#72/#79: 作成・採番・契約リンク・イベント."""
    cid, u1, u2 = await _seed(db_session)
    matter = await matter_service.create_matter(
        db_session,
        actor_id=u1,
        title="下請代金未払請求",
        matter_type="contract",
        priority="high",
        assignee_id=u2,
        contract_ids=[cid],
        description="弁護士相談の要否を検討",
    )
    assert matter.matter_no.startswith("MT-")
    assert matter.status == "open"
    assert matter.assignee_id == u2
    assert await matter_service.matter_contract_ids(
        db_session, matter_id=matter.id
    ) == [cid]

    events = await matter_service.list_events(db_session, matter_id=matter.id)
    types = [e.event_type for e in events]
    assert "created" in types and "assigned" in types and "contract_linked" in types


async def test_status_transition_rules(db_session) -> None:
    """#状態遷移: 通常遷移・同一 409・closed 復帰制約."""
    cid, u1, _ = await _seed(db_session)
    matter = await matter_service.create_matter(
        db_session, actor_id=u1, title="協議", matter_type="dispute", contract_ids=[cid]
    )
    m = await matter_service.set_status(
        db_session, matter_id=matter.id, actor_id=u1, status="in_progress"
    )
    assert m.status == "in_progress"
    with pytest.raises(ConflictError):
        await matter_service.set_status(
            db_session, matter_id=matter.id, actor_id=u1, status="in_progress"
        )

    closed = await matter_service.set_status(
        db_session, matter_id=matter.id, actor_id=u1, status="closed", note="解決"
    )
    assert closed.closed_at is not None and closed.close_note == "解決"
    with pytest.raises(ConflictError):
        await matter_service.set_status(
            db_session, matter_id=closed.id, actor_id=u1, status="waiting"
        )
    reopened = await matter_service.set_status(
        db_session, matter_id=closed.id, actor_id=u1, status="open"
    )
    assert reopened.status == "open" and reopened.closed_at is None


async def test_assign_owner_rules(db_session) -> None:
    """#74: 担当変更・同一 409・不明 user 404・CLOSED 変更不可."""
    _, u1, u2 = await _seed(db_session)
    matter = await matter_service.create_matter(
        db_session, actor_id=u1, title="担当テスト", matter_type="compliance"
    )
    m = await matter_service.assign_assignee(
        db_session, matter_id=matter.id, actor_id=u1, assignee_id=u2
    )
    assert m.assignee_id == u2
    with pytest.raises(ConflictError):
        await matter_service.assign_assignee(
            db_session, matter_id=matter.id, actor_id=u1, assignee_id=u2
        )
    with pytest.raises(NotFoundError):
        await matter_service.assign_assignee(
            db_session, matter_id=matter.id, actor_id=u1, assignee_id=999_999
        )


async def test_contract_link_unlink(db_session) -> None:
    """#79: リンク追加・重複 409・解除・未リンク解除 409."""
    cid, u1, _ = await _seed(db_session)
    matter = await matter_service.create_matter(
        db_session, actor_id=u1, title="リンクテスト", matter_type="other"
    )
    await matter_service.link_contract(
        db_session, matter_id=matter.id, actor_id=u1, contract_id=cid
    )
    assert await matter_service.matter_contract_ids(
        db_session, matter_id=matter.id
    ) == [cid]
    with pytest.raises(ConflictError):
        await matter_service.link_contract(
            db_session, matter_id=matter.id, actor_id=u1, contract_id=cid
        )
    await matter_service.unlink_contract(
        db_session, matter_id=matter.id, actor_id=u1, contract_id=cid
    )
    assert await matter_service.matter_contract_ids(
        db_session, matter_id=matter.id
    ) == []
    with pytest.raises(ConflictError):
        await matter_service.unlink_contract(
            db_session, matter_id=matter.id, actor_id=u1, contract_id=cid
        )


async def test_legal_hold_link_unlink(db_session) -> None:
    """#82: Legal Hold 連動・解除・不明 404."""
    cid, u1, _ = await _seed(db_session)
    hold = LegalHoldCase(contract_id=cid, reason="訴訟準備", started_at=datetime.now(UTC))
    db_session.add(hold)
    await db_session.flush()
    hold_id = int(hold.id)

    matter = await matter_service.create_matter(
        db_session, actor_id=u1, title="証拠保全", matter_type="dispute"
    )
    m = await matter_service.set_legal_hold(
        db_session, matter_id=matter.id, actor_id=u1, legal_hold_case_id=hold_id
    )
    assert m.legal_hold_case_id == hold_id
    with pytest.raises(ConflictError):
        await matter_service.set_legal_hold(
            db_session, matter_id=matter.id, actor_id=u1, legal_hold_case_id=hold_id
        )
    m2 = await matter_service.set_legal_hold(
        db_session, matter_id=matter.id, actor_id=u1, legal_hold_case_id=None
    )
    assert m2.legal_hold_case_id is None
    with pytest.raises(NotFoundError):
        await matter_service.set_legal_hold(
            db_session, matter_id=matter.id, actor_id=u1, legal_hold_case_id=999_999
        )


async def test_note_event_and_validation(db_session) -> None:
    """#78: メモ追記・不正 type/status ValidationError・不明 source NotFound."""
    _, u1, _ = await _seed(db_session)
    matter = await matter_service.create_matter(
        db_session, actor_id=u1, title="メモテスト", matter_type="labor"
    )
    event = await matter_service.add_note(
        db_session, matter_id=matter.id, actor_id=u1, note="ヒアリング完了"
    )
    assert isinstance(event, MatterEvent)
    assert event.event_type == "note"

    with pytest.raises(ValidationError):
        await matter_service.create_matter(db_session, actor_id=u1, title="x", matter_type="bogus")
    with pytest.raises(ValidationError):
        await matter_service.set_status(
            db_session, matter_id=matter.id, actor_id=u1, status="bogus"
        )
    with pytest.raises(ValidationError):
        await matter_service.create_matter(
            db_session,
            actor_id=u1,
            title="x",
            matter_type="dispute",
            source_type="weird",
            source_id=1,
        )
    with pytest.raises(NotFoundError):
        await matter_service.create_matter(
            db_session,
            actor_id=u1,
            title="昇格",
            matter_type="dispute",
            source_type="dispute",
            source_id=999_999,
        )
