"""契約書全文検索サービス（ロードマップ #5 下位 / Issue #100）.

契約メタデータ（contracts）・条項本文（clauses.body）・契約文書
（contract_documents.content）を横断する全文検索＋文字バイグラム Dice 係数による
類似度スコアを返す。DB ポータブル（trgm 非依存）で、AI を使用しない決定論的な
スコアリングを行う。

補足: ナレッジ横断検索は ``GET /knowledge/search``、類似契約検索（タイトル基準・
TF-cosine）は ``GET /knowledge/similar/{contract_id}`` が既存。本サービスは
「契約書本文（条項・文書）の全文検索」を補完する。
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.models.clause import Clause
from app.models.contract import Contract
from app.models.contract_document import ContractDocument

logger = structlog.get_logger(__name__)

SCOPES = frozenset({"contracts", "clauses", "documents", "all"})

_SNIPPET_RADIUS = 60


def _bigram_dice(a: str, b: str) -> float:
    """文字バイグラム Dice 係数（0.0〜1.0・日本語向き・決定論的）."""
    a = a.lower()
    b = b.lower()

    def bigrams(text: str) -> set[str]:
        if len(text) < 2:
            return {text} if text else set()
        return {text[i : i + 2] for i in range(len(text) - 1)}

    ba = bigrams(a)
    bb = bigrams(b)
    if not ba or not bb:
        return 0.0
    return 2.0 * len(ba & bb) / (len(ba) + len(bb))


def _first_index(text: str, term: str) -> int:
    return text.lower().find(term.lower())


def _snippet(text: str, term: str) -> str:
    idx = _first_index(text, term)
    if idx < 0:
        return text[:_SNIPPET_RADIUS * 2]
    start = max(0, idx - _SNIPPET_RADIUS)
    end = min(len(text), idx + len(term) + _SNIPPET_RADIUS)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return prefix + text[start:end] + suffix


async def _contract_map(
    session: AsyncSession, *, ids: set[int]
) -> dict[int, Contract]:
    if not ids:
        return {}
    rows = (
        await session.execute(select(Contract).where(Contract.id.in_(ids)))
    ).scalars().all()
    return {c.id: c for c in rows}


async def _search_contracts(
    session: AsyncSession, *, q: str, limit: int
) -> list[dict[str, Any]]:
    pattern = q
    stmt = select(Contract)
    clause_filters = [
        Contract.title.contains(pattern, autoescape=True),
        Contract.counterparty.contains(pattern, autoescape=True),
        Contract.contract_no.contains(pattern, autoescape=True),
    ]
    rows = (
        await session.execute(
            stmt.where(or_(*clause_filters)).limit(limit)
        )
    ).scalars().all()
    hits: list[dict[str, Any]] = []
    for c in rows:
        fields: list[str] = []
        snippet: str | None = None
        for field, value in (
            ("title", c.title),
            ("counterparty", c.counterparty),
            ("contract_no", c.contract_no),
        ):
            if _first_index(value, q) >= 0:
                fields.append(field)
                if snippet is None:
                    snippet = _snippet(value, q)
        if not fields:
            continue
        score = 10.0 * len(fields) + 90.0 * _bigram_dice(c.title, q)
        hits.append(
            {
                "kind": "contract",
                "record_id": c.id,
                "contract_id": c.id,
                "contract_no": c.contract_no,
                "title": c.title,
                "snippet": snippet or c.title,
                "matched_fields": fields,
                "score": round(score, 4),
            }
        )
    return hits


async def _search_clauses(
    session: AsyncSession, *, q: str, limit: int
) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(Clause).where(
                Clause.body.contains(q, autoescape=True)
                | Clause.title.contains(q, autoescape=True)
            ).limit(limit)
        )
    ).scalars().all()
    contracts = await _contract_map(session, ids={c.contract_id for c in rows})
    hits: list[dict[str, Any]] = []
    for clause in rows:
        contract = contracts.get(clause.contract_id)
        score = 10.0 + 90.0 * _bigram_dice(clause.body, q)
        hits.append(
            {
                "kind": "clause",
                "record_id": clause.id,
                "contract_id": clause.contract_id,
                "contract_no": contract.contract_no if contract else None,
                "title": clause.title or f"第{clause.seq}条",
                "snippet": _snippet(clause.body, q),
                "matched_fields": ["body"],
                "score": round(score, 4),
            }
        )
    return hits


async def _search_documents(
    session: AsyncSession, *, q: str, limit: int
) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(ContractDocument).where(
                ContractDocument.content.contains(q, autoescape=True)
                | ContractDocument.title.contains(q, autoescape=True)
            ).limit(limit)
        )
    ).scalars().all()
    contracts = await _contract_map(session, ids={d.contract_id for d in rows})
    hits: list[dict[str, Any]] = []
    for doc in rows:
        contract = contracts.get(doc.contract_id)
        text = doc.content or doc.title
        score = 10.0 + 90.0 * _bigram_dice(text, q)
        hits.append(
            {
                "kind": "document",
                "record_id": doc.id,
                "contract_id": doc.contract_id,
                "contract_no": contract.contract_no if contract else None,
                "title": doc.title,
                "snippet": _snippet(text, q),
                "matched_fields": ["content"] if doc.content else ["title"],
                "score": round(score, 4),
            }
        )
    return hits


async def search(
    session: AsyncSession,
    *,
    q: str,
    scope: str = "all",
    contract_id: int | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """契約書全文検索（contracts / clauses / documents）.

    ``scope``: all | contracts | clauses | documents。``contract_id`` 指定時は
    当該契約配下のみ検索する。
    """
    q = (q or "").strip()
    if not q:
        raise ValidationError("検索クエリ q は必須です。")
    if len(q) > 200:
        raise ValidationError("検索クエリは 200 文字以内です。")
    if scope not in SCOPES:
        raise ValidationError(f"不正な scope: {scope!r}（all/contracts/clauses/documents）")
    if limit < 1 or limit > 50:
        raise ValidationError("limit は 1〜50 です。")

    per_scope = limit * 3 if scope == "all" else limit
    hits: list[dict[str, Any]] = []
    if scope in {"all", "contracts"}:
        hits.extend(await _search_contracts(session, q=q, limit=per_scope))
    if scope in {"all", "clauses"}:
        clause_hits = await _search_clauses(session, q=q, limit=per_scope)
        if contract_id is not None:
            clause_hits = [h for h in clause_hits if h["contract_id"] == contract_id]
        hits.extend(clause_hits)
    if scope in {"all", "documents"}:
        doc_hits = await _search_documents(session, q=q, limit=per_scope)
        if contract_id is not None:
            doc_hits = [h for h in doc_hits if h["contract_id"] == contract_id]
        hits.extend(doc_hits)

    if scope == "contracts" and contract_id is not None:
        hits = [h for h in hits if h["contract_id"] == contract_id]

    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits[:limit]


__all__ = ["search"]
