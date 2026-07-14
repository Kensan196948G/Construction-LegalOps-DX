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
            "contract_type": "ukeoi",
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
            "contract_type": "ukeoi",
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
