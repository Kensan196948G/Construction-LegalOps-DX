"""Unit tests for app.services.legal_rag (一次情報限定コーパス)."""

from __future__ import annotations

from app.services.legal_rag import corpus_search, corpus_stats, load_corpus


class TestCorpus:
    def test_corpus_loads_primary_sources(self) -> None:
        docs = load_corpus()
        assert len(docs) >= 3
        ids = {d.source_id for d in docs}
        assert "toritekihou" in ids
        assert "construction_business_act" in ids
        assert "article19" in ids

    def test_every_document_has_primary_source_url(self) -> None:
        stats = corpus_stats()
        assert stats["document_count"] >= 3
        assert stats["all_have_source_url"] is True

    def test_search_finds_toritekihou_by_terms(self) -> None:
        hits = corpus_search("取適法 支払期日 60日")
        assert hits
        assert hits[0].source_id == "toritekihou"
        assert hits[0].source_url is not None
        assert "jftc.go.jp" in hits[0].source_url

    def test_search_finds_construction_law(self) -> None:
        hits = corpus_search("労務費 内訳 改正建設業法")
        assert hits
        assert hits[0].source_id == "construction_business_act"

    def test_search_unknown_returns_empty(self) -> None:
        assert corpus_search("存在しない法律用語XYZ") == []

    def test_search_empty_query_returns_empty(self) -> None:
        assert corpus_search("") == []
