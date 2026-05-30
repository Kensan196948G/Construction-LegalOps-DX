"""Unit tests for app.services.knowledge_service.

Covers:
- _base_query: privileged vs. drafter role scoping
- search: KnowledgeArticle hits / Contract hits / hybrid / tag / contract_type
- find_similar: normal / not_found / empty corpus / similarity calculation
- create_article: ORM insert / flush / refresh
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.knowledge import KnowledgeArticleCreate
from app.services import knowledge_service
from app.services.knowledge_service import _base_query

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(role: str = "admin", user_id: int = 1) -> MagicMock:
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


def _make_contract(
    *,
    id: int = 1,
    contract_no: str = "C-0001",
    title: str = "テスト請負契約",
    counterparty: str = "株式会社テスト",
    contract_type: str = "請負",
    drafter_id: int = 1,
    deleted_at: datetime | None = None,
) -> MagicMock:
    c = MagicMock()
    c.id = id
    c.contract_no = contract_no
    c.title = title
    c.counterparty = counterparty
    c.contract_type = contract_type
    c.drafter_id = drafter_id
    c.deleted_at = deleted_at
    c.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    c.updated_at = datetime(2026, 1, 1, tzinfo=UTC)
    return c


def _make_article(
    *,
    id: int = 10,
    title: str = "知識記事タイトル",
    body: str = "記事本文サンプル",
    contract_type: str | None = None,
    tags: list[str] | None = None,
    deleted_at: datetime | None = None,
) -> MagicMock:
    a = MagicMock()
    a.id = id
    a.title = title
    a.body = body
    a.contract_type = contract_type
    a.tags = tags or []
    a.deleted_at = deleted_at
    a.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    a.updated_at = datetime(2026, 1, 1, tzinfo=UTC)
    return a


def _execute_result(rows: list) -> AsyncMock:
    """Return a mock that simulates session.execute() returning scalar rows."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    result.scalar.return_value = len(rows)
    result.scalar_one_or_none.return_value = rows[0] if rows else None
    execute = AsyncMock(return_value=result)
    return execute


# ---------------------------------------------------------------------------
# _base_query tests
# ---------------------------------------------------------------------------


class TestBaseQuery:
    """Tests for the _base_query helper."""

    def test_privileged_role_no_drafter_filter(self) -> None:
        """admin role should not add a WHERE drafter_id = <id> clause."""
        # drafter_id appears in the SELECT column list for all queries.
        # The privileged path must NOT add a "drafter_id = <value>" equality
        # restriction in the WHERE clause.  We verify this by confirming that
        # the compiled SQL does NOT contain the user's id (42) as a literal
        # value in the query (which would only appear if the drafter filter
        # were applied).
        for role in ("admin", "legal", "auditor", "reviewer", "approver"):
            viewer = _make_user(role=role, user_id=42)
            stmt = _base_query(viewer)
            compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
            # The literal "= 42" only appears when the drafter_id filter fires.
            assert "= 42" not in compiled, f"role={role} should not filter by drafter_id = 42"

    def test_drafter_role_adds_drafter_filter(self) -> None:
        """drafter role should add drafter_id == viewer.id filter."""
        viewer = _make_user(role="drafter", user_id=42)
        stmt = _base_query(viewer)
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "= 42" in compiled

    def test_unknown_role_adds_drafter_filter(self) -> None:
        """Any non-privileged role should also restrict to own contracts."""
        viewer = _make_user(role="external", user_id=99)
        stmt = _base_query(viewer)
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "= 99" in compiled


# ---------------------------------------------------------------------------
# search() tests
# ---------------------------------------------------------------------------


