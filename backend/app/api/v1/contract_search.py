"""契約書全文検索エンドポイント（Issue #100・ロードマップ #5 下位）.

``GET /search`` — 契約メタデータ・条項本文・契約文書を横断検索し、
ヒット位置スニペット＋バイグラム類似度スコア（降順）を返す。

補足: ナレッジ横断検索は ``GET /knowledge/search``、類似契約（タイトル・
TF-cosine）は ``GET /knowledge/similar/{contract_id}`` と住み分ける。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import CurrentUser, require_role
from app.schemas.contract_search import ContractSearchHit
from app.services import contract_search_service

router = APIRouter(prefix="/search", tags=["search"])

_READ_ROLES = ("viewer", "drafter", "reviewer", "approver", "admin", "auditor")


@router.get(
    "",
    response_model=list[ContractSearchHit],
    summary="契約書全文検索（条項・文書・契約メタデータ横断）",
)
async def search_contracts(
    q: str = Query(..., min_length=1, max_length=200, description="検索クエリ"),
    scope: str = Query(
        default="all",
        description="contracts / clauses / documents / all（既定 all）",
    ),
    contract_id: int | None = Query(default=None, description="契約配下のみに絞る"),
    limit: int = Query(default=20, ge=1, le=50),
    session: AsyncSession = Depends(get_db),
    _current_user: CurrentUser = Depends(require_role(*_READ_ROLES)),
) -> list[ContractSearchHit]:
    hits = await contract_search_service.search(
        session, q=q, scope=scope, contract_id=contract_id, limit=limit
    )
    return [ContractSearchHit(**hit) for hit in hits]
