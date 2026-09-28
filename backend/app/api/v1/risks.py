"""リスク管理エンドポイント。

- GET `/risks` : リスク一覧 (重大度・状態・契約 ID で絞り込み)
- GET `/risks/aggregate` : 集計 KPI (ヒートマップ・ステータス別件数)
- GET `/risks/heatmap` : 発生可能性 × 影響度のマトリクス集計
- PATCH `/risks/{id}` : 状態・対応策更新
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.deps import CurrentUser, get_current_user, require_role
from app.models.contract import Contract
from app.models.risk_item import RiskItem
from app.schemas.common import Page
from app.schemas.risk import (
    RiskAggregate,
    RiskHeatmap,
    RiskHeatmapCell,
    RiskOut,
    RiskUpdate,
)
from app.services import audit_service, risk_service

router = APIRouter(prefix="/risks", tags=["risks"])

# ``risk_service`` と同じ可視性ルール。``risk_items`` は RLS が無効
# (``pg_class.relrowsecurity = false``) なので、この条件が唯一の行レベル防御で
# ある。ロール集合を変える場合は ``app/services/risk_service.py`` の
# ``_FULL_ACCESS_ROLES`` と必ず同時に更新すること
# (両者が同じ結果になることは
# ``tests/integration/test_contract_alignment_api.py``
# の ``test_heatmap_matrix_total_matches_risks_list_total`` で固定している)。
_FULL_ACCESS_ROLES = {"admin", "legal", "auditor", "reviewer", "approver"}


def _is_full_access(viewer: CurrentUser) -> bool:
    return getattr(viewer, "role", None) in _FULL_ACCESS_ROLES


@router.get(
    "",
    response_model=Page[RiskOut],
    summary="リスク一覧",
    description="severity / status / contract_id / owner_id / department_id で絞り込み。RLS 適用。",
)
async def list_risks(
    severity: str | None = Query(default=None, description="low/medium/high/critical"),
    status_: str | None = Query(default=None, alias="status"),
    contract_id: int | None = Query(default=None),
    owner_id: int | None = Query(default=None),
    department_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Page[RiskOut]:
    items, total = await risk_service.list_risks(
        session,
        viewer=current_user,
        severity=severity,
        status=status_,
        contract_id=contract_id,
        owner_id=owner_id,
        department_id=department_id,
        page=page,
        size=size,
    )
    return Page[RiskOut](items=items, total=total, page=page, size=size)


@router.get(
    "/aggregate",
    response_model=RiskAggregate,
    summary="リスク集計 KPI",
    description=(
        "重大度ヒートマップ・ステータス別件数・部門別件数・期日超過件数を集計して返却。"
        " ダッシュボードや KPI 画面で利用。"
    ),
)
async def aggregate_risks(
    department_id: int | None = Query(default=None),
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> RiskAggregate:
    return await risk_service.aggregate(
        session,
        viewer=current_user,
        department_id=department_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get(
    "/heatmap",
    response_model=RiskHeatmap,
    summary="リスクヒートマップ（発生可能性 × 影響度）",
    description=(
        "リスクを ``probability`` × ``impact`` で集計し、件数が 1 件以上の"
        "セルを ``matrix`` として返却する。``GET /risks`` と同じ可視性ルールを"
        "適用する。ダッシュボード / リスク一覧画面で利用。"
    ),
)
async def risk_heatmap(
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> RiskHeatmap:
    stmt = (
        select(
            RiskItem.probability,
            RiskItem.impact,
            func.count(RiskItem.id).label("cnt"),
        )
        .where(RiskItem.deleted_at.is_(None))
        .group_by(RiskItem.probability, RiskItem.impact)
    )
    if not _is_full_access(current_user):
        # risk_service.list_risks / aggregate と同じ行レベル絞り込み。
        stmt = stmt.join(Contract, Contract.id == RiskItem.contract_id).where(
            Contract.drafter_id == current_user.db_id
        )

    rows = await session.execute(stmt)
    return RiskHeatmap(
        matrix=[
            RiskHeatmapCell(probability=probability, impact=impact, count=count)
            for probability, impact, count in rows
        ]
    )


@router.patch(
    "/{risk_id}",
    response_model=RiskOut,
    summary="リスク更新",
    description="status (open/mitigated/accepted/closed) や対応策 mitigation を更新する。",
)
async def update_risk(
    risk_id: int,
    payload: RiskUpdate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_role("legal", "manager", "admin")),
) -> RiskOut:
    try:
        risk = await risk_service.update_risk(
            session, risk_id=risk_id, data=payload, editor=current_user
        )
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="risk not found")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    await audit_service.log(
        session,
        actor_id=current_user.db_id,
        action="risk.update",
        target_type="risks",
        target_id=risk["id"],
        payload={"after": payload.model_dump(exclude_unset=True)},
        request=request,
    )
    return RiskOut.model_validate(risk)
