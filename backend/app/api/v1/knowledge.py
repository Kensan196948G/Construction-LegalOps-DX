"""ナレッジ検索エンドポイント。

- GET `/knowledge` : ナレッジ記事一覧
- GET `/knowledge/search` : ナレッジ記事・契約メタデータを横断検索する
- GET `/knowledge/similar/{contract_id}` : 類似契約を検索する
- POST `/knowledge` : ナレッジ記事追加 (legal/admin)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import CurrentUser, get_current_user, require_role
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
    "",
    response_model=Page[KnowledgeArticleOut],
    summary="ナレッジ記事一覧",
    description="全ナレッジ記事をページネーションで返す。",
)
async def list_articles(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Page[KnowledgeArticleOut]:
    items, total = await knowledge_service.list_articles(session, page=page, size=size)
    return Page[KnowledgeArticleOut](items=items, total=total, page=page, size=size)


@router.get(
    "/search",
    response_model=Page[KnowledgeSearchResult],
    summary="ナレッジ検索",
    description=(
        "クエリ q、タグ、契約種別でナレッジ記事と契約メタデータを横断検索する。"
        "現行実装は DB-backed のテキスト検索とスコアリングを使う。"
    ),
)
async def search_knowledge(
    q: str = Query(..., min_length=1, description="検索クエリ"),
    tag: str | None = Query(default=None),
    contract_type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
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
    summary="類似契約検索",
    description=(
        "対象契約に類似する過去契約を、DBから取得した契約本文・メタデータの"
        "TF-cosine類似度で返す。"
    ),
)
async def find_similar_contracts(
    contract_id: int,
    top_k: int = Query(default=10, ge=1, le=50),
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[SimilarContractOut]:
    try:
        return await knowledge_service.find_similar(
            session, contract_id=contract_id, viewer=current_user, top_k=top_k
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="contract not found")


@router.get(
    "/{article_id}",
    response_model=KnowledgeArticleOut,
    summary="ナレッジ記事詳細",
    description="指定 ID のナレッジ記事を返す。見つからない場合は 404。",
)
async def get_article(
    article_id: int,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> KnowledgeArticleOut:
    article = await knowledge_service.get_article(session, article_id=article_id)
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="article not found")
    return article


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
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_role("legal", "admin")),
) -> KnowledgeArticleOut:
    article = await knowledge_service.create_article(session, data=payload, creator=current_user)
    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="knowledge.create",
        target_type="knowledge_articles",
        target_id=article.id,
        request=request,
    )
    return KnowledgeArticleOut.model_validate(article)
