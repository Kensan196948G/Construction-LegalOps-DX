"""Unit tests for ``app.services.clause_extractor``.

Covers:
  - Clause dataclass creation
  - ClauseExtractor.extract() — main logic
  - _CLAUSE_HEAD regex pattern matching
  - Various contract text shapes (standard, branch clauses, inline title)
  - LLM enrichment path (mode=llm with mock ai service)
  - Error / edge cases

Target coverage: >= 80% of clause_extractor.py
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.clause_extractor import (
    _CLAUSE_HEAD,
    Clause,
    ClauseExtractor,
)

# ---------------------------------------------------------------------------
# 1. Clause dataclass
# ---------------------------------------------------------------------------


def test_clause_dataclass_defaults() -> None:
    """Arrange/Act: construct Clause with required args. Assert: defaults are set."""
    c = Clause(number="第1条", title="総則", body="本契約は...", start=0, end=100)
    assert c.paragraph_count == 0
    assert c.citations == []
    assert c.metadata == {}


def test_clause_dataclass_fields() -> None:
    """Arrange/Act: construct Clause with all fields. Assert: values retained."""
    c = Clause(
        number="第2条の3",
        title="定義",
        body="以下に定義する。",
        start=10,
        end=50,
        paragraph_count=2,
        citations=["第1条"],
        metadata={"llm_enriched": True},
    )
    assert c.number == "第2条の3"
    assert c.title == "定義"
    assert c.paragraph_count == 2
    assert c.citations == ["第1条"]
    assert c.metadata["llm_enriched"] is True


# ---------------------------------------------------------------------------
# 2. _CLAUSE_HEAD regex
# ---------------------------------------------------------------------------


def test_regex_matches_standard_clause() -> None:
    """Arrange: standard 第X条. Act: findall. Assert: match found."""
    text = "\n第1条 本契約の目的"
    matches = list(_CLAUSE_HEAD.finditer(text))
    assert len(matches) == 1
    assert matches[0].group(1) == "第1条"


def test_regex_matches_branch_clause() -> None:
    """Arrange: branch clause 第X条のY. Act: findall. Assert: match found."""
    text = "\n第3条の2 特例規定"
    matches = list(_CLAUSE_HEAD.finditer(text))
    assert len(matches) == 1
    assert matches[0].group(1) == "第3条の2"


def test_regex_matches_inline_title_in_parens() -> None:
    """Arrange: clause with inline title in parens. Assert: group(2) is captured."""
    text = "\n第5条（損害賠償）賠償の定め"
    matches = list(_CLAUSE_HEAD.finditer(text))
    assert len(matches) == 1
    assert matches[0].group(2) == "損害賠償"


def test_regex_matches_fullwidth_number() -> None:
    """Arrange: fullwidth digits in clause number. Assert: matched."""
    text = "\n第１条 目的"
    matches = list(_CLAUSE_HEAD.finditer(text))
    assert len(matches) == 1
    assert "第" in matches[0].group(1)


def test_regex_matches_kanji_number() -> None:
    """Arrange: kanji number. Assert: matched."""
    text = "\n第一条 定義"
    matches = list(_CLAUSE_HEAD.finditer(text))
    assert len(matches) == 1
    assert matches[0].group(1) == "第一条"


def test_regex_no_match_for_plain_text() -> None:
    """Arrange: text with no clause markers. Assert: no match."""
    text = "これは条項番号のない普通のテキストです。"
    matches = list(_CLAUSE_HEAD.finditer(text))
    assert len(matches) == 0


def test_regex_matches_multiple_clauses() -> None:
    """Arrange: multiple clauses. Assert: correct count."""
    text = "\n第1条 目的\n内容\n第2条 定義\n内容\n第3条 期間\n内容"
    matches = list(_CLAUSE_HEAD.finditer(text))
    assert len(matches) == 3


# ---------------------------------------------------------------------------
# 3. ClauseExtractor.extract() — main logic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_empty_string_returns_empty() -> None:
    """Arrange: empty text. Act: extract. Assert: empty list."""
    extractor = ClauseExtractor()
    result = await extractor.extract("")
    assert result == []


@pytest.mark.asyncio
async def test_extract_whitespace_only_returns_empty() -> None:
    """Arrange: whitespace only. Act: extract. Assert: empty list."""
    extractor = ClauseExtractor()
    result = await extractor.extract("   \n\t  ")
    assert result == []


@pytest.mark.asyncio
async def test_extract_no_clauses_returns_empty() -> None:
    """Arrange: text with no clause markers. Act: extract. Assert: empty list."""
    extractor = ClauseExtractor()
    result = await extractor.extract("本文には条番号がありません。通常のテキストです。")
    assert result == []


@pytest.mark.asyncio
async def test_extract_single_clause() -> None:
    """Arrange: single clause. Act: extract. Assert: one Clause returned."""
    text = "\n第1条\n本契約は甲乙間の合意に基づく。\n"
    extractor = ClauseExtractor()
    result = await extractor.extract(text)
    assert len(result) == 1
    assert result[0].number == "第1条"


@pytest.mark.asyncio
async def test_extract_multiple_clauses_count() -> None:
    """Arrange: 3 clauses. Act: extract. Assert: 3 Clauses returned."""
    text = "\n第1条\n目的に関する規定。\n\n第2条\n定義に関する規定。\n\n第3条\n期間に関する規定。\n"
    extractor = ClauseExtractor()
    result = await extractor.extract(text)
    assert len(result) == 3


@pytest.mark.asyncio
async def test_extract_clause_numbers_correct() -> None:
    """Arrange: multiple clauses. Act: extract. Assert: numbers match source."""
    text = "\n第1条\n内容A。\n\n第2条\n内容B。\n\n第3条\n内容C。\n"
    extractor = ClauseExtractor()
    result = await extractor.extract(text)
    numbers = [c.number for c in result]
    assert numbers == ["第1条", "第2条", "第3条"]


@pytest.mark.asyncio
async def test_extract_clause_body_not_empty() -> None:
    """Arrange: clause with multi-line body (title + body). Act: extract.
    Assert: body is non-empty when a second line follows the title line."""
    # Two-line body: first line becomes title, second line becomes body
    text = "\n第1条\n損害賠償の上限\n詳細な条項内容がここに記載されます。\n"
    extractor = ClauseExtractor()
    result = await extractor.extract(text)
    assert len(result) == 1
    # title is the first line, body is the remainder
    assert len(result[0].title) > 0
    assert len(result[0].body) > 0


@pytest.mark.asyncio
async def test_extract_inline_title_captured() -> None:
    """Arrange: clause with inline paren title. Act: extract. Assert: title set."""
    text = "\n第1条（目的）本契約は甲乙間の合意です。\n第2条\n次の条項。"
    extractor = ClauseExtractor()
    result = await extractor.extract(text)
    assert result[0].title == "目的"


@pytest.mark.asyncio
async def test_extract_heuristic_title_from_first_line() -> None:
    """Arrange: clause without paren title but short first line. Act: extract.
    Assert: first line used as title."""
    text = "\n第1条\n損害賠償の上限\n具体的な内容がここに記載されます。\n第2条\n次。"
    extractor = ClauseExtractor()
    result = await extractor.extract(text)
    # First line "損害賠償の上限" should be used as title (<=40 chars)
    assert result[0].title != "" and result[0].title != "第1条"


@pytest.mark.asyncio
async def test_extract_paragraph_count_set() -> None:
    """Arrange: multi-line body. Act: extract. Assert: paragraph_count > 0."""
    text = "\n第1条\n第一項の内容。\n第二項の内容。\n第三項の内容。\n第2条\n次。"
    extractor = ClauseExtractor()
    result = await extractor.extract(text)
    assert result[0].paragraph_count >= 1


@pytest.mark.asyncio
async def test_extract_branch_clause() -> None:
    """Arrange: branch clause 第X条のY. Act: extract. Assert: branch number captured."""
    text = "\n第3条の2\n特例規定の内容。\n第4条\n次の条項。"
    extractor = ClauseExtractor()
    result = await extractor.extract(text)
    branch = [c for c in result if "の2" in c.number]
    assert len(branch) == 1
    assert branch[0].number == "第3条の2"


@pytest.mark.asyncio
async def test_extract_start_end_positions() -> None:
    """Arrange: two clauses. Act: extract. Assert: start < end for each."""
    text = "\n第1条\n内容A。\n\n第2条\n内容B。\n"
    extractor = ClauseExtractor()
    result = await extractor.extract(text)
    for clause in result:
        assert clause.start < clause.end


@pytest.mark.asyncio
async def test_extract_mode_regex_default() -> None:
    """Arrange: no mode specified. Act: extract. Assert: runs without error (regex mode)."""
    text = "\n第1条\n本契約に定める事項。\n"
    extractor = ClauseExtractor()
    assert extractor._mode == "regex"
    result = await extractor.extract(text)
    assert len(result) >= 1


@pytest.mark.asyncio
async def test_extract_mode_llm_with_ai_service_calls_enrich() -> None:
    """Arrange: mode=llm with mock ai_service. Act: extract. Assert: _llm_enrich called."""
    text = "\n第1条\n条文内容。\n"
    mock_ai = MagicMock()
    extractor = ClauseExtractor(ai_service=mock_ai, mode="llm")
    # Patch _llm_enrich to track calls
    enrich_called = {"count": 0}

    async def mock_enrich(clauses, text):  # type: ignore[misc]
        enrich_called["count"] += 1
        # Set metadata to simulate enrichment
        for c in clauses:
            c.metadata["llm_enriched"] = True

    extractor._llm_enrich = mock_enrich  # type: ignore[method-assign]
    result = await extractor.extract(text)
    assert enrich_called["count"] == 1
    assert result[0].metadata.get("llm_enriched") is True


@pytest.mark.asyncio
async def test_extract_mode_llm_without_ai_service_skips_enrich() -> None:
    """Arrange: mode=llm but ai_service=None. Act: extract.
    Assert: returns clauses without calling llm enrich."""
    text = "\n第1条\n条文内容。\n"
    extractor = ClauseExtractor(ai_service=None, mode="llm")
    result = await extractor.extract(text)
    # Should still return regex results, llm enrichment skipped
    assert len(result) >= 1
    assert result[0].metadata.get("llm_enriched") is not True


@pytest.mark.asyncio
async def test_extract_large_contract_text() -> None:
    """Arrange: realistic multi-clause contract. Act: extract. Assert: all clauses found."""
    text = (
        "\n第1条（目的）\n"
        "本契約は、甲（発注者）と乙（受注者）との間の建設工事請負に関する基本的事項を定めます。\n"
        "\n第2条（定義）\n"
        "本契約において「工事」とは、別紙に定める建設工事をいいます。\n"
        "\n第3条（工期）\n"
        "乙は、着工日から180日以内に工事を完成させます。\n"
        "\n第4条（請負代金）\n"
        "甲は乙に対し、請負代金として金1億円を支払います。\n"
        "\n第5条（損害賠償）\n"
        "損害賠償の範囲は、直接損害に限るものとします。\n"
        "\n第6条（反社会的勢力の排除）\n"
        "甲乙は、反社会的勢力との関係を有しないことを表明します。\n"
    )
    extractor = ClauseExtractor()
    result = await extractor.extract(text)
    assert len(result) == 6
    numbers = [c.number for c in result]
    assert "第1条" in numbers
    assert "第6条" in numbers
