"""Integration tests for JIT identity resolution (Issue #45).

``get_current_user`` resolves the token principal to a real ``users.id``
(``CurrentUser.db_id``) with just-in-time provisioning. These tests assert
the invariants that replaced the old hash-synthesised ids:

* first authenticated request provisions exactly one ``users`` row and
  repeat requests reuse it (no duplicates);
* ``contracts.drafter_id`` written by the API equals the caller's
  provisioned ``users.id`` (write/read symmetry for drafter scoping);
* a non-privileged user can fetch their own ``/users/{id}`` (was always
  403 while the raw token subject was compared to the int path param);
* the token role is stored truthfully on the provisioned row, an email
  bound to a different Entra oid is rejected instead of merged, and a
  deactivated account stops resolving even while its token is valid.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select, update

from app.models.contract import Contract
from app.models.user import User

CONTRACTS = "/api/v1/contracts"
USERS = "/api/v1/users"


def _headers(role: str, subject: str, *, oid: str | None = None) -> dict[str, str]:
    from app.core.security import create_access_token

    claims: dict[str, Any] = {"role": role}
    if oid is not None:
        claims["oid"] = oid
    token = create_access_token(subject=subject, extra_claims=claims)
    return {"Authorization": f"Bearer {token}"}


def _session_for(engine: Any) -> Any:
    """Short-lived session opened INSIDE the test body.

    Deliberately not the ``db_session`` fixture: a fixture-held session keeps
    its (NullPool) asyncpg connection alive into the teardown phase, where
    pytest-asyncio may finalise on a different event loop and the rollback
    explodes with "Future attached to a different loop". Opening and closing
    within the test keeps every connection on the test's own loop.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    return async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)()


async def _user_rows(engine: Any, email: str) -> list[User]:
    session = _session_for(engine)
    try:
        result = await session.execute(select(User).where(User.email == email))
        return list(result.scalars().all())
    finally:
        await session.close()


async def _user_by_id(engine: Any, user_id: int) -> User:
    session = _session_for(engine)
    try:
        return (await session.execute(select(User).where(User.id == user_id))).scalar_one()
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_first_request_provisions_single_user_row(client: Any, test_engine: Any) -> None:
    """1st request creates exactly one users row; 2nd reuses it."""
    email = "jit-provision-1@example.com"
    headers = _headers("drafter", email)

    assert await _user_rows(test_engine, email) == []

    r1 = await client.get(CONTRACTS, headers=headers)
    assert r1.status_code == 200
    rows = await _user_rows(test_engine, email)
    assert len(rows) == 1
    assert rows[0].role == "drafter"
    assert rows[0].is_active is True

    r2 = await client.get(CONTRACTS, headers=headers)
    assert r2.status_code == 200
    assert len(await _user_rows(test_engine, email)) == 1


@pytest.mark.asyncio
async def test_contract_drafter_id_is_provisioned_users_id(client: Any, test_engine: Any) -> None:
    """POST /contracts writes the caller's real users.id into drafter_id."""
    email = "jit-drafter-2@example.com"
    headers = _headers("drafter", email)
    title = "JIT identity 契約 (drafter_id 検証)"

    r = await client.post(
        CONTRACTS,
        headers=headers,
        json={
            "title": title,
            "contract_type": "工事請負契約",
            "counterparty": "JIT建設",
            "department_id": 1,
        },
    )
    assert r.status_code == 201, r.text

    rows = await _user_rows(test_engine, email)
    assert len(rows) == 1
    session = _session_for(test_engine)
    try:
        contract = (
            await session.execute(select(Contract).where(Contract.title == title))
        ).scalar_one()
        assert contract.drafter_id == rows[0].id
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_drafter_sees_own_contract_in_scoped_list(client: Any) -> None:
    """Write/read symmetry: the drafter-scope filter matches own rows again.

    Before Issue #45 the INSERT used a hash while the WHERE compared the raw
    subject, so a drafter could never see their own contracts.
    """
    email = "jit-scope-3@example.com"
    headers = _headers("drafter", email)
    title = "JIT identity 契約 (scope 検証)"

    created = await client.post(
        CONTRACTS,
        headers=headers,
        json={
            "title": title,
            "contract_type": "工事請負契約",
            "counterparty": "JITスコープ建設",
            "department_id": 1,
        },
    )
    assert created.status_code == 201, created.text

    listed = await client.get(CONTRACTS, headers=headers)
    assert listed.status_code == 200
    titles = [item.get("title") for item in listed.json().get("items", [])]
    assert title in titles