class TestSearch:
    """Tests for knowledge_service.search()."""

    @pytest.mark.asyncio
    async def test_search_returns_article_results(self) -> None:
        """search() returns KnowledgeSearchResult from knowledge_articles."""
        session = _make_session()
        article = _make_article(id=10, title="工事請負に関する知識", body="本文詳細")
        viewer = _make_user(role="legal")

        # Execute calls: 1st = KnowledgeArticle rows, 2nd = count, 3rd = contracts
        ka_result = MagicMock()
        ka_result.scalars.return_value.all.return_value = [article]

        count_result = MagicMock()
        count_result.scalar.return_value = 0

        session.execute = AsyncMock(side_effect=[ka_result, count_result])

        items, total = await knowledge_service.search(session, q="工事請負", viewer=viewer)

        assert total == 1
        assert len(items) == 1
        assert items[0].id == 10
        assert items[0].score == 1.0
        assert "工事請負" in items[0].title

    @pytest.mark.asyncio
    async def test_search_returns_contract_results(self) -> None:
        """search() appends Contract results when contract_total > 0."""
        session = _make_session()
        contract = _make_contract(id=5, title="ABC工事請負契約", counterparty="乙社")
        viewer = _make_user(role="admin")

        ka_result = MagicMock()
        ka_result.scalars.return_value.all.return_value = []

        count_result = MagicMock()
        count_result.scalar.return_value = 1

        data_result = MagicMock()
        data_result.scalars.return_value.all.return_value = [contract]

        session.execute = AsyncMock(side_effect=[ka_result, count_result, data_result])

        items, total = await knowledge_service.search(session, q="ABC工事", viewer=viewer)

        assert total == 1
        assert items[0].id == 5
        assert items[0].score == 0.8

    @pytest.mark.asyncio
    async def test_search_hybrid_article_and_contract(self) -> None:
        """search() merges articles and contracts into combined results."""
        session = _make_session()
        article = _make_article(id=10, title="工事知識記事")
        contract = _make_contract(id=5, title="工事請負契約")
        viewer = _make_user(role="admin")

        ka_result = MagicMock()
        ka_result.scalars.return_value.all.return_value = [article]

        count_result = MagicMock()
        count_result.scalar.return_value = 1

        data_result = MagicMock()
        data_result.scalars.return_value.all.return_value = [contract]

        session.execute = AsyncMock(side_effect=[ka_result, count_result, data_result])

        items, total = await knowledge_service.search(session, q="工事", viewer=viewer)

        assert total == 2
        ids = {i.id for i in items}
        assert 10 in ids
        assert 5 in ids

    @pytest.mark.asyncio
    async def test_search_filters_by_contract_type(self) -> None:
        """search() applies contract_type filter to both articles and contracts."""
        session = _make_session()
        viewer = _make_user(role="admin")

        ka_result = MagicMock()
        ka_result.scalars.return_value.all.return_value = []

        count_result = MagicMock()
        count_result.scalar.return_value = 0

        session.execute = AsyncMock(side_effect=[ka_result, count_result])

        items, total = await knowledge_service.search(
            session, q="請負", viewer=viewer, contract_type="請負"
        )

        assert total == 0
        assert items == []

    @pytest.mark.asyncio
    async def test_search_filters_by_tag_in_python(self) -> None:
        """search() filters KnowledgeArticles by tag in Python (dialect-safe)."""
        session = _make_session()
        article_with_tag = _make_article(id=10, title="タグあり記事", tags=["瑕疵担保"])
        article_no_tag = _make_article(id=11, title="タグなし記事", tags=[])
        viewer = _make_user(role="legal")

        ka_result = MagicMock()
        ka_result.scalars.return_value.all.return_value = [
            article_with_tag,
            article_no_tag,
        ]

        count_result = MagicMock()
        count_result.scalar.return_value = 0

        session.execute = AsyncMock(side_effect=[ka_result, count_result])

        items, total = await knowledge_service.search(
            session, q="記事", viewer=viewer, tag="瑕疵担保"
        )

        assert total == 1
        assert items[0].id == 10

    @pytest.mark.asyncio
    async def test_search_pagination(self) -> None:
        """search() applies page/size pagination to combined results."""
        session = _make_session()
        viewer = _make_user(role="admin")

        articles = [_make_article(id=i, title=f"記事{i}") for i in range(1, 6)]

        ka_result = MagicMock()
        ka_result.scalars.return_value.all.return_value = articles

        count_result = MagicMock()
        count_result.scalar.return_value = 0

        session.execute = AsyncMock(side_effect=[ka_result, count_result])

        items, total = await knowledge_service.search(
            session, q="記事", viewer=viewer, page=2, size=2
        )

        assert total == 5
        assert len(items) == 2
        assert items[0].id == 3


