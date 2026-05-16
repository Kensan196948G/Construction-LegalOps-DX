"""ダッシュボード集計エンドポイント。

- GET `/dashboard/summary` : 未レビュー件数 / 承認待ち / 期限切れ / 高リスク件数
- GET `/dashboard/trends` : 期間別件数推移 (週次/月次)

ロールに応じて集計範囲が変わる (site は自身案件、manager は配下、legal/admin は全件)。
"""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas.dashboard import DashboardSummary, DashboardTrends
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get(
    "/summary",
    response_model=DashboardSummary,
    summary="ダッシュボードサマリ",
    description=(
        "KPI を集計: pending_review (未レビュー), pending_approval (承認待ち),"
        " overdue (期限切れ), high_risk (高リスク件数), recent_completed (直近完了),"
        " my_tasks (自分宛タスク)。"
    ),
)
async def get_summary(
    department_id: int | None = Query(default=None, description="部署で絞り込み"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DashboardSummary:
    return cast(DashboardSummary, await dashboard_service.get_summary(
        session, viewer=current_user, department_id=department_id
    ))


@router.get(
    "/trends",
    response_model=DashboardTrends,
    summary="ダッシュボードトレンド",
    description="期間別の契約件数・レビュー件数・承認件数の推移を集計。",
)
async def get_trends(
    interval: str = Query(default="week", description="week / month"),
    weeks: int = Query(default=12, ge=1, le=52, description="集計期間 (interval の単位数)"),
    department_id: int | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DashboardTrends:
    return cast(DashboardTrends, await dashboard_service.get_trends(
        session,
        viewer=current_user,
        interval=interval,
        windows=weeks,
        department_id=department_id,
    ))
