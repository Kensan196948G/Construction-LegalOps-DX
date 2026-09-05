"""労務費基準マスタ API スキーマ（Issue #111）."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from app.models.enums import LaborWorkType

from .common import ORMModel


class LaborWageStandardCreate(BaseModel):
    work_type: LaborWorkType
    amount_jpy: int = Field(..., ge=0)
    prefecture: str | None = Field(default=None, max_length=16)
    effective_from: date
    effective_to: date | None = None
    amount_unit: str = Field(default="日", max_length=16)
    source_ref: str | None = Field(default=None, max_length=512)


class LaborWageStandardOut(ORMModel):
    id: int
    work_type: str
    prefecture: str | None
    amount_jpy: int
    amount_unit: str
    effective_from: date
    effective_to: date | None
    source_ref: str | None


class LaborWageDiscrepancyOut(BaseModel):
    """#20 乖離率判定結果（#21 ダンピング深刻度を含む）."""

    work_type: str
    prefecture: str | None
    standard_day_jpy: int
    amount_unit: str
    effective_from: date
    source_ref: str | None
    quote_day_jpy: int
    ratio: float
    shortage_rate: float
    status: str  # ok / below
    severity: str = "none"  # #21: none / watch / warning / critical
    dumping: bool = False  # #21: severity が warning 以上 = True（要確認）
