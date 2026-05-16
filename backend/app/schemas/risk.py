"""Risk-item Pydantic schemas.

Mirrors ``docs/api_design.md`` section 8.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

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


__all__ = ["RiskAggregate", "RiskOut", "RiskUpdate"]
