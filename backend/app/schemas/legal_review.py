"""Legal-review Pydantic schemas.

Mirrors ``docs/api_design.md`` section 6. The AI structured-output shape is
defined in :class:`AIReviewResult` and stored in ``legal_reviews.result``
(JSONB) so that the column round-trips cleanly through Pydantic.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, Field

from app.models.enums import ReviewStatus, ReviewType, RiskLevel

from .common import ORMModel, TimestampsMixin


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


class ReviewActionRequest(BaseModel):
    """Body of ``POST /reviews/{id}/accept|reject``."""

    reason: str | None = Field(default=None, max_length=2000)
    comment: str | None = None


class ReviewActionResponse(BaseModel):
    id: int
    status: ReviewStatus
    decided_at: datetime
