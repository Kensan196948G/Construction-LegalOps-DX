"""AI review initiation service.

Creates a LegalReview row and runs the configured AI review pipeline. The
pipeline itself lives in :mod:`app.services.ai_review`; when no production
Claude key is available it deterministically falls back to stub mode instead
of returning HTTP 501.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ReviewStatus
from app.models.legal_review import LegalReview
from app.services.ai_review import DISCLAIMER, AIReviewService, AIReviewServiceError


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
        "requires_human_review": bool(result.get("requires_human_review", False)),
        "citation_gaps": int(result.get("citation_gaps", 0)),
        "findings": result.get("issues", []),
        "suggested_actions": result.get("suggested_actions", []),
        "disclaimer": (
            (review.result or {}).get("disclaimer")
            or "本 AI レビュー結果は参考情報であり、最終判断は法務担当者および"
            "顧問弁護士が行ってください。"
        ),
        "created_at": review.created_at,
        "updated_at": review.updated_at,
    }


def _risk_score(overall_risk: str, issue_count: int) -> int:
    """Return a coarse 0-100 score aligned to risk severity."""
    base = {
        "low": 20,
        "medium": 45,
        "high": 70,
        "critical": 90,
    }.get(overall_risk, 45)
    return min(100, base + max(0, issue_count - 1) * 3)


def _contract_text(contract: Any) -> str:
    """Build review text from the available contract fields."""
    metadata = getattr(contract, "extra_metadata", None) or {}
    body = ""
    if isinstance(metadata, dict):
        body = str(
            metadata.get("body")
            or metadata.get("text")
            or metadata.get("description")
            or ""
        )
    parts = [
        f"契約名: {getattr(contract, 'title', '')}",
        f"契約種別: {getattr(contract, 'contract_type', '')}",
        f"相手方: {getattr(contract, 'counterparty', '')}",
        body,
    ]
    return "\n".join(part for part in parts if part and part.strip())


def _api_issue(issue: dict[str, Any], seq: int) -> dict[str, Any]:
    """Convert AIReviewService issue shape to ReviewIssue API shape."""
    return {
        "clause_seq": seq,
        "title": issue.get("title"),
        "risk_level": issue.get("severity", "medium"),
        "comment": issue.get("description") or issue.get("comment") or "",
        "suggestion": issue.get("recommended_action"),
        "citations": list(issue.get("citations") or []),
        "source_page": issue.get("source_page"),
        "clause_number": issue.get("clause_number"),
        "excerpt": issue.get("excerpt"),
        "law_name": issue.get("law_name"),
        "law_article": issue.get("law_article"),
        "law_version": issue.get("law_version"),
        "effective_date": issue.get("effective_date"),
        "primary_source_url": issue.get("primary_source_url"),
        "internal_policy_id": issue.get("internal_policy_id"),
        "internal_policy_version": issue.get("internal_policy_version"),
        "rule_id": issue.get("rule_id"),
        "ai_confidence": issue.get("ai_confidence"),
        "verdict": issue.get("verdict", "finding"),
        "suggested_actions": [],
    }


async def start_review(
    session: AsyncSession,
    *,
    contract_id: int,
    user_id: int | None,
    payload: Any,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Create a LegalReview row and attach a structured AI review result."""
    from app.models.contract import Contract

    contract = await session.get(Contract, contract_id)
    if contract is None:
        raise LookupError(f"contract {contract_id} not found")

    now = datetime.now(UTC)
    review_type = getattr(payload, "review_type", "ai")
    ai_model = getattr(payload, "ai_model", None)

    forced_stub = os.getenv("AI_REVIEW_STUB") == "1"
    mode = "stub" if forced_stub else None
    service_model = ai_model or ("stub" if forced_stub else None)
    service = AIReviewService(mode=mode, model_id=service_model)
    text = _contract_text(contract)

    try:
        ai_result = await service.review_contract(
            text,
            contract_type=getattr(contract, "contract_type", "unknown"),
        )
        result = ai_result.to_dict()
        issues = [
            _api_issue(issue, seq=i + 1)
            for i, issue in enumerate(result.get("issues", []))
        ]
        suggested_actions = result.get("suggested_actions", [])
        overall_risk = result.get("overall_risk")
        risk_score = _risk_score(str(overall_risk), len(issues))
        summary = result.get("summary")
        model_id = result.get("model_id") or ai_model or "stub"
        review_status = ReviewStatus.RUNNING.value
        finished_at = None
    except AIReviewServiceError as exc:
        issues = []
        suggested_actions = []
        overall_risk = None
        risk_score = None
        summary = f"AI review failed: {exc}"
        model_id = ai_model
        review_status = ReviewStatus.FAILED.value
        finished_at = now
        result = {
            "summary": summary,
            "issues": issues,
            "suggested_actions": suggested_actions,
            "disclaimer": DISCLAIMER,
            "error": str(exc),
        }

    result["issues"] = issues
    result["suggested_actions"] = suggested_actions
    result["disclaimer"] = result.get("disclaimer") or DISCLAIMER

    review = LegalReview(
        contract_id=contract_id,
        review_type=review_type,
        status=review_status,
        ai_model=model_id,
        reviewer_id=user_id,
        started_at=now,
        finished_at=finished_at,
        summary=summary,
        overall_risk=overall_risk,
        risk_score=risk_score,
        result=result,
        created_at=now,
        updated_at=now,
    )
    session.add(review)
    await session.flush()
    return _to_dict(review)
