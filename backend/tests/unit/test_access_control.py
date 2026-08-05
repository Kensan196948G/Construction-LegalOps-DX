"""案件単位 ACL・倫理壁サービス（access_control）のテスト."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.models.contract import Contract
from app.models.department import Department
from app.models.user import User
from app.services import access_control


async def _seed_contract(db_session, *, case_category: str | None = None) -> tuple[int, int]:
    dept = Department(code=f"D-{uuid4().hex[:8]}", name="法務部")
    db_session.add(dept)
    await db_session.flush()
    user = User(
        entra_oid=uuid4(),
        email=f"{uuid4().hex[:10]}@test.local",
        display_name="作成者",
        role="drafter",
        department_id=dept.id,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    contract = Contract(
        contract_no=f"C-{uuid4().hex[:10]}",
        title="テスト契約",
        counterparty="株式会社テスト",
        contract_type="請負",
        department_id=dept.id,
        drafter_id=user.id,
        extra_metadata=(
            {"case_category": case_category} if case_category else {}
        ),
    )
    db_session.add(contract)
    await db_session.flush()
    return int(contract.id), int(user.id)


async def _seed_user(db_session) -> int:
    user = User(
        entra_oid=uuid4(),
        email=f"{uuid4().hex[:10]}@test.local",
        display_name="利用者",
        role="viewer",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return int(user.id)


class _Viewer:
    def __init__(self, *, role: str, db_id: int | None) -> None:
        self.role = role
        self.db_id = db_id


async def test_grant_revoke_list_flow(db_session) -> None:
    contract_id, _ = await _seed_contract(db_session)
    grantee = await _seed_user(db_session)

    grant = await access_control.grant_access(
        db_session,
        contract_id=contract_id,
        user_id=grantee,
        access_level="view",
        granted_by=None,
    )
    assert grant.id is not None
    assert grant.revoked_at is None

    grants = await access_control.list_grants(db_session, contract_id=contract_id)
    assert len(grants) == 1

    ok = await access_control.revoke_access(
        db_session, grant_id=int(grant.id), actor_id=0
    )
    assert ok is True
    active = await access_control.get_active_grant(
        db_session, contract_id=contract_id, user_id=grantee
    )
    assert active is None


async def test_grant_access_updates_existing_row(db_session) -> None:
    contract_id, _ = await _seed_contract(db_session)
    grantee = await _seed_user(db_session)
    await access_control.grant_access(
        db_session,
        contract_id=contract_id,
        user_id=grantee,
        access_level="view",
        granted_by=None,
    )
    updated = await access_control.grant_access(
        db_session,
        contract_id=contract_id,
        user_id=grantee,
        access_level="edit",
        granted_by=None,
    )
    grants = await access_control.list_grants(db_session, contract_id=contract_id)
    assert len(grants) == 1
    assert updated.access_level == "edit"


async def test_expired_grant_is_not_active(db_session) -> None:
    contract_id, _ = await _seed_contract(db_session)
    grantee = await _seed_user(db_session)
    await access_control.grant_access(
        db_session,
        contract_id=contract_id,
        user_id=grantee,
        access_level="view",
        granted_by=None,
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    assert (
        await access_control.get_active_grant(
            db_session, contract_id=contract_id, user_id=grantee
        )
        is None
    )


async def test_can_access_roles_and_drafter(db_session) -> None:
    contract_id, drafter_id = await _seed_contract(db_session)
    contract = await db_session.get(Contract, contract_id)
    grantee = await _seed_user(db_session)

    assert await access_control.can_access(
        db_session, viewer=_Viewer(role="admin", db_id=999), contract=contract
    ) is True
    assert await access_control.can_access(
        db_session, viewer=_Viewer(role="viewer", db_id=drafter_id), contract=contract
    ) is True
    assert await access_control.can_access(
        db_session, viewer=_Viewer(role="viewer", db_id=999), contract=contract
    ) is False

    await access_control.grant_access(
        db_session,
        contract_id=contract_id,
        user_id=grantee,
        access_level="view",
        granted_by=None,
    )
    assert await access_control.can_access(
        db_session, viewer=_Viewer(role="viewer", db_id=grantee), contract=contract
    ) is True


async def test_ethical_wall_blocks_sensitive_case(db_session) -> None:
    contract_id, _ = await _seed_contract(
        db_session, case_category="bid_rigging"
    )
    contract = await db_session.get(Contract, contract_id)
    grantee = await _seed_user(db_session)

    assert access_control.is_sensitive_case(contract) is True
    await access_control.grant_access(
        db_session,
        contract_id=contract_id,
        user_id=grantee,
        access_level="view",
        granted_by=None,
        ethical_wall=True,
    )
    # 倫理壁付与は機密案件では通常ロールに効かない
    assert await access_control.can_access(
        db_session, viewer=_Viewer(role="viewer", db_id=grantee), contract=contract
    ) is False
    # admin は通る
    assert await access_control.can_access(
        db_session, viewer=_Viewer(role="admin", db_id=1), contract=contract
    ) is True


async def test_is_sensitive_case_false_for_normal(db_session) -> None:
    contract_id, _ = await _seed_contract(db_session)
    contract = await db_session.get(Contract, contract_id)
    assert access_control.is_sensitive_case(contract) is False
