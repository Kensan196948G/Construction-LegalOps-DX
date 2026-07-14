"""Knowledge search service.

Implements search over contracts table and similarity-based contract
lookup. Knowledge article creation is reserved for a future loop when
a dedicated ``knowledge_articles`` table is added.

Role-scope rules
----------------
* admin / legal / auditor / reviewer / approver  →  all contracts visible
* drafter (and any other role)                   →  only their own contracts
  (``contracts.drafter_id == viewer.db_id``)
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import CurrentUser
from app.models.contract import Contract
from app.models.knowledge_article import KnowledgeArticle
from app.schemas.knowledge import (
    KnowledgeArticleCreate,
    KnowledgeArticleOut,
    KnowledgeSearchResult,
    SimilarContractOut,
)
from app.services.similarity_search import CorpusEntry, SimilaritySearchService

# ---------------------------------------------------------------------------
# Article CRUD helpers
# ---------------------------------------------------------------------------


async def list_articles(
    session: AsyncSession,
    *,
    page: int = 1,
    size: int = 20,
) -> tuple[list[KnowledgeArticleOut], int]:
    """Return a paginated list of all non-deleted knowledge articles."""
    base = select(KnowledgeArticle).where(KnowledgeArticle.deleted_at.is_(None))

    count_result = await session.execute(select(func.count()).select_from(base.subquery()))
    total: int = count_result.scalar() or 0

    offset = (page - 1) * size
    rows_result = await session.execute(
        base.order_by(KnowledgeArticle.id).offset(offset).limit(size)
    )
    rows = rows_result.scalars().all()

    items = [
        KnowledgeArticleOut(
            id=a.id,
            title=a.title,
            body=a.body,
            tags=list(a.tags or []),
            contract_type=a.contract_type,
            citations=list(a.citations or []),
            created_at=a.created_at,
            updated_at=a.updated_at,
        )
        for a in rows
    ]
    return items, total


async def get_article(
    session: AsyncSession,
    *,
    article_id: int,
) -> KnowledgeArticleOut | None:
    """Return a single knowledge article by id, or None if not found."""
    result = await session.execute(
        select(KnowledgeArticle).where(
            KnowledgeArticle.id == article_id,
            KnowledgeArticle.deleted_at.is_(None),
        )
    )
    a = result.scalar_one_or_none()
    if a is None:
        return None
    return KnowledgeArticleOut(
        id=a.id,
        title=a.title,
        body=a.body,
        tags=list(a.tags or []),
        contract_type=a.contract_type,
        citations=list(a.citations or []),
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


# Roles that may see all contracts (not just their own drafts).
_PRIVILEGED_ROLES = frozenset({"admin", "legal", "auditor", "reviewer", "approver"})


def _base_query(viewer: CurrentUser) -> Any:
    """Return a SELECT query scoped to what ``viewer`` is allowed to see."""
    q = select(Contract).where(Contract.deleted_at.is_(None))
    if viewer.role not in _PRIVILEGED_ROLES:
        q = q.where(Contract.drafter_id == viewer.db_id)
    return q


async def search(
    session: AsyncSession,
    *,
    q: str,
    viewer: CurrentUser,
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
    results: list[KnowledgeSearchResult] = []

    # --- Search knowledge_articles first (primary knowledge source) ----------
    ka_base = select(KnowledgeArticle).where(
        KnowledgeArticle.deleted_at.is_(None),
        or_(
            KnowledgeArticle.title.ilike(pattern),
            KnowledgeArticle.body.ilike(pattern),
        ),
    )
    if contract_type:
        ka_base = ka_base.where(KnowledgeArticle.contract_type == contract_type)
    if tag:
        # tags is a JSONB/JSON array; filter in Python after fetch (dialect-safe)
        ka_rows_q = await session.execute(ka_base.order_by(KnowledgeArticle.id))
        ka_rows = [r for r in ka_rows_q.scalars().all() if tag in (r.tags or [])]
    else:
        ka_rows_q = await session.execute(ka_base.order_by(KnowledgeArticle.id))
        ka_rows = list(ka_rows_q.scalars().all())

    for a in ka_rows:
        results.append(
            KnowledgeSearchResult(
                id=a.id,
                title=a.title,
                snippet=a.body[:100] if a.body else a.title[:100],
                score=1.0,
                tags=list(a.tags or []),
            )
        )

    # --- Search contracts (secondary source, contract-law knowledge) ---------
    base = _base_query(viewer).where(
        or_(
            Contract.title.ilike(pattern),
            Contract.counterparty.ilike(pattern),
        )
    )
    if contract_type:
        base = base.where(Contract.contract_type == contract_type)

    count_q = await session.execute(select(func.count()).select_from(base.subquery()))
    contract_total: int = count_q.scalar() or 0

    # Only include contracts if there are results worth showing
    if contract_total > 0:
        data_q = await session.execute(
            base.order_by(Contract.id).limit(max(0, size - len(results)))
        )
        for c in data_q.scalars().all():
            results.append(
                KnowledgeSearchResult(
                    id=c.id,
                    title=c.title,
                    snippet=c.title[:100],
                    score=0.8,  # lower score for contracts vs articles
                    tags=[],
                )
            )

    # Paginate combined results
    total = len(results)
    offset = (page - 1) * size
    items = results[offset : offset + size]

    return items, total


async def find_similar(
    session: AsyncSession,
    *,
    contract_id: int,
    viewer: CurrentUser,
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
    creator: CurrentUser,
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
        author_id=getattr(creator, "db_id", None),
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
