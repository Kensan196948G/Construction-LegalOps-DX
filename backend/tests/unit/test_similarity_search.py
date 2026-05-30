"""Unit tests for app.services.similarity_search.

Covers the SimilaritySearchService.search() method and edge cases,
targeting the uncovered lines: 93, 110-111, 121, 123, 131, 134, 164
"""

from __future__ import annotations

import pytest

from app.services.similarity_search import (
    CorpusEntry,
    SimilarityHit,
    SimilaritySearchError,
    SimilaritySearchService,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _entry(
    contract_id: str,
    title: str,
    text: str,
    contract_type: str | None = None,
) -> CorpusEntry:
    return CorpusEntry(
        contract_id=contract_id,
        title=title,
        text=text,
        contract_type=contract_type,
    )


_SAMPLE_CORPUS = [
    _entry("c1", "建設工事請負契約", "工事内容 請負代金 工期 引渡 設計変更 不可抗力", "請負"),
    _entry("c2", "業務委託契約", "業務委託 成果物 納品 検収 報告書", "委託"),
    _entry("c3", "秘密保持契約", "秘密情報 開示 目的外使用禁止 返還", "NDA"),
    _entry("c4", "下請工事請負契約", "請負代金 工期 下請 施工体制 引渡", "請負"),
    _entry("c5", "売買契約", "売買 代金 引渡 所有権 瑕疵担保", "売買"),
]


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSearchErrors:
    def setup_method(self) -> None:
        self.svc = SimilaritySearchService(corpus=_SAMPLE_CORPUS)

    async def test_empty_query_raises(self) -> None:
        """Empty string raises SimilaritySearchError (line 121)."""
        with pytest.raises(SimilaritySearchError, match="query_text is required"):
            await self.svc.search("")

    async def test_whitespace_only_query_raises(self) -> None:
        """Whitespace-only query is treated as empty (line 121)."""
        with pytest.raises(SimilaritySearchError, match="query_text is required"):
            await self.svc.search("   ")

    async def test_zero_top_k_raises(self) -> None:
        """top_k=0 raises SimilaritySearchError (line 123)."""
        with pytest.raises(SimilaritySearchError, match="top_k must be positive"):
            await self.svc.search("工事", top_k=0)

    async def test_negative_top_k_raises(self) -> None:
        """Negative top_k raises SimilaritySearchError (line 123)."""
        with pytest.raises(SimilaritySearchError, match="top_k must be positive"):
            await self.svc.search("工事", top_k=-1)


# ---------------------------------------------------------------------------
# Empty corpus
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestEmptyCorpus:
    def setup_method(self) -> None:
        self.svc = SimilaritySearchService()

    async def test_empty_corpus_returns_empty_list(self) -> None:
        """No corpus entries → empty result."""
        results = await self.svc.search("工事内容 請負代金")
        assert results == []

    async def test_empty_corpus_with_top_k_returns_empty(self) -> None:
        results = await self.svc.search("工事", top_k=3)
        assert results == []


# ---------------------------------------------------------------------------
# Results with corpus
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSearchResults:
    def setup_method(self) -> None:
        self.svc = SimilaritySearchService(corpus=_SAMPLE_CORPUS)

    async def test_returns_list_of_similarity_hits(self) -> None:
        results = await self.svc.search("請負代金 工期")
        assert isinstance(results, list)
        assert all(isinstance(h, SimilarityHit) for h in results)

    async def test_results_sorted_by_score_descending(self) -> None:
        results = await self.svc.search("請負代金 工期 引渡")
        scores = [h.score for h in results]
        assert scores == sorted(scores, reverse=True)

    async def test_top_k_limits_result_count(self) -> None:
        """top_k=2 returns at most 2 results even with 5-entry corpus."""
        results = await self.svc.search("契約 工事 業務", top_k=2)
        assert len(results) <= 2

    async def test_top_k_1_returns_single_best(self) -> None:
        results = await self.svc.search("請負代金 工期", top_k=1)
        assert len(results) == 1

    async def test_score_is_between_0_and_1(self) -> None:
        results = await self.svc.search("工事内容 請負代金")
        for hit in results:
            assert 0.0 <= hit.score <= 1.0

    async def test_hit_has_required_fields(self) -> None:
        results = await self.svc.search("請負代金", top_k=1)
        assert len(results) == 1
        h = results[0]
        assert isinstance(h.contract_id, str)
        assert isinstance(h.title, str)
        assert isinstance(h.score, float)
        assert isinstance(h.matched_keywords, list)

    async def test_matched_keywords_are_from_query(self) -> None:
        """matched_keywords contain tokens that appear in both query and document."""
        results = await self.svc.search("請負代金 工期 引渡", top_k=1)
        assert len(results) == 1
        hit = results[0]
        assert len(hit.matched_keywords) > 0

    async def test_unrelated_query_returns_empty(self) -> None:
        """Query with no overlap with any corpus entry returns empty list."""
        # Purely ASCII noise tokens that tokenizer maps to latin words
        results = await self.svc.search("xyz abc def ghi")
        # Score will be 0 for all, so they are filtered out (line 136-137)
        assert results == []

    async def test_contract_type_filter_applied(self) -> None:
        """contract_type filter excludes entries of different type (line 130-131)."""
        results = await self.svc.search("請負代金 工期", contract_type="委託")
        # Only c2 has type '委託'; others are filtered
        for h in results:
            assert h.contract_type == "委託"

    async def test_contract_type_filter_none_entry_excluded(self) -> None:
        """Entries with contract_type set to non-matching value are excluded."""
        corpus = [
            _entry("a1", "NDA", "秘密情報 開示", "NDA"),
            _entry("a2", "工事", "工事内容 請負代金", "請負"),
        ]
        svc = SimilaritySearchService(corpus=corpus)
        results = await svc.search("請負代金 工事内容", contract_type="NDA")
        ids = [h.contract_id for h in results]
        assert "a2" not in ids

    async def test_entry_with_none_contract_type_not_filtered_by_type(self) -> None:
        """Entry with contract_type=None is NOT filtered when contract_type filter is set."""
        corpus = [
            _entry("n1", "一般契約", "工事内容 請負代金 工期", contract_type=None),
        ]
        svc = SimilaritySearchService(corpus=corpus)
        # contract_type=None on entry → condition `entry.contract_type` is falsy → not skipped
        results = await svc.search("工事内容 請負代金", contract_type="請負")
        ids = [h.contract_id for h in results]
        assert "n1" in ids

    async def test_empty_text_entry_is_skipped(self) -> None:
        """Corpus entry with empty text produces empty counter → skipped (line 133-134)."""
        corpus = [
            _entry("empty", "空文書", ""),
            _entry("c1", "工事", "工事内容 請負代金"),
        ]
        svc = SimilaritySearchService(corpus=corpus)
        results = await svc.search("工事内容")
        ids = [h.contract_id for h in results]
        assert "empty" not in ids
        assert "c1" in ids


# ---------------------------------------------------------------------------
# index() and token cache
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestIndex:
    def setup_method(self) -> None:
        self.svc = SimilaritySearchService()

    async def test_index_replaces_corpus(self) -> None:
        """index() replaces the existing corpus (lines 110-111)."""
        old = [_entry("old1", "旧契約", "旧テキスト")]
        self.svc.index(old)
        results_before = await self.svc.search("旧テキスト")
        assert any(h.contract_id == "old1" for h in results_before)

        new = [_entry("new1", "新契約", "新テキスト 新情報")]
        self.svc.index(new)
        results_after = await self.svc.search("旧テキスト")
        ids = [h.contract_id for h in results_after]
        assert "old1" not in ids

    async def test_index_clears_token_cache(self) -> None:
        """index() clears the _token_cache (line 111)."""
        self.svc.index(_SAMPLE_CORPUS)
        # Trigger cache population
        await self.svc.search("請負代金")
        assert len(self.svc._token_cache) > 0

        # Re-index clears cache
        self.svc.index(_SAMPLE_CORPUS[:2])
        assert len(self.svc._token_cache) == 0

    async def test_token_cache_populated_after_search(self) -> None:
        """_counter_for populates the cache on first access (line 164)."""
        self.svc.index(_SAMPLE_CORPUS)
        assert len(self.svc._token_cache) == 0

        await self.svc.search("請負代金 工期")
        # At least one entry should have been cached
        assert len(self.svc._token_cache) > 0

    async def test_token_cache_hit_reuses_counter(self) -> None:
        """Second search reuses the cached counter (line 163 branch)."""
        self.svc.index(_SAMPLE_CORPUS)
        await self.svc.search("請負代金")
        cache_after_first = dict(self.svc._token_cache)

        await self.svc.search("引渡 設計変更")
        # Same entries should remain in cache (no duplicates)
        for key in cache_after_first:
            assert key in self.svc._token_cache
            assert self.svc._token_cache[key] is cache_after_first[key]
