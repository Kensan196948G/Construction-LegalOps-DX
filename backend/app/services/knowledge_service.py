"""Knowledge search service.

Implements search over contracts table and similarity-based contract
lookup. Knowledge article creation is reserved for a future loop when
a dedicated ``knowledge_articles`` table is added.

Role-scope rules
----------------
* admin / legal / auditor / reviewer / approver  →  all contracts visible
* drafter (and any other role)                   →  only their own contracts
  (``contracts.drafter_id == viewer.id``)
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract import Contract
from app.models.knowledge_article import KnowledgeArticle
from app.models.user import User
from app.schemas.knowledge import (
    KnowledgeArticleCreate,
    KnowledgeArticleOut,
    KnowledgeSearchResult,
    SimilarContractOut,
)
from app.services.similarity_search import CorpusEntry, SimilaritySearchService

# Roles that may see all contracts (not just their own drafts).
_PRIVILEGED_ROLES = frozenset({"admin", "legal", "auditor", "reviewer", "approver"})


def _base_query(viewer: User) -> Any:
    """Return a SELECT query scoped to what ``viewer`` is allowed to see."""
    q = select(Contract).where(Contract.deleted_at.is_(None))
    if viewer.role not in _PRIVILEGED_ROLES:
        q = q.where(Contract.drafter_id == viewer.id)
    return q


async def search(
    session: AsyncSession,
    *,
    q: str,
    viewer: User,
    tag: str | None = None,
    contract_type: str | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[KnowledgeSearchResult], int]:
    """Search contracts by keyword against title and counterparty.

    Parameters
    ----------
    session:
        Async database session.
    q:
        Keyword to search for (LIKE pattern applied to title and counterparty).
    viewer:
        The authenticated user making the request (used for row-level scoping).
    tag:
        Unused in the current implementation (reserved for future tagging).
    contract_type:
        Optional filter restricting results to a specific contract type.
    page:
        1-based page index.
    size:
        Number of items per page.

    Returns
    -------
    tuple[list[KnowledgeSearchResult], int]
        ``(items, total)`` where *total* is the unfiltered match count.
    """
    pattern = f"%{q}%"

    base = _base_query(viewer).where(
        or_(
            Contract.title.ilike(pattern),
            Contract.counterparty.ilike(pattern),
        )
    )

    if contract_type:
        base = base.where(Contract.contract_type == contract_type)

    # COUNT via a dedicated subquery to avoid loading all rows into memory.
    count_q = await session.execute(select(func.count()).select_from(base.subquery()))
    total: int = count_q.scalar() or 0

    # Paginated data fetch.
    offset = (page - 1) * size
    data_q = await session.execute(base.order_by(Contract.id).offset(offset).limit(size))
    page_rows = data_q.scalars().all()

    items: list[KnowledgeSearchResult] = [
        KnowledgeSearchResult(
            id=c.id,
            title=c.title,
            snippet=c.title[:100],
            score=1.0,
            tags=[],
        )
        for c in page_rows
    ]

    return items, total


async def find_similar(
    session: AsyncSession,
    *,
    contract_id: int,
    viewer: User,
    top_k: int = 10,
) -> list[SimilarContractOut]:
    """Return the top-k contracts most similar to ``contract_id``.

    Similarity is calculated using :class:`SimilaritySearchService` (TF-cosine
    over bi-gram tokens). The target contract title is used as the query; all
    other visible contracts form the corpus.

    Raises
    ------
    LookupError
        When ``contract_id`` is not found (or is not visible to ``viewer``).
    """
    # Load the target contract (respecting viewer scope).
    target_stmt = _base_query(viewer).where(Contract.id == contract_id)
    target_result = await session.execute(target_stmt)
    target = target_result.scalar_one_or_none()
    if target is None:
        raise LookupError(f"contract {contract_id} not found")

    # Load the rest of the visible contracts as corpus (exclude the target).
    corpus_stmt = _base_query(viewer).where(Contract.id != contract_id)
    corpus_result = await session.execute(corpus_stmt)
    corpus_rows = corpus_result.scalars().all()

    if not corpus_rows:
        return []

    corpus = [
        CorpusEntry(
            contract_id=str(c.id),
            title=c.title,
            text=c.title,  # Using title as text; body field not stored on Contract.
            contract_type=c.contract_type,
            metadata={"contract_no": c.contract_no, "counterparty": c.counterparty},
        )
        for c in corpus_rows
    ]

    svc = SimilaritySearchService(corpus)
    hits = await svc.search(target.title, top_k=top_k)

    # Build a quick lookup map from contract_id (str) → Contract ORM object.
    id_to_contract: dict[str, Contract] = {str(c.id): c for c in corpus_rows}

    results: list[SimilarContractOut] = []
    for hit in hits:
        c = id_to_contract.get(hit.contract_id)
        if c is None:
            continue
        results.append(
            SimilarContractOut(
                id=c.id,
                contract_no=c.contract_no,
                title=c.title,
                similarity=hit.score,
                counterparty=c.counterparty,
            )
        )

    return results


async def create_article(
    session: AsyncSession,
    *,
    data: KnowledgeArticleCreate,
    creator: User,
) -> KnowledgeArticleOut:
    """Create and persist a knowledge article.

    Parameters
    ----------
    session:
        Async database session.
    data:
        Validated article payload.
    creator:
        The authenticated user creating the article (used as author_id).

    Returns
    -------
    KnowledgeArticleOut
        The newly created article with DB-assigned id and timestamps.
    """
    article = KnowledgeArticle(
        title=data.title,
        body=data.body,
        contract_type=data.contract_type,
        tags=data.tags,
        citations=data.citations,
        author_id=getattr(creator, "id", None),
    )
    session.add(article)
    await session.flush()
    await session.refresh(article)
    return KnowledgeArticleOut(
        id=article.id,
        title=article.title,
        body=article.body,
        tags=article.tags or [],
        contract_type=article.contract_type,
        citations=article.citations or [],
        created_at=article.created_at,
        updated_at=article.updated_at,
    )
