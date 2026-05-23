"""AI review initiation service.

Creates a LegalReview row and (in stub mode) skips the real Claude API call.
Set AI_REVIEW_STUB=1 to activate stub mode for integration tests.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ReviewStatus
from app.models.legal_review import LegalReview


def _to_dict(review: LegalReview) -> dict[str, Any]:
    result = review.result or {}
    return {
        "id": review.id,
        "contract_id": review.contract_id,
        "review_type": review.review_type,
        "status": review.status,
        "ai_model": review.ai_model,
        "overall_risk": review.overall_risk,
        "risk_score": review.risk_score,
        "summary": review.summary,
        "started_at": review.started_at,
        "finished_at": review.finished_at,
        "reviewer_id": review.reviewer_id,
        "ai_input_tokens": review.ai_input_tokens,
        "ai_output_tokens": review.ai_output_tokens,
        "result": result,
        "findings": result.get("issues", []),
        "suggested_actions": result.get("suggested_actions", []),
        "disclaimer": (
            "本 AI レビュー結果は参考情報であり、最終判断は法務担当者および"
            "顧問弁護士が行ってください。"
        ),
        "created_at": review.created_at,
        "updated_at": review.updated_at,
    }


async def start_review(
    session: AsyncSession,
    *,
    contract_id: int,
    user_id: int,
    payload: Any,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Create a LegalReview row. Stub mode skips the real AI pipeline."""
    from app.models.contract import Contract

    contract = await session.get(Contract, contract_id)
    if contract is None:
        raise LookupError(f"contract {contract_id} not found")

    now = datetime.now(UTC)
    review_type = getattr(payload, "review_type", "ai")
    ai_model = getattr(payload, "ai_model", None)

    if os.getenv("AI_REVIEW_STUB") == "1":
        review = LegalReview(
            contract_id=contract_id,
            review_type=review_type,
            status=ReviewStatus.RUNNING.value,
            ai_model=ai_model or "stub",
            started_at=now,
            result={},
            created_at=now,
            updated_at=now,
        )
        session.add(review)
        await session.flush()
        return _to_dict(review)

    from fastapi import HTTPException, status as http_status

    raise HTTPException(
        status_code=http_status.HTTP_501_NOT_IMPLEMENTED,
        detail="Real AI review pipeline is not implemented yet.",
    )
