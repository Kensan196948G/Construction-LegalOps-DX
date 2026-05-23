"""Legal review CRUD service.

Handles list / get / update / accept / reject over :class:`LegalReview`
objects.  AI review *initiation* is handled by :mod:`ai_review_service`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ReviewStatus
from app.models.legal_review import LegalReview

_FULL_ACCESS_ROLES = {"admin", "legal", "auditor", "reviewer", "approver"}


def _is_full_access(viewer: Any) -> bool:
    return getattr(viewer, "role", None) in _FULL_ACCESS_ROLES


def _to_dict(review: LegalReview) -> dict[str, Any]:
    result = review.result or {}
    findings = result.get("issues", [])
    suggested_actions = result.get("suggested_actions", [])
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
        "reviewer_id": review.reviewer_id if isinstance(review.reviewer_id, (int, type(None))) else None,
        "ai_input_tokens": review.ai_input_tokens,
        "ai_output_tokens": review.ai_output_tokens,
        "result": result,
        "findings": findings,
        "suggested_actions": suggested_actions,
        "disclaimer": (
            "本 AI レビュー結果は参考情報であり、最終判断は法務担当者および"
            "顧問弁護士が行ってください。"
        ),
        "created_at": review.created_at,
        "updated_at": review.updated_at,
    }


async def list_reviews(
    session: AsyncSession,
    *,
    viewer: Any,
    contract_id: int | None = None,
    status: str | None = None,
    ai_model: str | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[dict[str, Any]], int]:
    stmt = select(LegalReview).where(LegalReview.deleted_at.is_(None))
    if not _is_full_access(viewer):
        # Site users can only see reviews on their own contracts.
        from app.models.contract import Contract  # avoid circular at module level

        stmt = stmt.join(Contract, Contract.id == LegalReview.contract_id).where(
            Contract.drafter_id == viewer.id
        )
    if contract_id is not None:
        stmt = stmt.where(LegalReview.contract_id == contract_id)
    if status is not None:
        stmt = stmt.where(LegalReview.status == status)
    if ai_model is not None:
        stmt = stmt.where(LegalReview.ai_model == ai_model)

    count_q = await session.execute(
        stmt.with_only_columns(
            __import__("sqlalchemy", fromlist=["func"]).func.count(LegalReview.id)  # type: ignore[attr-defined]
        ).order_by(None)
    )
    total = count_q.scalar() or 0

    stmt = stmt.order_by(LegalReview.id.desc()).offset((page - 1) * size).limit(size)
    rows = await session.execute(stmt)
    items = [_to_dict(r) for r in rows.scalars()]
    return items, total


async def get_review(
    session: AsyncSession,
    *,
    review_id: int,
    viewer: Any,
) -> dict[str, Any] | None:
    stmt = select(LegalReview).where(
        LegalReview.id == review_id,
        LegalReview.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    review = result.scalar_one_or_none()
    if review is None:
        return None
    if not _is_full_access(viewer):
        from app.models.contract import Contract

        cr = await session.get(Contract, review.contract_id)
        if cr is None or cr.drafter_id != viewer.id:
            return None
    return _to_dict(review)


async def update_review(
    session: AsyncSession,
    *,
    review_id: int,
    data: Any,
    editor: Any,
) -> dict[str, Any]:
    result = await session.execute(
        select(LegalReview).where(
            LegalReview.id == review_id, LegalReview.deleted_at.is_(None)
        )
    )
    review = result.scalar_one_or_none()
    if review is None:
        raise LookupError(f"review {review_id} not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(review, field):
            setattr(review, field, value)
    review.updated_at = datetime.now(UTC)
    await session.flush()
    return _to_dict(review)


async def accept(
    session: AsyncSession,
    *,
    review_id: int,
    actor: Any,
    comment: str | None = None,
) -> dict[str, Any]:
    result = await session.execute(
        select(LegalReview).where(
            LegalReview.id == review_id, LegalReview.deleted_at.is_(None)
        )
    )
    review = result.scalar_one_or_none()
    if review is None:
        raise LookupError(f"review {review_id} not found")
    if review.status not in (ReviewStatus.COMPLETED, ReviewStatus.RUNNING):
        raise ValueError(f"cannot accept review in status '{review.status}'")

    review.status = ReviewStatus.COMPLETED.value
    review.reviewer_id = getattr(actor, "id", None)
    review.finished_at = datetime.now(UTC)
    review.updated_at = datetime.now(UTC)
    if comment:
        extra = review.result or {}
        extra["legal_comment"] = comment
        review.result = extra
    await session.flush()
    return _to_dict(review)


async def reject(
    session: AsyncSession,
    *,
    review_id: int,
    actor: Any,
    reason: str | None = None,
) -> dict[str, Any]:
    result = await session.execute(
        select(LegalReview).where(
            LegalReview.id == review_id, LegalReview.deleted_at.is_(None)
        )
    )
    review = result.scalar_one_or_none()
    if review is None:
        raise LookupError(f"review {review_id} not found")

    review.status = ReviewStatus.REJECTED.value
    review.reviewer_id = getattr(actor, "id", None)
    review.finished_at = datetime.now(UTC)
    review.updated_at = datetime.now(UTC)
    if reason:
        extra = review.result or {}
        extra["rejection_reason"] = reason
        review.result = extra
    await session.flush()
    return _to_dict(review)
