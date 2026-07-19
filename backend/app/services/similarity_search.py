"""Similar-contract search service.

Uses a lightweight TF-cosine matcher over a caller-supplied corpus. The
production API feeds the corpus from the contracts table; a future vector
index can replace this scorer without changing the public API shape.

The corpus is supplied by the caller (no DB dependency) which keeps the
module pure and unit-testable.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Final


class SimilaritySearchError(RuntimeError):
    """Raised on invalid input to :meth:`SimilaritySearchService.search`."""


@dataclass(slots=True)
class CorpusEntry:
    """A single past contract used as the search corpus."""

    contract_id: str
    title: str
    text: str
    contract_type: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class SimilarityHit:
    """A search result with score."""

    contract_id: str
    title: str
    score: float
    contract_type: str | None
    matched_keywords: list[str]


# Japanese tokens we strip out before scoring (stop-word + punctuation seed).
_NOISE_RE: Final[re.Pattern[str]] = re.compile(
    r"[ 　、。．・「」（）()【】\[\]\n\r\t,．:;'\"]+"
)

_STOP_WORDS: Final[frozenset[str]] = frozenset(
    {
        "及び",
        "並びに",
        "若しくは",
        "又は",
        "において",
        "に関する",
        "及びその他",
        "場合",
        "これ",
        "それ",
        "ため",
        "として",
        "について",
        "する",
        "した",
        "する場合",
        "ある",
        "あり",
        "いる",
        "なお",
        "本",
        "本契約",
    }
)


def _tokenize(text: str) -> list[str]:
    """Naive bi-gram tokenizer + Latin word splitter.

    The bi-gram approach keeps the release candidate dependency-light while
    still surfacing near-duplicates in Japanese contract text.
    """
    cleaned = _NOISE_RE.sub(" ", text)
    tokens: list[str] = []
    for chunk in cleaned.split():
        if chunk.isascii():
            tokens.extend(chunk.lower().split())
            continue
        if len(chunk) < 2:
            continue
        for i in range(len(chunk) - 1):
            bg = chunk[i : i + 2]
            if bg not in _STOP_WORDS:
                tokens.append(bg)
    return tokens


class SimilaritySearchService:
    """TF-cosine-like similarity over an in-memory corpus."""

    def __init__(self, corpus: list[CorpusEntry] | None = None) -> None:
        self._corpus: list[CorpusEntry] = list(corpus or [])
        self._token_cache: dict[str, Counter[str]] = {}

    def index(self, entries: list[CorpusEntry]) -> None:
        """Add or replace corpus entries."""
        self._corpus = list(entries)
        self._token_cache.clear()

    async def search(
        self,
        query_text: str,
        *,
        top_k: int = 5,
        contract_type: str | None = None,
    ) -> list[SimilarityHit]:
        if not query_text or not query_text.strip():
            raise SimilaritySearchError("query_text is required")
        if top_k <= 0:
            raise SimilaritySearchError("top_k must be positive")

        q_counter = Counter(_tokenize(query_text))
        q_norm = math.sqrt(sum(v * v for v in q_counter.values())) or 1.0

        hits: list[SimilarityHit] = []
        for entry in self._corpus:
            if contract_type and entry.contract_type and entry.contract_type != contract_type:
                continue
            counter = self._counter_for(entry)
            if not counter:
                continue
            dot = sum(q_counter[t] * counter.get(t, 0) for t in q_counter)
            if dot == 0:
                continue
            d_norm = math.sqrt(sum(v * v for v in counter.values())) or 1.0
            score = dot / (q_norm * d_norm)
            matched = sorted(
                (t for t in q_counter if t in counter),
                key=lambda t: -q_counter[t] * counter[t],
            )[:5]
            hits.append(
                SimilarityHit(
                    contract_id=entry.contract_id,
                    title=entry.title,
                    score=round(score, 4),
                    contract_type=entry.contract_type,
                    matched_keywords=matched,
                )
            )

        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:top_k]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _counter_for(self, entry: CorpusEntry) -> Counter[str]:
        cached = self._token_cache.get(entry.contract_id)
        if cached is not None:
            return cached
        counter = Counter(_tokenize(entry.text))
        self._token_cache[entry.contract_id] = counter
        return counter
