"""AI レビューエンドポイント。

- POST `/contracts/{id}/reviews` : AI レビュー起動 (202 Accepted)
- GET `/reviews` : レビュー一覧
- GET `/reviews/{id}` : レビュー詳細
- PATCH `/reviews/{id}` : 法務担当コメント・final_decision 更新
- POST `/reviews/{id}/accept` / `/reject` : 結果受領/差戻
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import get_current_user, require_role
from app.models.user import User
from app.schemas.common import Page
from app.schemas.review import (
    ReviewAcceptRequest,
    ReviewOut,
    ReviewRejectRequest,
    ReviewStartRequest,
    ReviewStartResponse,
    ReviewUpdate,
)
from app.services import ai_review_service, audit_service, review_service

router = APIRouter(tags=["reviews"])


@router.post(
    "/contracts/{contract_id}/reviews",
    response_model=ReviewStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="AI レビュー起動",
    description="契約に対し AI レビュージョブを起動する。レート制限: 30 req/h/user。",
)
async def start_review(
    contract_id: int,
    payload: ReviewStartRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_role("site", "legal", "admin")),
) -> ReviewStartResponse:
    try:
        review = await ai_review_service.start_review(
            session,
            contract_id=contract_id,
            user_id=current_user.id,
            payload=payload,
            idempotency_key=idempotency_key,
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="contract not found")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    await audit_service.log(
        session,
        actor_id=current_user.id,
        action="review.start",
        target_type="reviews",
        target_id=review.id,
        payload={"contract_id": contract_id, "ai_model": payload.ai_model},
        request=request,
    )
    return ReviewStartResponse.model_validate(review)


@router.get(
    "/reviews",
    response_model=Page[ReviewOut],
    summary="レビュー一覧",
    description="契約 ID・ステータス・モデルで絞り込み可能。",
)
async def list_reviews(
    contract_id: int | None = Query(default=None),
    status_: str | None = Query(default=None, alias="status"),
    ai_model: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Page[ReviewOut]:
    items, total = await review_service.list_reviews(
        session,
        viewer=current_user,
        contract_id=contract_id,
        status=status_,
        ai_model=ai_model,
        page=page,
        size=size,
    )
    return Page[ReviewOut](items=items, total=total, page=page, size=size)


@router.get(
    "/reviews/{review_id}",
    response_model=ReviewOut,
    summary="レビュー詳細",
    description="findings 配列と AI 免責事項を含むレビュー結果を返す。",
)
async def get_review(
    review_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReviewOut:
    review = await review_service.get_review(session, review_id=review_id, viewer=current_user)
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="review not found")
    return ReviewOut.model_validate(review)


@router.patch(
    "/reviews/{review_id}",
    response_model=ReviewOut,
    summary="レビュー更新",
    description="法務担当者のコメント・final_decision を更新する。",
)
async def update_review(
    review_id: int,
    payload: ReviewUpdate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_role("legal", "admin")),
) -> ReviewOut:
    try:
        review = await review_service.update_review(
            session,
            review_id=review_id,
            data=payload,
            editor=current_user,
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="review not found")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    await audit_service.log(
        session,
        actor_id=current_user.id,
        action="review.update",
        target_type="reviews",
        target_id=review.id,
        payload={"after": payload.model_dump(exclude_unset=True)},
        request=request,
    )
    return ReviewOut.model_validate(review)


@router.post(
    "/reviews/{review_id}/accept",
    response_model=ReviewOut,
    summary="レビュー受領",
    description="AI レビュー結果を受領し、契約 status を更新する。",
)
async def accept_review(
    review_id: int,
    payload: ReviewAcceptRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_role("legal", "admin")),
) -> ReviewOut:
    try:
        review = await review_service.accept(
            session, review_id=review_id, actor=current_user, comment=payload.comment
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="review not found")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    await audit_service.log(
        session,
        actor_id=current_user.id,
        action="review.accept",
        target_type="reviews",
        target_id=review.id,
        request=request,
    )
    return ReviewOut.model_validate(review)


@router.post(
    "/reviews/{review_id}/reject",
    response_model=ReviewOut,
    summary="レビュー差戻",
)
async def reject_review(
    review_id: int,
    payload: ReviewRejectRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_role("legal", "admin")),
) -> ReviewOut:
    try:
        review = await review_service.reject(
            session, review_id=review_id, actor=current_user, reason=payload.reason
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="review not found")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    await audit_service.log(
        session,
        actor_id=current_user.id,
        action="review.reject",
        target_type="reviews",
        target_id=review.id,
        payload={"reason": payload.reason},
        request=request,
    )
    return ReviewOut.model_validate(review)
