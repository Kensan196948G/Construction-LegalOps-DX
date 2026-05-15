"""ナレッジ検索エンドポイント (stub)。

- GET `/knowledge/search` : 過去レビューや判例ナレッジを全文・ベクトル検索する (stub)
- GET `/knowledge/similar/{contract_id}` : 類似契約を検索する (stub)
- POST `/knowledge` : ナレッジ記事追加 (legal/admin)

Loop 5 で OpenSearch / pgvector の本格実装に切り替える想定。
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, require_role
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import Page
from app.schemas.knowledge import (
    KnowledgeArticleCreate,
    KnowledgeArticleOut,
    KnowledgeSearchResult,
    SimilarContractOut,
)
from app.services import audit_service, knowledge_service

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get(
    "/search",
    response_model=Page[KnowledgeSearchResult],
    summary="ナレッジ検索 (stub)",
    description=(
        "クエリ q とタグでナレッジ記事・過去契約・判例コメントを横断検索する stub。"
        " 本実装は Loop 5 で OpenSearch / pgvector を統合予定。"
    ),
)
async def search_knowledge(
    q: str = Query(..., min_length=1, description="検索クエリ"),
    tag: Optional[str] = Query(default=None),
    contract_type: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Page[KnowledgeSearchResult]:
    items, total = await knowledge_service.search(
        session,
        viewer=current_user,
        q=q,
        tag=tag,
        contract_type=contract_type,
        page=page,
        size=size,
    )
    return Page[KnowledgeSearchResult](items=items, total=total, page=page, size=size)


@router.get(
    "/similar/{contract_id}",
    response_model=list[SimilarContractOut],
    summary="類似契約検索 (stub)",
    description=(
        "対象契約に類似する過去契約を embedding 類似度で取得する stub。Loop 5 にて pgvector で実装。"
    ),
)
async def find_similar_contracts(
    contract_id: int,
    top_k: int = Query(default=10, ge=1, le=50),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SimilarContractOut]:
    try:
        return await knowledge_service.find_similar(
            session, contract_id=contract_id, viewer=current_user, top_k=top_k
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="contract not found")


@router.post(
    "",
    response_model=KnowledgeArticleOut,
    status_code=status.HTTP_201_CREATED,
    summary="ナレッジ記事追加",
)
async def create_article(
    payload: KnowledgeArticleCreate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_role("legal", "admin")),
) -> KnowledgeArticleOut:
    article = await knowledge_service.create_article(session, data=payload, creator=current_user)
    await audit_service.log(
        session,
        actor_id=current_user.id,
        action="knowledge.create",
        target_type="knowledge_articles",
        target_id=article.id,
        request=request,
    )
    return KnowledgeArticleOut.model_validate(article)
