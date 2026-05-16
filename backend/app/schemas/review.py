"""AI review Pydantic schemas (v1 API surface).

Thin re-export layer on top of :mod:`app.schemas.legal_review` so the
public API uses the friendlier ``Review*`` naming required by
``docs/api_design.md`` section 6. The underlying validation logic and
``disclaimer`` defaults live in :mod:`legal_review` to avoid drift.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import ReviewStatus

from .legal_review import (
    AIReviewResult,
    ReviewActionRequest,
    ReviewCreate,
    ReviewDetail,
    ReviewIssue,
    ReviewRead,
    SuggestedAction,
)

# ---------------------------------------------------------------------------
# Public-API aliases
# ---------------------------------------------------------------------------


class ReviewOut(ReviewDetail):
    """``GET /reviews/{id}`` and list rows.

    Inherits the full ``ReviewDetail`` shape (incl. ``disclaimer``) so the
    "最終判断は法務担当者・顧問弁護士" guard rail is always present.
    """


class ReviewStartRequest(ReviewCreate):
    """``POST /contracts/{id}/reviews`` body."""


class ReviewStartResponse(BaseModel):
    """Async-accept envelope for ``POST /contracts/{id}/reviews``."""

    review_id: int
    contract_id: int
    status: ReviewStatus = ReviewStatus.PENDING
    accepted_at: datetime
    disclaimer: str = (
        "本 AI レビュー結果は参考情報であり、最終判断は法務担当者および"
        "顧問弁護士が行ってください。"
    )


class ReviewUpdate(BaseModel):
    """``PATCH /reviews/{id}`` — legal annotator overrides."""

    final_decision: str | None = Field(
        default=None, pattern="^(accept|reject|return)$"
    )
    legal_comment: str | None = Field(default=None, max_length=4000)
    overall_risk: str | None = Field(
        default=None, pattern="^(low|medium|high|critical)$"
    )
    reviewer_id: int | None = None


class ReviewAcceptRequest(ReviewActionRequest):
    """``POST /reviews/{id}/accept``."""


class ReviewRejectRequest(ReviewActionRequest):
    """``POST /reviews/{id}/reject``."""


__all__ = [
    "AIReviewResult",
    "ReviewAcceptRequest",
    "ReviewIssue",
    "ReviewOut",
    "ReviewRead",
    "ReviewRejectRequest",
    "ReviewStartRequest",
    "ReviewStartResponse",
    "ReviewUpdate",
    "SuggestedAction",
]
