"""Risk-item Pydantic schemas.

Mirrors ``docs/api_design.md`` section 8.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Dict, Optional

from pydantic import BaseModel, Field

from .common import ORMModel


class RiskOut(ORMModel):
    """Read schema for a single risk item."""

    id: int
    contract_id: int
    severity: Annotated[str, Field(pattern="^(low|medium|high|critical)$")]
    status: Annotated[str, Field(max_length=32)]
    title: str
    description: Optional[str] = None
    mitigation: Optional[str] = None
    owner_id: Optional[int] = None
    department_id: Optional[int] = None
    due_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class RiskUpdate(BaseModel):
    """Patch payload for ``PATCH /risks/{id}``."""

    status: Optional[str] = Field(default=None, max_length=32)
    mitigation: Optional[str] = Field(default=None, max_length=4000)
    severity: Optional[str] = Field(
        default=None, pattern="^(low|medium|high|critical)$"
    )
    owner_id: Optional[int] = None
    due_date: Optional[datetime] = None


class RiskAggregate(BaseModel):
    """Response of ``GET /risks/aggregate``.

    Heat map + per-status counts. Always carries the project disclaimer
    so downstream UIs cannot strip it inadvertently.
    """

    by_severity: Dict[str, int] = Field(default_factory=dict)
    by_status: Dict[str, int] = Field(default_factory=dict)
    open_count: int = Field(default=0, ge=0)
    closed_count: int = Field(default=0, ge=0)
    disclaimer: str = (
        "本リスク評価は AI / ルール出力の参考情報です。最終判断は法務担当者"
        "および顧問弁護士が行ってください。"
    )


__all__ = ["RiskAggregate", "RiskOut", "RiskUpdate"]
