"""Legal-review Pydantic schemas.

Mirrors ``docs/api_design.md`` section 6. The AI structured-output shape is
defined in :class:`AIReviewResult` and stored in ``legal_reviews.result``
(JSONB) so that the column round-trips cleanly through Pydantic.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ReviewStatus, ReviewType, RiskLevel

from .common import ORMModel, TimestampsMixin


class SuggestedAction(BaseModel):
    """An AI-recommended action (counter-proposal, deletion, etc.)."""

    action: Annotated[str, Field(max_length=32)]
    target_clause_seq: Optional[int] = None
    description: str
    replacement_text: Optional[str] = None


class ReviewIssue(BaseModel):
    """Single AI finding tied to a clause within a contract."""

    clause_seq: int
    title: Optional[str] = None
    risk_level: RiskLevel
    comment: str
    suggestion: Optional[str] = None
    citations: List[str] = Field(default_factory=list)
    suggested_actions: List[SuggestedAction] = Field(default_factory=list)


class AIReviewResult(BaseModel):
    """Structured payload produced by the AI worker.

    Stored verbatim in ``legal_reviews.result``. Also returned in the API
    response body as ``findings`` per the design doc example.
    """

    ai_summary: str
    risk_score: Annotated[int, Field(ge=0, le=100)]
    risk_level: RiskLevel
    issues: List[ReviewIssue] = Field(default_factory=list)
    suggested_actions: List[SuggestedAction] = Field(default_factory=list)
    disclaimer: str = (
        "本結果は AI 生成の参考情報であり、最終判断は人間が行ってください。"
    )


class ReviewCreate(BaseModel):
    """Body of ``POST /contracts/{id}/reviews``."""

    review_type: ReviewType = ReviewType.AI
    ai_model: Optional[str] = Field(default=None, max_length=64)
    scope: Annotated[str, Field(pattern="^(full|delta|clause)$")] = "full"
    options: dict[str, Any] = Field(default_factory=dict)


class ReviewRead(ORMModel, TimestampsMixin):
    """Brief view of a review (list endpoints)."""

    id: int
    contract_id: int
    review_type: ReviewType
    status: ReviewStatus
    ai_model: Optional[str] = None
    overall_risk: Optional[RiskLevel] = None
    risk_score: Optional[int] = None
    summary: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    reviewer_id: Optional[int] = None


class ReviewDetail(ReviewRead):
    """Detail view including the structured AI result."""

    ai_input_tokens: Optional[int] = None
    ai_output_tokens: Optional[int] = None
    result: dict[str, Any] = Field(default_factory=dict)
    findings: List[ReviewIssue] = Field(default_factory=list)
    suggested_actions: List[SuggestedAction] = Field(default_factory=list)
    disclaimer: Optional[str] = None


class ReviewActionRequest(BaseModel):
    """Body of ``POST /reviews/{id}/accept|reject``."""

    reason: Optional[str] = Field(default=None, max_length=2000)


class ReviewActionResponse(BaseModel):
    id: int
    status: ReviewStatus
    decided_at: datetime