@pytest.mark.asyncio
async def test_get_user_self_access_allowed(client: Any, test_engine: Any) -> None:
    """A non-privileged user can read their own /users/{id} (was 403)."""
    email = "jit-self-4@example.com"
    headers = _headers("drafter", email)

    provision = await client.get(CONTRACTS, headers=headers)
    assert provision.status_code == 200
    rows = await _user_rows(test_engine, email)
    assert len(rows) == 1

    r = await client.get(f"{USERS}/{rows[0].id}", headers=headers)
    assert r.status_code == 200, r.text
    # The masking middleware redacts emails in responses; compare by id.
    assert r.json()["id"] == rows[0].id

    # Another user's row stays forbidden for non-privileged roles.
    other_headers = _headers("drafter", "jit-other-4@example.com")
    other = await client.get(f"{USERS}/{rows[0].id + 999999}", headers=other_headers)
    assert other.status_code == 403


@pytest.mark.asyncio
async def test_token_role_is_stored_truthfully(client: Any, test_engine: Any) -> None:
    """ck_users_role accepts every UserRole (incl. auditor) — no silent clamp."""
    email = "jit-auditor-5@example.com"
    headers = _headers("auditor", email)

    r = await client.get(CONTRACTS, headers=headers)
    assert r.status_code == 200
    rows = await _user_rows(test_engine, email)
    assert len(rows) == 1
    assert rows[0].role == "auditor"


@pytest.mark.asyncio
async def test_same_email_different_oid_is_rejected(client: Any, test_engine: Any) -> None:
    """An email match bound to a different Entra oid must never merge (401).

    Emails get reassigned (offboarding, B2B guests); the oid is the immutable
    identifier. Adopting the row would hand the new principal the old
    identity's contracts, audit trail, and self-access rights.
    """
    import uuid as _uuid

    email = "jit-oid-6@example.com"
    oid_a = str(_uuid.uuid4())
    oid_b = str(_uuid.uuid4())

    first = await client.get(CONTRACTS, headers=_headers("drafter", email, oid=oid_a))
    assert first.status_code == 200
    rows = await _user_rows(test_engine, email)
    assert len(rows) == 1

    hijack = await client.get(CONTRACTS, headers=_headers("drafter", email, oid=oid_b))
    assert hijack.status_code == 401
    # No second row was provisioned and the original binding is untouched.
    rows_after = await _user_rows(test_engine, email)
    assert len(rows_after) == 1
    assert str(rows_after[0].entra_oid) == oid_a


@pytest.mark.asyncio
async def test_deactivated_user_is_rejected(client: Any, test_engine: Any) -> None:
    """is_active=false blocks resolution even while the token is still valid."""
    email = "jit-inactive-7@example.com"
    headers = _headers("drafter", email)

    first = await client.get(CONTRACTS, headers=headers)
    assert first.status_code == 200
    rows = await _user_rows(test_engine, email)
    assert len(rows) == 1

    session = _session_for(test_engine)
    try:
        await session.execute(
            update(User).where(User.email == email).values(is_active=False)
        )
        await session.commit()
    finally:
        await session.close()

    blocked = await client.get(CONTRACTS, headers=headers)
    assert blocked.status_code == 403


@pytest.mark.asyncio
async def test_admin_explicit_identity_link_allows_later_real_oid(
    client: Any, test_engine: Any
) -> None:
    """Admin-only explicit link is the safe path from derived oid to real oid."""
    import uuid as _uuid

    email = "jit-link-8@example.com"
    real_oid = str(_uuid.uuid4())

    first = await client.get(CONTRACTS, headers=_headers("drafter", email))
    assert first.status_code == 200
    rows = await _user_rows(test_engine, email)
    assert len(rows) == 1
    derived_oid = str(rows[0].entra_oid)

    linked = await client.post(
        f"{USERS}/{rows[0].id}/identity-link",
        headers=_headers("admin", "admin-linker@example.com"),
        json={
            "expected_current_entra_oid": derived_oid,
            "new_entra_oid": real_oid,
            "reason": "Operator verified Entra oid during JIT identity migration.",
        },
    )
    assert linked.status_code == 200, linked.text
    assert linked.json()["id"] == rows[0].id
    assert linked.json()["entra_oid"] == real_oid

    # The real oid token now resolves to the existing row instead of creating
    # a second row or failing the same-email/different-oid guard.
    after = await client.get(CONTRACTS, headers=_headers("drafter", email, oid=real_oid))
    assert after.status_code == 200
    rows_after = await _user_rows(test_engine, email)
    assert len(rows_after) == 1
    assert str(rows_after[0].entra_oid) == real_oid

    persisted = await _user_by_id(test_engine, rows[0].id)
    assert persisted.attributes["identity_link_policy"] == "admin_explicit_oid_rebind_v1"
    assert persisted.attributes["identity_link_history"][-1]["from_entra_oid"] == derived_oid
    assert persisted.attributes["identity_link_history"][-1]["to_entra_oid"] == real_oid


