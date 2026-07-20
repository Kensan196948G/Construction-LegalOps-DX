"""User service — database-backed user management helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.schemas.user import UserCreate, UserOut, UserSyncJob, UserUpdate
from app.services._stub import make_stub

_stub = make_stub("user_service")


async def list_users(
    session: AsyncSession,
    *,
    q: str | None = None,
    role: str | None = None,
    department_id: int | None = None,
    is_active: bool | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[UserOut], int]:
    """Return paginated user list."""
    # Eager-load department: UserOut.department would otherwise lazy-load
    # during model_validate and raise MissingGreenlet under async whenever a
    # row has department_id set (Issue #45 Bug 2).
    stmt = select(User).options(selectinload(User.department))

    if q:
        stmt = stmt.where(User.display_name.ilike(f"%{q}%") | User.email.ilike(f"%{q}%"))
    if role:
        stmt = stmt.where(User.role == role)
    if department_id is not None:
        stmt = stmt.where(User.department_id == department_id)
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await session.execute(count_stmt)
    total: int = total_result.scalar_one()

    offset = (page - 1) * size
    stmt = stmt.offset(offset).limit(size)
    result = await session.execute(stmt)
    rows = list(result.scalars().all())
    items = [UserOut.model_validate(r) for r in rows]
    return items, total


async def get_user(session: AsyncSession, *, user_id: int) -> User | None:
    """Return a single active user (department eager-loaded) or None."""
    stmt = (
        select(User)
        .options(selectinload(User.department))
        .where(User.id == user_id, User.deleted_at.is_(None))
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def create_user(session: AsyncSession, *, data: UserCreate) -> User:
    """Create an active user row for emergency admin provisioning."""
    user = User(
        entra_oid=data.entra_oid,
        email=str(data.email),
        display_name=data.display_name,
        department_id=data.department_id,
        role=data.role.value if hasattr(data.role, "value") else str(data.role),
        is_active=data.is_active,
        attributes=data.attributes,
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ValueError("email or Entra oid is already linked to another user") from exc
    await session.refresh(user)
    return user


async def update_user(session: AsyncSession, *, user_id: int, data: UserUpdate) -> User:
    """Patch a user row without automatic identity merging."""
    user = await get_user(session, user_id=user_id)
    if user is None:
        raise LookupError("user not found")
    if data.version is not None:
        # The users table does not carry VersionedMixin today. Reject explicit
        # optimistic-lock tokens instead of pretending that we checked them.
        raise ValueError("users.version optimistic locking is not available")

    fields = data.model_dump(exclude={"version"}, exclude_unset=True)
    for field, value in fields.items():
        if value is None:
            setattr(user, field, None)
            continue
        if field == "role":
            value = value.value if hasattr(value, "value") else str(value)
        setattr(user, field, value)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ValueError("user update conflicts with an existing row") from exc
    await session.refresh(user)
    return user


async def soft_delete_user(
    session: AsyncSession,
    *,
    user_id: int,
    actor_id: int | None,
) -> None:
    """Deactivate and soft-delete a user row."""
    user = await get_user(session, user_id=user_id)
    if user is None:
        raise LookupError("user not found")
    if actor_id is not None and user.id == actor_id:
        raise ValueError("admin users cannot delete their own account")
    now = datetime.now(UTC)
    user.is_active = False
    user.deleted_at = now
    user.updated_at = now
    await session.flush()


async def start_graph_sync(
    session: AsyncSession,
    *,
    triggered_by: int | None,
) -> UserSyncJob:
    """Queue a local Microsoft Graph sync job handle without external writes.

    Production Graph execution is intentionally held behind the #23/#50 human
    gates. This function returns an auditable queued handle and never contacts
    Microsoft Graph by itself.
    """
    _ = session
    queued_at = datetime.now(UTC)
    return UserSyncJob(
        job_id=f"graph-sync-{queued_at.strftime('%Y%m%d%H%M%S')}",
        status="queued",
        triggered_by=triggered_by,
        queued_at=queued_at,
        note=(
            "Queued locally. Production execution requires Microsoft Graph "
            "credentials and worker approval."
        ),
    )


async def link_entra_identity(
    session: AsyncSession,
    *,
    user_id: int,
    expected_current_entra_oid: UUID,
    new_entra_oid: UUID,
    reason: str,
    actor_id: int,
) -> User:
    """Explicitly link an existing user row to a real Entra oid.

    This is the controlled escape hatch for Issue #48. Automatic merging
    remains forbidden in ``get_current_user``; an admin must name the target
    row, prove the currently bound oid, provide a reason, and the new oid
    must not already be bound to another account.
    """
    user = await get_user(session, user_id=user_id)
    if user is None:
        raise LookupError("user not found")
    if str(user.entra_oid) != str(expected_current_entra_oid):
        raise ValueError("current Entra oid does not match the requested source row")
    if str(expected_current_entra_oid) == str(new_entra_oid):
        raise ValueError("new Entra oid is identical to the current oid")

    conflict = (
        await session.execute(
            select(User.id).where(
                User.entra_oid == new_entra_oid,
                User.id != user_id,
                User.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if conflict is not None:
        raise ValueError("new Entra oid is already linked to another user")

    history = list((user.attributes or {}).get("identity_link_history", []))
    history.append(
        {
            "from_entra_oid": str(user.entra_oid),
            "to_entra_oid": str(new_entra_oid),
            "linked_by": actor_id,
            "linked_at": datetime.now(UTC).isoformat(),
            "reason": reason,
        }
    )
    user.attributes = {
        **(user.attributes or {}),
        "identity_link_policy": "admin_explicit_oid_rebind_v1",
        "identity_link_history": history,
    }
    user.entra_oid = new_entra_oid
    await session.flush()
    await session.refresh(user)
    return user


def __getattr__(item: str) -> Any:
    return getattr(_stub, item)
