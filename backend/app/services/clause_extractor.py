"""Clause extractor.

Splits a Japanese contract body into structured clauses using a regex
pre-segmenter and (when ``AI_REVIEW_MODE != "stub"``) an LLM
post-classifier. The LLM step is wired through
:class:`app.services.ai_review.AIReviewService` so the API key, retry
and circuit-breaker policies stay consistent. For Loop 2 the regex
output is sufficient for downstream services.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Final

import structlog

logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class Clause:
    """A single extracted contract clause."""

    number: str  # 例: "第1条", "第2条の3"
    title: str
    body: str
    start: int
    end: int
    paragraph_count: int = 0
    citations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Regex strategy
# ---------------------------------------------------------------------------
#
# Japanese construction contracts almost universally use one of:
#   1.  「第○条」見出し
#   2.  「(○○)\n第○条」見出し（タイトルが前置）
#   3.  「第○条の○」枝番条
#
# The pattern below captures the trigger token; we then split the text
# at each trigger and reconstruct (number, title, body) windows.

_CLAUSE_HEAD: Final[re.Pattern[str]] = re.compile(
    r"(?:^|\n)\s*(第[一二三四五六七八九十百千零〇0-9０-９]+条(?:の[一二三四五六七八九十0-9０-９]+)?)"
    r"[\s　]*(?:[（(]([^）)\n]{1,40})[）)])?",
    flags=re.MULTILINE,
)


class ClauseExtractor:
    """Hybrid regex + LLM clause extractor."""

    def __init__(self, *, ai_service: Any | None = None, mode: str | None = None) -> None:
        self._ai = ai_service
        self._mode = (mode or os.getenv("CLAUSE_EXTRACTOR_MODE", "regex") or "regex").lower()

    async def extract(self, text: str) -> list[Clause]:
        """Return clauses extracted from ``text``."""
        if not text or not text.strip():
            return []
        clauses = self._regex_extract(text)
        if self._mode == "llm" and self._ai is not None and clauses:
            await self._llm_enrich(clauses, text)
        logger.info(
            "clause_extractor.done",
            mode=self._mode,
            clauses=len(clauses),
        )
        return clauses

    # ------------------------------------------------------------------
    # Regex implementation
    # ------------------------------------------------------------------

    def _regex_extract(self, text: str) -> list[Clause]:
        matches = list(_CLAUSE_HEAD.finditer(text))
        if not matches:
            return []

        clauses: list[Clause] = []
        for idx, m in enumerate(matches):
            number = m.group(1).strip()
            inline_title = (m.group(2) or "").strip()
            start = m.start()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            segment = text[m.end() : end].strip()

            title = inline_title
            body = segment
            if not title and segment:
                # Heuristic: first line up to 30 chars or a period is the title.
                first_line = segment.split("\n", 1)[0]
                if 0 < len(first_line) <= 40:
                    title = first_line.strip("。、 :")
                    body = segment[len(first_line) :].lstrip("\n ")

            clauses.append(
                Clause(
                    number=number,
                    title=title or number,
                    body=body,
                    start=start,
                    end=end,
                    paragraph_count=max(1, body.count("\n") + 1) if body else 0,
                )
            )
        return clauses

    # ------------------------------------------------------------------
    # LLM enrichment (Loop 3+)
    # ------------------------------------------------------------------

    async def _llm_enrich(
        self, clauses: list[Clause], text: str
    ) -> None:  # pragma: no cover - integration test only
        """Optional second pass to classify clause categories.

        Implementation deferred: this hook exists so callers can flip
        ``CLAUSE_EXTRACTOR_MODE=llm`` once the prompt template is signed
        off by the legal team.
        """
        for c in clauses:
            c.metadata.setdefault("llm_enriched", False)
