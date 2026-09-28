"""Legal-review Pydantic schemas.

Mirrors ``docs/api_design.md`` section 6. The AI structured-output shape is
defined in :class:`AIReviewResult` and stored in ``legal_reviews.result``
(JSONB) so that the column round-trips cleanly through Pydantic.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Any

import structlog
from pydantic import BaseModel, Field, field_validator

from app.models.enums import ReviewStatus, ReviewType, RiskLevel

from .common import ORMModel, TimestampsMixin

logger = structlog.get_logger(__name__)

# 旧形式 finding（2026-08-01 以前に投入されたデモデータ）は
# ``{"detail", "target", "summary", "severity"}`` を持ち、現行の
# ``ReviewIssue`` が必須とする ``clause_seq`` / ``risk_level`` / ``comment``
# を持たない。``legal_reviews.result``（JSONB）に残っているこの形を読み取り時に
# 正規化する（下の ``_normalize_finding`` / ``ReviewDetail._coerce_findings``）。
# データ側 backfill に依存せず API が 500 を返さないようにするための後方互換層。
_CLAUSE_SEQ_RE = re.compile(r"第\s*([0-9]+)\s*条")
_VALID_RISK_LEVELS: frozenset[str] = frozenset(level.value for level in RiskLevel)


class SuggestedAction(BaseModel):
    """An AI-recommended action (counter-proposal, deletion, etc.)."""

    action: Annotated[str, Field(max_length=32)]
    target_clause_seq: int | None = None
    description: str
    replacement_text: str | None = None


class ReviewIssue(BaseModel):
    """Single AI finding tied to a clause within a contract."""

    clause_seq: int
    title: str | None = None
    risk_level: RiskLevel
    comment: str
    suggestion: str | None = None
    citations: list[str] = Field(default_factory=list)
    # --- v2: 根拠保証（P0-4） ---
    source_page: int | None = None
    clause_number: str | None = None
    excerpt: str | None = None
    law_name: str | None = None
    law_article: str | None = None
    law_version: str | None = None
    effective_date: str | None = None
    primary_source_url: str | None = None
    internal_policy_id: str | None = None
    internal_policy_version: str | None = None
    rule_id: str | None = None
    ai_confidence: float | None = Field(default=None, ge=0, le=1)
    verdict: str = Field(
        default="finding",
        pattern="^(finding|compliant|needs_human_review|unverifiable)$",
    )
    suggested_actions: list[SuggestedAction] = Field(default_factory=list)


def _extract_clause_seq(target: Any) -> int:
    """``target``（例 ``"第3条 契約金額"``）から条番号を取り出す。

    抽出できない場合は ``0`` を返す。``ReviewIssue.clause_seq`` は非負整数で、
    frontend の ``reviewFindingSchema`` も ``nonnegative`` を要求するため
    ``-1`` は使えない。``0`` は「特定の条項に紐付かない指摘」を表す。
    """
    if isinstance(target, int) and not isinstance(target, bool):
        return target
    if isinstance(target, str):
        matched = _CLAUSE_SEQ_RE.search(target)
        if matched is not None:
            return int(matched.group(1))
    return 0


def _normalize_finding(raw: Any) -> dict[str, Any] | None:
    """1 件の finding を ``ReviewIssue`` が検証できる形へ寄せる。

    旧形式キー → 現行キーの対応:

    ==================  ==================
    旧形式              現行
    ==================  ==================
    ``severity``        ``risk_level``
    ``detail``          ``comment``
    ``summary``         ``title``
    ``target``          ``clause_seq``（``第N条`` を抽出。不能なら ``0``）
    ==================  ==================

    現行形式のキーが既にあればそれを優先する（新形式データは無変更で通る）。
    必須項目（``clause_seq`` / ``risk_level`` / ``comment``）を補えない要素、
    および dict でも ``ReviewIssue`` でもない要素は ``None`` を返す。呼び出し側
    （``ReviewDetail._coerce_findings``）がその件数をログに残して読み飛ばす。
    """
    if isinstance(raw, ReviewIssue):
        return raw.model_dump()
    if isinstance(raw, BaseModel):
        raw = raw.model_dump()
    if not isinstance(raw, dict):
        return None

    item: dict[str, Any] = dict(raw)

    if item.get("risk_level") not in _VALID_RISK_LEVELS:
        severity = item.get("severity")
        if isinstance(severity, str) and severity in _VALID_RISK_LEVELS:
            item["risk_level"] = severity

    if not isinstance(item.get("comment"), str):
        detail = item.get("detail")
        if isinstance(detail, str):
            item["comment"] = detail

    if not isinstance(item.get("title"), str):
        summary = item.get("summary")
        if isinstance(summary, str):
            item["title"] = summary

    clause_seq = item.get("clause_seq")
    if not isinstance(clause_seq, int) or isinstance(clause_seq, bool) or clause_seq < 0:
        item["clause_seq"] = _extract_clause_seq(item.get("target"))

    clause_seq = item.get("clause_seq")
    if not isinstance(clause_seq, int) or isinstance(clause_seq, bool) or clause_seq < 0:
        return None
    if item.get("risk_level") not in _VALID_RISK_LEVELS:
        return None
    if not isinstance(item.get("comment"), str):
        return None
    return item


class AIReviewResult(BaseModel):
    """Structured payload produced by the AI worker.

    Stored verbatim in ``legal_reviews.result``. Also returned in the API
    response body as ``findings`` per the design doc example.
    """

    ai_summary: str
    risk_score: Annotated[int, Field(ge=0, le=100)]
    risk_level: RiskLevel
    issues: list[ReviewIssue] = Field(default_factory=list)
    suggested_actions: list[SuggestedAction] = Field(default_factory=list)
    disclaimer: str = "本結果は AI 生成の参考情報であり、最終判断は人間が行ってください。"


class ReviewCreate(BaseModel):
    """Body of ``POST /contracts/{id}/reviews``."""

    review_type: ReviewType = ReviewType.AI
    ai_model: str | None = Field(default=None, max_length=64)
    scope: Annotated[str, Field(pattern="^(full|delta|clause)$")] = "full"
    options: dict[str, Any] = Field(default_factory=dict)


class ReviewRead(ORMModel, TimestampsMixin):
    """Brief view of a review (list endpoints)."""

    id: int
    contract_id: int
    review_type: ReviewType
    status: ReviewStatus
    ai_model: str | None = None
    overall_risk: RiskLevel | None = None
    risk_score: int | None = None
    summary: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    reviewer_id: int | None = None


class ReviewDetail(ReviewRead):
    """Detail view including the structured AI result."""

    ai_input_tokens: int | None = None
    ai_output_tokens: int | None = None
    result: dict[str, Any] = Field(default_factory=dict)
    findings: list[ReviewIssue] = Field(default_factory=list)
    suggested_actions: list[SuggestedAction] = Field(default_factory=list)
    disclaimer: str | None = None

    @field_validator("findings", mode="before")
    @classmethod
    def _coerce_findings(cls, value: Any) -> list[Any]:
        """``findings`` を読み取り時に正規化し、壊れた要素で 500 にしない。

        ``legal_reviews.result`` は JSONB で、スキーマ変更前のデータ
        （旧形式 ``severity`` / ``detail`` / ``summary`` / ``target``）や
        部分的に壊れた要素が残り得る。正規化できない要素は読み飛ばすが、
        **黙って握り潰さない**: 読み飛ばした件数を warning で記録する。
        """
        if value is None:
            return []
        if not isinstance(value, (list, tuple)):
            logger.warning(
                "legal_review.findings.not_a_list",
                value_type=type(value).__name__,
            )
            return []

        normalized: list[Any] = []
        dropped = 0
        for raw in value:
            item = _normalize_finding(raw)
            if item is None:
                dropped += 1
                continue
            normalized.append(item)

        if dropped:
            logger.warning(
                "legal_review.findings.dropped",
                dropped=dropped,
                kept=len(normalized),
            )
        return normalized


class ReviewActionRequest(BaseModel):
    """Body of ``POST /reviews/{id}/accept|reject``."""

    reason: str | None = Field(default=None, max_length=2000)
    comment: str | None = None


class ReviewActionResponse(BaseModel):
    id: int
    status: ReviewStatus
    decided_at: datetime