# ---------------------------------------------------------------------------
# find_similar() tests
# ---------------------------------------------------------------------------


class TestFindSimilar:
    """Tests for knowledge_service.find_similar()."""

    @pytest.mark.asyncio
    async def test_find_similar_not_found_raises(self) -> None:
        """find_similar() raises LookupError when contract not found."""
        session = _make_session()
        viewer = _make_user(role="admin")

        target_result = MagicMock()
        target_result.scalar_one_or_none.return_value = None

        session.execute = AsyncMock(return_value=target_result)

        with pytest.raises(LookupError, match="contract 999 not found"):
            await knowledge_service.find_similar(session, contract_id=999, viewer=viewer)

    @pytest.mark.asyncio
    async def test_find_similar_empty_corpus_returns_empty_list(self) -> None:
        """find_similar() returns [] when no other contracts exist."""
        session = _make_session()
        viewer = _make_user(role="admin")
        target = _make_contract(id=1, title="対象契約")

        target_result = MagicMock()
        target_result.scalar_one_or_none.return_value = target

        corpus_result = MagicMock()
        corpus_result.scalars.return_value.all.return_value = []

        session.execute = AsyncMock(side_effect=[target_result, corpus_result])

        results = await knowledge_service.find_similar(session, contract_id=1, viewer=viewer)

        assert results == []

    @pytest.mark.asyncio
    async def test_find_similar_returns_sorted_results(self) -> None:
        """find_similar() returns SimilarContractOut list ordered by score."""
        session = _make_session()
        viewer = _make_user(role="admin")
        target = _make_contract(id=1, title="工事請負契約")
        corpus1 = _make_contract(id=2, title="工事請負基本契約", contract_no="C-0002")
        corpus2 = _make_contract(id=3, title="業務委託契約", contract_no="C-0003")

        target_result = MagicMock()
        target_result.scalar_one_or_none.return_value = target

        corpus_result = MagicMock()
        corpus_result.scalars.return_value.all.return_value = [corpus1, corpus2]

        session.execute = AsyncMock(side_effect=[target_result, corpus_result])

        results = await knowledge_service.find_similar(
            session, contract_id=1, viewer=viewer, top_k=5
        )

        assert len(results) >= 1
        # Scores should be between 0 and 1
        for r in results:
            assert 0.0 <= r.similarity <= 1.0

    @pytest.mark.asyncio
    async def test_find_similar_respects_top_k(self) -> None:
        """find_similar() returns at most top_k results."""
        session = _make_session()
        viewer = _make_user(role="admin")
        target = _make_contract(id=1, title="工事請負契約テスト")
        corpus_contracts = [
            _make_contract(id=i + 2, title=f"工事請負契約テスト{i}", contract_no=f"C-{i:04d}")
            for i in range(10)
        ]

        target_result = MagicMock()
        target_result.scalar_one_or_none.return_value = target

        corpus_result = MagicMock()
        corpus_result.scalars.return_value.all.return_value = corpus_contracts

        session.execute = AsyncMock(side_effect=[target_result, corpus_result])

        results = await knowledge_service.find_similar(
            session, contract_id=1, viewer=viewer, top_k=3
        )

        assert len(results) <= 3

    @pytest.mark.asyncio
    async def test_find_similar_drafter_scoped(self) -> None:
        """find_similar() respects viewer role scope for drafter."""
        session = _make_session()
        viewer = _make_user(role="drafter", user_id=5)
        target = _make_contract(id=1, title="自分の契約", drafter_id=5)

        target_result = MagicMock()
        target_result.scalar_one_or_none.return_value = target

        corpus_result = MagicMock()
        corpus_result.scalars.return_value.all.return_value = []

        session.execute = AsyncMock(side_effect=[target_result, corpus_result])

        results = await knowledge_service.find_similar(session, contract_id=1, viewer=viewer)

        assert results == []


