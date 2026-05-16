"""User service — minimal list implementation with stub fallback."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import UserOut
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
    stmt = select(User)

    if q:
        stmt = stmt.where(
            User.display_name.ilike(f"%{q}%") | User.email.ilike(f"%{q}%")
        )
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


def __getattr__(item: str) -> Any:
    return getattr(_stub, item)
