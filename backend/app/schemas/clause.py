"""Contract clause Pydantic schemas.

Mirrors ``docs/api_design.md`` section 5.4 (条項取得).
"""

from __future__ import annotations

from pydantic import Field

from .common import ORMModel


class ClauseOut(ORMModel):
    """Read schema for a single extracted clause."""

    id: int
    contract_id: int
    seq: int = Field(..., ge=1, description="段落番号 / 条項番号")
    title: str | None = None
    text: str
    category: str | None = None
    risk_level: str | None = None


__all__ = ["ClauseOut"]
