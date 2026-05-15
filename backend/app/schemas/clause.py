"""Contract clause Pydantic schemas.

Mirrors ``docs/api_design.md`` section 5.4 (条項取得).
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from .common import ORMModel


class ClauseOut(ORMModel):
    """Read schema for a single extracted clause."""

    id: int
    contract_id: int
    seq: int = Field(..., ge=1, description="段落番号 / 条項番号")
    title: Optional[str] = None
    text: str
    category: Optional[str] = None
    risk_level: Optional[str] = None


__all__ = ["ClauseOut"]