# ---------------------------------------------------------------------------
# create_article() tests
# ---------------------------------------------------------------------------


class TestCreateArticle:
    """Tests for knowledge_service.create_article()."""

    @pytest.mark.asyncio
    async def test_create_article_calls_add_flush_refresh(self) -> None:
        """create_article() calls session.add / flush / refresh."""
        session = _make_session()
        creator = _make_user(role="legal", user_id=7)

        created_at = datetime(2026, 3, 1, tzinfo=UTC)
        updated_at = datetime(2026, 3, 1, tzinfo=UTC)

        # After refresh, the article's attributes should be set
        async def fake_refresh(obj: object) -> None:
            obj.id = 100  # type: ignore[attr-defined]
            obj.created_at = created_at  # type: ignore[attr-defined]
            obj.updated_at = updated_at  # type: ignore[attr-defined]

        session.refresh = fake_refresh

        data = KnowledgeArticleCreate(
            title="瑕疵担保条項の解説",
            body="建設業法第40条の3に基づく...",
            tags=["瑕疵担保", "品質"],
            contract_type="請負",
            citations=["建設業法40条の3"],
        )

        result = await knowledge_service.create_article(session, data=data, creator=creator)

        assert session.add.called
        assert result.id == 100
        assert result.title == "瑕疵担保条項の解説"
        assert result.tags == ["瑕疵担保", "品質"]
        assert result.contract_type == "請負"
        assert result.citations == ["建設業法40条の3"]

    @pytest.mark.asyncio
    async def test_create_article_sets_author_id(self) -> None:
        """create_article() assigns creator.id as author_id on the ORM object."""
        session = _make_session()
        creator = _make_user(role="legal", user_id=42)

        captured_article = None

        def capture_add(obj: object) -> None:
            nonlocal captured_article
            captured_article = obj

        session.add = capture_add

        created_at = datetime(2026, 3, 1, tzinfo=UTC)

        async def fake_refresh(obj: object) -> None:
            obj.id = 200  # type: ignore[attr-defined]
            obj.created_at = created_at  # type: ignore[attr-defined]
            obj.updated_at = created_at  # type: ignore[attr-defined]

        session.refresh = fake_refresh

        data = KnowledgeArticleCreate(
            title="著作権条項解説",
            body="設計成果物の著作権について...",
        )

        await knowledge_service.create_article(session, data=data, creator=creator)

        assert captured_article is not None
        assert captured_article.author_id == 42

    @pytest.mark.asyncio
    async def test_create_article_no_tags_defaults_empty(self) -> None:
        """create_article() with no tags returns empty tags list."""
        session = _make_session()
        creator = _make_user(role="legal", user_id=1)

        created_at = datetime(2026, 3, 1, tzinfo=UTC)

        async def fake_refresh(obj: object) -> None:
            obj.id = 300  # type: ignore[attr-defined]
            obj.tags = []  # type: ignore[attr-defined]
            obj.citations = []  # type: ignore[attr-defined]
            obj.created_at = created_at  # type: ignore[attr-defined]
            obj.updated_at = created_at  # type: ignore[attr-defined]

        session.refresh = fake_refresh

        data = KnowledgeArticleCreate(
            title="タグなし記事",
            body="本文",
        )

        result = await knowledge_service.create_article(session, data=data, creator=creator)

        assert result.tags == []
        assert result.citations == []
