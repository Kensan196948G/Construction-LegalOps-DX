"""Unit tests for app.services.template_service.

Covers:
- list_templates: contract_type/q/is_active filters, pagination
- get_template: found / not found
- list_clauses: ORM-based query with AsyncMock session
- create_clause: ORM insert / flush / refresh
- update_clause: not found / partial update
- create_template: raises NotImplementedError
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.template import (
    ClauseLibraryCreate,
    ClauseLibraryUpdate,
    TemplateCreate,
)
from app.services import template_service

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(role: str = "legal", user_id: int = 1) -> MagicMock:
    user = MagicMock()
    user.role = role
    user.id = user_id
    return user


def _make_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock(return_value=None)
    session.refresh = AsyncMock(return_value=None)
    return session


def _make_clause_orm(
    *,
    id: int = 1,
    code: str = "CL-TEST-001",
    title: str = "テスト条項",
    category: str = "品質保証",
    recommendation: str = "recommended",
    body: str = "条項本文テキスト",
    tags: list[str] | None = None,
    deleted_at: datetime | None = None,
) -> MagicMock:
    c = MagicMock()
    c.id = id
    c.code = code
    c.title = title
    c.category = category
    c.recommendation = recommendation
    c.body = body
    c.tags = tags or []
    c.deleted_at = deleted_at
    c.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    c.updated_at = datetime(2026, 1, 1, tzinfo=UTC)
    return c


# ---------------------------------------------------------------------------
# list_templates() tests
# ---------------------------------------------------------------------------


class TestListTemplates:
    """Tests for template_service.list_templates()."""

    @pytest.mark.asyncio
    async def test_returns_all_templates_by_default(self) -> None:
        """list_templates() returns all seeded templates without filters."""
        session = _make_session()
        items, total = await template_service.list_templates(session)
        assert total == 5
        assert len(items) == 5

    @pytest.mark.asyncio
    async def test_filter_by_contract_type(self) -> None:
        """list_templates() filters by contract_type exactly."""
        session = _make_session()
        items, total = await template_service.list_templates(session, contract_type="請負")
        assert total == 2
        assert all(t.contract_type == "請負" for t in items)

    @pytest.mark.asyncio
    async def test_filter_by_contract_type_itaku(self) -> None:
        """list_templates() returns only 委託 templates when filtered."""
        session = _make_session()
        items, total = await template_service.list_templates(session, contract_type="委託")
        assert total == 1
        assert items[0].contract_type == "委託"

    @pytest.mark.asyncio
    async def test_filter_by_is_active_true(self) -> None:
        """list_templates(is_active=True) returns only active templates."""
        session = _make_session()
        items, total = await template_service.list_templates(session, is_active=True)
        assert total >= 1
        assert all(t.is_active is True for t in items)

    @pytest.mark.asyncio
    async def test_filter_by_is_active_false_returns_empty(self) -> None:
        """list_templates(is_active=False) returns nothing if all templates active."""
        session = _make_session()
        items, total = await template_service.list_templates(session, is_active=False)
        # All seeded templates have is_active=True
        assert total == 0
        assert items == []

    @pytest.mark.asyncio
    async def test_filter_by_q_matches_name(self) -> None:
        """list_templates(q=...) performs case-insensitive name search."""
        session = _make_session()
        items, total = await template_service.list_templates(session, q="秘密保持")
        assert total >= 1
        assert any("秘密保持" in t.name for t in items)

    @pytest.mark.asyncio
    async def test_filter_by_q_matches_description(self) -> None:
        """list_templates(q=...) also searches description field."""
        session = _make_session()
        _items, total = await template_service.list_templates(session, q="建設業法")
        assert total >= 1

    @pytest.mark.asyncio
    async def test_filter_by_q_no_match_returns_empty(self) -> None:
        """list_templates() returns empty for q with no match."""
        session = _make_session()
        items, total = await template_service.list_templates(session, q="存在しないキーワードXYZ")
        assert total == 0
        assert items == []

    @pytest.mark.asyncio
    async def test_pagination_page2(self) -> None:
        """list_templates() respects page/size pagination."""
        session = _make_session()
        items_p1, total_p1 = await template_service.list_templates(session, page=1, size=2)
        items_p2, total_p2 = await template_service.list_templates(session, page=2, size=2)
        assert total_p1 == total_p2 == 5
        assert len(items_p1) == 2
        assert len(items_p2) == 2
        # Pages should not overlap
        ids_p1 = {t.id for t in items_p1}
        ids_p2 = {t.id for t in items_p2}
        assert ids_p1.isdisjoint(ids_p2)

    @pytest.mark.asyncio
    async def test_pagination_last_page(self) -> None:
        """list_templates() returns remaining items on last page."""
        session = _make_session()
        items, total = await template_service.list_templates(session, page=3, size=2)
        assert total == 5
        assert len(items) == 1


# ---------------------------------------------------------------------------
# get_template() tests
# ---------------------------------------------------------------------------


class TestGetTemplate:
    """Tests for template_service.get_template()."""

    @pytest.mark.asyncio
    async def test_get_existing_template(self) -> None:
        """get_template() returns the template for a valid ID."""
        session = _make_session()
        result = await template_service.get_template(session, template_id=1)
        assert result is not None
        assert result.id == 1
        assert result.code == "TMPL-UKEOI-001"

    @pytest.mark.asyncio
    async def test_get_template_not_found_returns_none(self) -> None:
        """get_template() returns None for an unknown ID."""
        session = _make_session()
        result = await template_service.get_template(session, template_id=9999)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_seeded_templates(self) -> None:
        """get_template() resolves each of the 5 seeded template IDs."""
        session = _make_session()
        for template_id in range(1, 6):
            result = await template_service.get_template(session, template_id=template_id)
            assert result is not None, f"template_id={template_id} should exist"


# ---------------------------------------------------------------------------
# create_template() tests
# ---------------------------------------------------------------------------


class TestCreateTemplate:
    """Tests for template_service.create_template()."""

    @pytest.mark.asyncio
    async def test_create_template_raises_not_implemented(self) -> None:
        """create_template() must raise NotImplementedError (no persistent store)."""
        session = _make_session()
        creator = _make_user()
        data = TemplateCreate(
            code="TMPL-NEW-001",
            name="新規テンプレート",
            contract_type="請負",
            body="本文",
        )
        with pytest.raises(NotImplementedError):
            await template_service.create_template(session, data=data, creator=creator)


# ---------------------------------------------------------------------------
# list_clauses() tests
# ---------------------------------------------------------------------------


class TestListClauses:
    """Tests for template_service.list_clauses()."""

    def _setup_session_for_clauses(self, rows: list, count: int | None = None) -> AsyncMock:
        """Build a session mock that returns ``rows`` for clause queries."""
        session = _make_session()

        count_result = MagicMock()
        count_result.scalar.return_value = count if count is not None else len(rows)

        data_result = MagicMock()
        data_result.scalars.return_value.all.return_value = rows

        session.execute = AsyncMock(side_effect=[count_result, data_result])
        return session

    @pytest.mark.asyncio
    async def test_list_clauses_returns_rows(self) -> None:
        """list_clauses() returns ClauseLibraryOut objects from DB rows."""
        clause = _make_clause_orm(id=1, title="瑕疵担保責任条項")
        session = self._setup_session_for_clauses([clause])

        items, total = await template_service.list_clauses(session)

        assert total == 1
        assert len(items) == 1
        assert items[0].id == 1
        assert items[0].title == "瑕疵担保責任条項"
        assert items[0].text == "条項本文テキスト"  # body mapped to text

    @pytest.mark.asyncio
    async def test_list_clauses_empty_result(self) -> None:
        """list_clauses() handles no DB rows gracefully."""
        session = self._setup_session_for_clauses([])

        items, total = await template_service.list_clauses(session)

        assert total == 0
        assert items == []

    @pytest.mark.asyncio
    async def test_list_clauses_tag_filter_in_python(self) -> None:
        """list_clauses() filters by tag in Python after DB fetch."""
        clause_with_tag = _make_clause_orm(id=1, title="タグあり", tags=["瑕疵担保"])
        clause_no_tag = _make_clause_orm(id=2, title="タグなし", tags=[])

        count_result = MagicMock()
        count_result.scalar.return_value = 2

        data_result = MagicMock()
        data_result.scalars.return_value.all.return_value = [
            clause_with_tag,
            clause_no_tag,
        ]

        session = _make_session()
        session.execute = AsyncMock(side_effect=[count_result, data_result])

        items, total = await template_service.list_clauses(session, tag="瑕疵担保")

        assert total == 1
        assert items[0].id == 1

    @pytest.mark.asyncio
    async def test_list_clauses_maps_body_to_text(self) -> None:
        """_clause_to_out() maps ClauseLibrary.body to ClauseLibraryOut.text."""
        clause = _make_clause_orm(id=5, body="詳細な条項本文テキスト内容")
        session = self._setup_session_for_clauses([clause])

        items, _total = await template_service.list_clauses(session)

        assert items[0].text == "詳細な条項本文テキスト内容"


# ---------------------------------------------------------------------------
# create_clause() tests
# ---------------------------------------------------------------------------


class TestCreateClause:
    """Tests for template_service.create_clause()."""

    @pytest.mark.asyncio
    async def test_create_clause_calls_add_flush_refresh(self) -> None:
        """create_clause() calls session.add / flush / refresh."""
        session = _make_session()
        creator = _make_user(role="legal", user_id=3)

        created_at = datetime(2026, 4, 1, tzinfo=UTC)

        async def fake_refresh(obj: object) -> None:
            obj.id = 50  # type: ignore[attr-defined]
            obj.code = "CL-NEW-001"  # type: ignore[attr-defined]
            obj.title = "新条項タイトル"  # type: ignore[attr-defined]
            obj.category = "品質保証"  # type: ignore[attr-defined]
            obj.recommendation = "recommended"  # type: ignore[attr-defined]
            obj.body = "新条項本文"  # type: ignore[attr-defined]
            obj.tags = ["品質", "保証"]  # type: ignore[attr-defined]
            obj.created_at = created_at  # type: ignore[attr-defined]
            obj.updated_at = created_at  # type: ignore[attr-defined]
            obj.deleted_at = None  # type: ignore[attr-defined]

        session.refresh = fake_refresh

        data = ClauseLibraryCreate(
            code="CL-NEW-001",
            title="新条項タイトル",
            category="品質保証",
            recommendation="recommended",
            text="新条項本文",
            tags=["品質", "保証"],
        )

        result = await template_service.create_clause(session, data=data, creator=creator)

        assert session.add.called
        assert result.id == 50
        assert result.title == "新条項タイトル"
        assert result.text == "新条項本文"
        assert result.tags == ["品質", "保証"]

    @pytest.mark.asyncio
    async def test_create_clause_stores_text_as_body(self) -> None:
        """create_clause() stores data.text as ClauseLibrary.body (field mapping)."""
        session = _make_session()
        creator = _make_user()

        captured = None

        def capture_add(obj: object) -> None:
            nonlocal captured
            captured = obj

        session.add = capture_add

        created_at = datetime(2026, 4, 1, tzinfo=UTC)

        async def fake_refresh(obj: object) -> None:
            obj.id = 99  # type: ignore[attr-defined]
            obj.code = "CL-BODY-001"  # type: ignore[attr-defined]
            obj.title = "body/text マッピング確認"  # type: ignore[attr-defined]
            obj.category = "免責"  # type: ignore[attr-defined]
            obj.recommendation = "caution"  # type: ignore[attr-defined]
            obj.body = "免責条項テキスト"  # type: ignore[attr-defined]
            obj.tags = []  # type: ignore[attr-defined]
            obj.created_at = created_at  # type: ignore[attr-defined]
            obj.updated_at = created_at  # type: ignore[attr-defined]
            obj.deleted_at = None  # type: ignore[attr-defined]

        session.refresh = fake_refresh

        data = ClauseLibraryCreate(
            code="CL-BODY-001",
            title="body/text マッピング確認",
            category="免責",
            recommendation="caution",
            text="免責条項テキスト",
        )

        await template_service.create_clause(session, data=data, creator=creator)

        assert captured is not None
        assert captured.body == "免責条項テキスト"


# ---------------------------------------------------------------------------
# update_clause() tests
# ---------------------------------------------------------------------------


class TestUpdateClause:
    """Tests for template_service.update_clause()."""

    @pytest.mark.asyncio
    async def test_update_clause_not_found_raises(self) -> None:
        """update_clause() raises LookupError when clause_id does not exist."""
        session = _make_session()
        editor = _make_user()

        not_found_result = MagicMock()
        not_found_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=not_found_result)

        with pytest.raises(LookupError, match="clause 9999 not found"):
            await template_service.update_clause(
                session,
                clause_id=9999,
                data=ClauseLibraryUpdate(title="新タイトル"),
                editor=editor,
            )

    @pytest.mark.asyncio
    async def test_update_clause_partial_update_title(self) -> None:
        """update_clause() updates only the supplied fields (partial update)."""
        session = _make_session()
        editor = _make_user(role="legal", user_id=2)

        clause = _make_clause_orm(
            id=10, title="元のタイトル", category="品質保証", recommendation="recommended"
        )
        found_result = MagicMock()
        found_result.scalar_one_or_none.return_value = clause
        session.execute = AsyncMock(return_value=found_result)

        async def fake_refresh(obj: object) -> None:
            # Simulate DB refresh after flush
            pass

        session.refresh = fake_refresh

        await template_service.update_clause(
            session,
            clause_id=10,
            data=ClauseLibraryUpdate(title="新しいタイトル"),
            editor=editor,
        )

        assert clause.title == "新しいタイトル"
        assert clause.category == "品質保証"  # unchanged

    @pytest.mark.asyncio
    async def test_update_clause_text_maps_to_body(self) -> None:
        """update_clause() maps ClauseLibraryUpdate.text to ClauseLibrary.body."""
        session = _make_session()
        editor = _make_user()

        clause = _make_clause_orm(id=20, body="旧本文テキスト")
        found_result = MagicMock()
        found_result.scalar_one_or_none.return_value = clause
        session.execute = AsyncMock(return_value=found_result)
        session.refresh = AsyncMock(return_value=None)

        await template_service.update_clause(
            session,
            clause_id=20,
            data=ClauseLibraryUpdate(text="新本文テキスト"),
            editor=editor,
        )

        assert clause.body == "新本文テキスト"

    @pytest.mark.asyncio
    async def test_update_clause_multiple_fields(self) -> None:
        """update_clause() applies all provided fields simultaneously."""
        session = _make_session()
        editor = _make_user()

        clause = _make_clause_orm(
            id=30,
            title="旧タイトル",
            category="旧カテゴリ",
            recommendation="recommended",
            tags=["旧タグ"],
        )
        found_result = MagicMock()
        found_result.scalar_one_or_none.return_value = clause
        session.execute = AsyncMock(return_value=found_result)
        session.refresh = AsyncMock(return_value=None)

        await template_service.update_clause(
            session,
            clause_id=30,
            data=ClauseLibraryUpdate(
                title="新タイトル",
                category="新カテゴリ",
                recommendation="prohibited",
                tags=["新タグ1", "新タグ2"],
            ),
            editor=editor,
        )

        assert clause.title == "新タイトル"
        assert clause.category == "新カテゴリ"
        assert clause.recommendation == "prohibited"
        assert clause.tags == ["新タグ1", "新タグ2"]
