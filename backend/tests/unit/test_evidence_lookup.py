"""Unit tests for app.services.evidence_lookup (一次情報限定 RAG)."""

from __future__ import annotations

import pytest

from app.models.knowledge_article import KnowledgeArticle
from app.services.evidence_lookup import (
    search_primary_sources,
    validate_citation_url,
    verify_citations,
)


class TestCitationValidation:
    def test_accepts_gov_hosts(self) -> None:
        assert validate_citation_url("https://elaws.e-gov.go.jp/document?lawid=324AC0000000100")
        assert validate_citation_url("https://www.jftc.go.jp/partnership_package/toritekihou.html")
        assert validate_citation_url("https://www.mlit.go.jp/totikensangyo/const/content/001979929.pdf")
        assert validate_citation_url("https://www.ppc.go.jp/legal/policy/")

    def test_rejects_unknown_hosts_and_none(self) -> None:
        assert validate_citation_url(None) is False
        assert validate_citation_url("") is False
        assert validate_citation_url("https://example.com/foo") is False
        assert validate_citation_url("javascript:alert(1)") is False

    @pytest.mark.asyncio
    async def test_verify_citations_counts(self, db_session) -> None:
        result = await verify_citations(
            db_session,
            urls=[
                "https://www.jftc.go.jp/partnership_package/toritekihou.html",
                "https://example.com/evil",
                None,
            ]
        )
        assert result["total"] == 3
        assert result["valid"] == 1
        assert result["invalid"] == 1
        assert result["invalid_urls"] == ["https://example.com/evil"]


class TestSearchPrimarySources:
    @pytest.mark.asyncio
    async def test_returns_knowledge_hits_and_corpus_fallback(
        self, db_session
    ) -> None:
        session = db_session
        article = KnowledgeArticle(
            title="取適法の適用判定",
            body="取適法は2026年1月1日施行。支払期日は受領日から60日以内。",
            tags=["取適法"],
            citations=["https://www.jftc.go.jp/partnership_package/toritekihou.html"],
        )
        session.add(article)
        await session.flush()

        hits = await search_primary_sources(session, query="取適法 支払期日", limit=4)
        assert hits
        assert hits[0].article_id == article.id
        assert hits[0].source_kind == "knowledge"
        assert hits[0].to_dict()["source_verified"] is True

    @pytest.mark.asyncio
    async def test_corpus_fallback_when_no_articles(self, db_session) -> None:
        hits = await search_primary_sources(
            db_session, query="取適法 60日 支払", limit=4
        )
        assert hits
        # No DB rows → the local corpus supplies the evidence.
        assert all(h.source_kind == "corpus" for h in hits)
        assert hits[0].source_url is not None
        assert "jftc.go.jp" in hits[0].source_url

    @pytest.mark.asyncio
    async def test_empty_query_returns_empty(self, db_session) -> None:
        assert await search_primary_sources(db_session, query="") == []