@pytest.mark.asyncio
async def test_identity_link_rejects_stale_source_oid(client: Any, test_engine: Any) -> None:
    """The admin must prove the current oid to avoid stale-console mistakes."""
    import uuid as _uuid

    email = "jit-link-stale-9@example.com"
    first = await client.get(CONTRACTS, headers=_headers("drafter", email))
    assert first.status_code == 200
    rows = await _user_rows(test_engine, email)
    assert len(rows) == 1

    stale = await client.post(
        f"{USERS}/{rows[0].id}/identity-link",
        headers=_headers("admin", "admin-linker-stale@example.com"),
        json={
            "expected_current_entra_oid": str(_uuid.uuid4()),
            "new_entra_oid": str(_uuid.uuid4()),
            "reason": "Operator attempted a stale identity link update.",
        },
    )
    assert stale.status_code == 409
    unchanged = await _user_by_id(test_engine, rows[0].id)
    assert str(unchanged.entra_oid) == str(rows[0].entra_oid)


@pytest.mark.asyncio
async def test_identity_link_rejects_oid_already_bound_to_another_user(
    client: Any, test_engine: Any
) -> None:
    """A target Entra oid can never be linked to two user rows."""
    import uuid as _uuid

    source_email = "jit-link-source-10@example.com"
    target_email = "jit-link-target-10@example.com"
    target_oid = str(_uuid.uuid4())

    source = await client.get(CONTRACTS, headers=_headers("drafter", source_email))
    assert source.status_code == 200
    target = await client.get(CONTRACTS, headers=_headers("drafter", target_email, oid=target_oid))
    assert target.status_code == 200

    source_rows = await _user_rows(test_engine, source_email)
    assert len(source_rows) == 1
    conflict = await client.post(
        f"{USERS}/{source_rows[0].id}/identity-link",
        headers=_headers("admin", "admin-linker-conflict@example.com"),
        json={
            "expected_current_entra_oid": str(source_rows[0].entra_oid),
            "new_entra_oid": target_oid,
            "reason": "Operator attempted to link an oid that is already bound.",
        },
    )
    assert conflict.status_code == 409


@pytest.mark.asyncio
async def test_admin_soft_deletes_user(client: Any, test_engine: Any) -> None:
    """DELETE /users/{id} deactivates and soft-deletes the target row."""
    email = "jit-delete-target-11@example.com"

    first = await client.get(CONTRACTS, headers=_headers("drafter", email))
    assert first.status_code == 200
    rows = await _user_rows(test_engine, email)
    assert len(rows) == 1

    deleted = await client.delete(
        f"{USERS}/{rows[0].id}",
        headers=_headers("admin", "admin-delete@example.com"),
    )
    assert deleted.status_code == 204, deleted.text

    persisted = await _user_by_id(test_engine, rows[0].id)
    assert persisted.is_active is False
    assert persisted.deleted_at is not None


@pytest.mark.asyncio
async def test_admin_cannot_soft_delete_self(client: Any, test_engine: Any) -> None:
    """Self-deletion is fail-closed to avoid locking out the last admin."""
    email = "admin-self-delete-12@example.com"
    headers = _headers("admin", email)

    provision = await client.get(USERS, headers=headers)
    assert provision.status_code == 200
    rows = await _user_rows(test_engine, email)
    assert len(rows) == 1

    deleted = await client.delete(f"{USERS}/{rows[0].id}", headers=headers)
    assert deleted.status_code == 409
