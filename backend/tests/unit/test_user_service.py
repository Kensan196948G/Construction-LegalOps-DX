"""Unit tests for ``app.services.user_service.list_users``.

``user_service`` implements:
  - ``list_users(session, *, q, role, department_id, is_active, page, size)``
    → tuple[list[UserOut], int]

``get_user_by_id``, ``get_user_by_sub``, ``create_or_update_user`` are
currently delegated to the _stub (returns HTTP 501), so we verify the stub
delegation behaviour rather than full business logic.

Target coverage: >= 90 % of user_service.py
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import user_service

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session() -> AsyncMock:
    """Return a minimal async-compatible SQLAlchemy session mock."""
    session = AsyncMock()
    return session


def _make_user_row(
    *,
    id: int = 1,
    email: str = "alice@example.com",
    display_name: str = "Alice",
    role: str = "reviewer",
    is_active: bool = True,
    department_id: int | None = None,
) -> MagicMock:
    """Build a minimal User-like MagicMock accepted by UserOut.model_validate."""
    user = MagicMock()
    user.id = id
    user.email = email
    user.display_name = display_name
    user.role = role
    user.is_active = is_active
    user.department_id = department_id
    user.department = None
    user.entra_oid = "00000000-0000-0000-0000-000000000001"
    user.last_login_at = None
    user.attributes = {}
    user.created_at = None
    user.updated_at = None
    user.deleted_at = None
    return user


# ---------------------------------------------------------------------------
# list_users — empty result
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_users_empty_returns_empty_list_and_zero() -> None:
    """Arrange: DB returns 0 rows. Act: list_users. Assert: ([], 0)."""
    # Arrange
    session = _make_session()
    # count query returns 0
    count_result = MagicMock()
    count_result.scalar_one.return_value = 0
    # rows query returns empty
    rows_result = MagicMock()
    rows_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(side_effect=[count_result, rows_result])

    # Act
    items, total = await user_service.list_users(session)

    # Assert
    assert items == []
    assert total == 0


# ---------------------------------------------------------------------------
# list_users — with data
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_users_returns_mapped_user_out() -> None:
    """Arrange: DB returns 1 user row. Act: list_users. Assert: list has UserOut."""
    from app.schemas.user import UserOut

    # Arrange
    session = _make_session()
    user_row = _make_user_row()

    count_result = MagicMock()
    count_result.scalar_one.return_value = 1
    rows_result = MagicMock()
    rows_result.scalars.return_value.all.return_value = [user_row]

    session.execute = AsyncMock(side_effect=[count_result, rows_result])

    # We need model_validate to succeed — patch it to return a MagicMock UserOut
    with patch.object(UserOut, "model_validate", side_effect=lambda r: MagicMock(spec=UserOut)):
        items, total = await user_service.list_users(session)

    # Assert
    assert total == 1
    assert len(items) == 1


# ---------------------------------------------------------------------------
# list_users — role filter (covers line 35: stmt = stmt.where(User.role == role))
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_users_with_role_filter() -> None:
    """Arrange: role='admin'. Act: list_users. Assert: query executed, total returned."""
    # Arrange
    session = _make_session()

    count_result = MagicMock()
    count_result.scalar_one.return_value = 2
    rows_result = MagicMock()
    rows_result.scalars.return_value.all.return_value = []

    session.execute = AsyncMock(side_effect=[count_result, rows_result])

    # Act
    _items, total = await user_service.list_users(session, role="admin")

    # Assert
    assert total == 2
    assert session.execute.call_count == 2


# ---------------------------------------------------------------------------
# list_users — department_id filter (covers line 37)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_users_with_department_id_filter() -> None:
    """Arrange: department_id=10. Act: list_users. Assert: query executed."""
    # Arrange
    session = _make_session()

    count_result = MagicMock()
    count_result.scalar_one.return_value = 0
    rows_result = MagicMock()
    rows_result.scalars.return_value.all.return_value = []

    session.execute = AsyncMock(side_effect=[count_result, rows_result])

    # Act
    items, total = await user_service.list_users(session, department_id=10)

    # Assert
    assert total == 0
    assert items == []


# ---------------------------------------------------------------------------
# list_users — is_active filter (covers line 39)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_users_with_is_active_false_filter() -> None:
    """Arrange: is_active=False. Act: list_users. Assert: query executed."""
    # Arrange
    session = _make_session()

    count_result = MagicMock()
    count_result.scalar_one.return_value = 0
    rows_result = MagicMock()
    rows_result.scalars.return_value.all.return_value = []

    session.execute = AsyncMock(side_effect=[count_result, rows_result])

    # Act
    _items, total = await user_service.list_users(session, is_active=False)

    # Assert
    assert total == 0


# ---------------------------------------------------------------------------
# list_users — text search filter q (covers line 31)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_users_with_search_query() -> None:
    """Arrange: q='alice'. Act: list_users. Assert: query executed successfully."""
    # Arrange
    session = _make_session()

    count_result = MagicMock()
    count_result.scalar_one.return_value = 0
    rows_result = MagicMock()
    rows_result.scalars.return_value.all.return_value = []

    session.execute = AsyncMock(side_effect=[count_result, rows_result])

    # Act
    _items, total = await user_service.list_users(session, q="alice")

    # Assert
    assert total == 0


# ---------------------------------------------------------------------------
# list_users — pagination (covers lines 43-50)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_users_pagination_page2() -> None:
    """Arrange: page=2, size=5. Act: list_users. Assert: returns correct total."""
    # Arrange
    session = _make_session()

    count_result = MagicMock()
    count_result.scalar_one.return_value = 12
    rows_result = MagicMock()
    rows_result.scalars.return_value.all.return_value = []

    session.execute = AsyncMock(side_effect=[count_result, rows_result])

    # Act
    items, total = await user_service.list_users(session, page=2, size=5)

    # Assert
    assert total == 12
    assert items == []


# ---------------------------------------------------------------------------
# list_users — multiple rows with model_validate (covers line 54)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_users_multiple_rows_converted() -> None:
    """Arrange: 3 user rows. Act: list_users. Assert: all converted to UserOut."""
    from app.schemas.user import UserOut

    # Arrange
    session = _make_session()
    rows = [_make_user_row(id=i, email=f"user{i}@example.com") for i in range(1, 4)]

    count_result = MagicMock()
    count_result.scalar_one.return_value = 3
    rows_result = MagicMock()
    rows_result.scalars.return_value.all.return_value = rows

    session.execute = AsyncMock(side_effect=[count_result, rows_result])

    mock_out = MagicMock(spec=UserOut)
    with patch.object(UserOut, "model_validate", return_value=mock_out):
        items, total = await user_service.list_users(session)

    # Assert
    assert total == 3
    assert len(items) == 3


# ---------------------------------------------------------------------------
# list_users — all filters combined
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_users_all_filters_combined() -> None:
    """Arrange: all filters set. Act: list_users. Assert: executes without error."""
    # Arrange
    session = _make_session()

    count_result = MagicMock()
    count_result.scalar_one.return_value = 0
    rows_result = MagicMock()
    rows_result.scalars.return_value.all.return_value = []

    session.execute = AsyncMock(side_effect=[count_result, rows_result])

    # Act
    items, total = await user_service.list_users(
        session,
        q="ken",
        role="reviewer",
        department_id=5,
        is_active=True,
        page=1,
        size=10,
    )

    # Assert
    assert isinstance(total, int)
    assert isinstance(items, list)


# ---------------------------------------------------------------------------
# __getattr__ stub delegation (covers line 57-58: __getattr__ + _stub)
# ---------------------------------------------------------------------------


def test_getattr_unknown_returns_stub_coroutine() -> None:
    """Arrange: access unknown attr via __getattr__. Act. Assert: callable."""
    # Act — module __getattr__ delegates to _stub
    fn = user_service.__getattr__("get_user_by_id")  # type: ignore[attr-defined]
    # Assert
    assert fn is not None
    assert callable(fn)


def test_getattr_get_user_by_sub_is_callable() -> None:
    """Arrange: access get_user_by_sub via __getattr__. Act. Assert: callable."""
    # Act
    fn = user_service.__getattr__("get_user_by_sub")  # type: ignore[attr-defined]
    # Assert
    assert fn is not None
    assert callable(fn)


def test_getattr_create_or_update_user_is_callable() -> None:
    """Arrange: access create_or_update_user via __getattr__. Act. Assert: callable."""
    # Act
    fn = user_service.__getattr__("create_or_update_user")  # type: ignore[attr-defined]
    # Assert
    assert fn is not None
    assert callable(fn)


# ---------------------------------------------------------------------------
# stub functions raise HTTP 501 when awaited
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_user_by_id_stub_raises_501() -> None:
    """Arrange: stub get_user_by_id. Act: await. Assert: HTTPException 501."""
    from fastapi import HTTPException

    fn = user_service.__getattr__("get_user_by_id")  # type: ignore[attr-defined]
    with pytest.raises(HTTPException) as exc_info:
        await fn(session=None, user_id=1)
    assert exc_info.value.status_code == 501


@pytest.mark.asyncio
async def test_get_user_by_sub_stub_raises_501() -> None:
    """Arrange: stub get_user_by_sub. Act: await. Assert: HTTPException 501."""
    from fastapi import HTTPException

    fn = user_service.__getattr__("get_user_by_sub")  # type: ignore[attr-defined]
    with pytest.raises(HTTPException) as exc_info:
        await fn(session=None, sub="some-sub")
    assert exc_info.value.status_code == 501


@pytest.mark.asyncio
async def test_create_or_update_user_stub_raises_501() -> None:
    """Arrange: stub create_or_update_user. Act: await. Assert: HTTPException 501."""
    from fastapi import HTTPException

    fn = user_service.__getattr__("create_or_update_user")  # type: ignore[attr-defined]
    with pytest.raises(HTTPException) as exc_info:
        await fn(session=None)
    assert exc_info.value.status_code == 501
