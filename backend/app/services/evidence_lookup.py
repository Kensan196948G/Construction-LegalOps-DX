"""一次情報限定 RAG / 根拠 URL 検証（評価 AI 機能 #1・P0-4）.

検索対象はナレッジベース（knowledge_articles。e-Gov・国交省・公取委等の
一次情報をソースとする社内記事）に限定し、citations の URL は
公的機関ホストの許可リストで検証する。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_article import KnowledgeArticle

# AI レビュー (ai_review.py) の許可リストと同期する
CITATION_ALLOWLIST: tuple[str, ...] = (
    "elaws.e-gov.go.jp",
    "japaneselawtranslation.go.jp",
    "jftc.go.jp",
    "mlit.go.jp",
    "moj.go.jp",
    "nta.go.jp",
    "pca.go.jp",
    "mhlw.go.jp",
    "courts.go.jp",
)


def validate_citation_url(url: str | None) -> bool:
    """引用 URL が一次情報の許可ホストかを判定する。"""
    if not url:
        return False
    try:
        host = urlparse(url).netloc.lower()
    except ValueError:
        return False
    return host == "www.jftc.go.jp" or any(
        host == h or host.endswith("." + h) for h in CITATION_ALLOWLIST
    )


@dataclass(slots=True)
class EvidenceHit:
    article_id: int
    title: str
    source_url: str | None
    excerpt: str
    law_tags: list[str] = field(default_factory=list)
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "article_id": self.article_id,
            "title": self.title,
            "source_url": self.source_url,
            "excerpt": self.excerpt,
            "law_tags": self.law_tags,
            "score": self.score,
            "source_verified": validate_citation_url(self.source_url),
        }


def _excerpt(body: str, query_terms: list[str], radius: int = 120) -> str:
    body = body or ""
    low = body.lower()
    for term in query_terms:
        idx = low.find(term.lower())
        if idx >= 0:
            start = max(0, idx - radius)
            end = min(len(body), idx + len(term) + radius)
            prefix = "…" if start > 0 else ""
            suffix = "…" if end < len(body) else ""
            return f"{prefix}{body[start:end].strip()}{suffix}"
    return body[: radius * 2]


async def search_primary_sources(
    session: AsyncSession,
    *,
    query: str,
    limit: int = 8,
) -> list[EvidenceHit]:
    """ナレッジベースの一次情報記事から関連根拠を検索する。"""
    terms = [t.strip() for t in query.replace("、", " ").replace("，", " ").split() if t.strip()]
    if not terms:
        return []
    conditions = [
        KnowledgeArticle.title.ilike(f"%{t}%")
        | KnowledgeArticle.body.ilike(f"%{t}%")
        for t in terms[:5]
    ]
    stmt = (
        select(KnowledgeArticle)
        .where(or_(*conditions), KnowledgeArticle.deleted_at.is_(None))
        .order_by(KnowledgeArticle.updated_at.desc())
        .limit(limit * 2)
    )
    rows = (await session.execute(stmt)).scalars().all()
    hits: list[EvidenceHit] = []
    for article in rows:
        body = article.body or ""
        citations = list(article.citations or [])
        source_url = next(
            (c for c in citations if validate_citation_url(c)),
            citations[0] if citations else None,
        )
        score = sum(
            1.0
            for t in terms
            if t.lower() in (article.title or "").lower()
            or t.lower() in body.lower()
        ) / len(terms)
        if score <= 0:
            continue
        hits.append(
            EvidenceHit(
                article_id=article.id,
                title=article.title or "",
                source_url=source_url,
                excerpt=_excerpt(body, terms),
                law_tags=list(article.tags or []),
                score=score,
            )
        )
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:limit]


async def verify_citations(
    session: AsyncSession,
    *,
    urls: list[str | None],
) -> dict[str, Any]:
    """引用 URL 群を許可ホストで検証し、結果サマリを返す。"""
    valid = [u for u in urls if validate_citation_url(u)]
    invalid = [u for u in urls if u and not validate_citation_url(u)]
    return {
        "total": len(urls),
        "valid": len(valid),
        "invalid": len(invalid),
        "invalid_urls": invalid[:20],
    }


__all__ = [
    "CITATION_ALLOWLIST",
    "EvidenceHit",
    "search_primary_sources",
    "validate_citation_url",
    "verify_citations",
]
