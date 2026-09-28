"""Risk-item Pydantic schemas.

Mirrors ``docs/api_design.md`` section 8.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

from app.models.enums import RiskImpact, RiskProbability

from .common import ORMModel


class RiskOut(ORMModel):
    """Read schema for a single risk item."""

    id: int
    contract_id: int
    severity: Annotated[str, Field(pattern="^(low|medium|high|critical)$")]
    status: Annotated[str, Field(max_length=32)]
    title: str
    description: str | None = None
    mitigation: str | None = None
    owner_id: int | None = None
    department_id: int | None = None
    due_date: datetime | None = None
    created_at: datetime
    updated_at: datetime


class RiskUpdate(BaseModel):
    """Patch payload for ``PATCH /risks/{id}``."""

    status: str | None = Field(default=None, max_length=32)
    mitigation: str | None = Field(default=None, max_length=4000)
    severity: str | None = Field(
        default=None, pattern="^(low|medium|high|critical)$"
    )
    owner_id: int | None = None
    due_date: datetime | None = None


class RiskAggregate(BaseModel):
    """Response of ``GET /risks/aggregate``.

    Heat map + per-status counts. Always carries the project disclaimer
    so downstream UIs cannot strip it inadvertently.
    """

    by_severity: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    open_count: int = Field(default=0, ge=0)
    closed_count: int = Field(default=0, ge=0)
    disclaimer: str = (
        "本リスク評価は AI / ルール出力の参考情報です。最終判断は法務担当者"
        "および顧問弁護士が行ってください。"
    )


class RiskHeatmapCell(BaseModel):
    """発生可能性 × 影響度の 1 セルと、その件数。

    ``probability`` / ``impact`` は ``risk_items`` の CHECK 制約
    （``ck_risk_probability`` / ``ck_risk_impact``）と同じ
    :class:`~app.models.enums.RiskProbability` /
    :class:`~app.models.enums.RiskImpact`（``low`` / ``medium`` / ``high``）
    を取る。frontend の ``riskHeatmapCellSchema`` は
    ``low`` / ``medium`` / ``high`` / ``critical`` の 4 値を許容する上位集合
    であり、本 3 値はその部分集合としてそのまま妥当する（frontend 側の
    スキーマを緩める必要はない）。
    """

    probability: RiskProbability
    impact: RiskImpact
    count: int = Field(ge=0)


class RiskHeatmap(BaseModel):
    """Response of ``GET /risks/heatmap``.

    frontend ``lib/api/schemas.ts`` の ``riskHeatmapSchema``
    （``{ matrix: [{ probability, impact, count }] }``）と同形。
    発生件数が 0 のセルは返さない（frontend は ``find()`` の未ヒットを 0 として
    描画する）。
    """

    matrix: list[RiskHeatmapCell] = Field(default_factory=list)


__all__ = [
    "RiskAggregate",
    "RiskHeatmap",
    "RiskHeatmapCell",
    "RiskOut",
    "RiskUpdate",
]
