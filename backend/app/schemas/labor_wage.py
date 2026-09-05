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


# ---------------------------------------------------------------- #22 標準工期 ---
class StandardWorkDurationCreate(BaseModel):
    """標準工期マスタの登録（#22・更新型で履歴蓄積）."""

    work_type: str = Field(..., min_length=1, max_length=64)
    prefecture: str | None = Field(default=None, max_length=16)
    amount_min_jpy: int = Field(..., ge=0)
    amount_max_jpy: int | None = Field(default=None, ge=0)
    standard_days: int = Field(..., ge=1)
    effective_from: date
    effective_to: date | None = None
    source_ref: str | None = Field(default=None, max_length=512)


class StandardWorkDurationOut(ORMModel):
    id: int
    work_type: str
    prefecture: str | None
    amount_min_jpy: int
    amount_max_jpy: int | None
    standard_days: int
    effective_from: date
    effective_to: date | None
    source_ref: str | None


class ShortDurationCheckOut(BaseModel):
    """#22 短工期判定結果."""

    work_type: str
    prefecture: str | None
    amount_min_jpy: int
    amount_max_jpy: int | None
    standard_days: int
    planned_days: int
    ratio: float
    shorten_rate: float
    status: str  # ok / short
    severity: str  # none / watch / warning / critical
    effective_from: date
    source_ref: str | None


# ------------------------------------------------- #25/#26 価格転嫁シミュレータ ---
class PriceSimulatorIn(BaseModel):
    """価格転嫁シミュレーションの入力（#26・スライド試算 #25 と同一式）."""

    contract_amount_jpy: int = Field(..., ge=0)
    labor_cost_jpy: int = Field(..., ge=0)
    material_cost_jpy: int = Field(..., ge=0)
    labor_change_rate: float = Field(..., ge=-1.0, description="例 0.08 = 8% 上昇")
    material_change_rate: float = Field(..., ge=-1.0)
    pass_through_rate: float = Field(..., ge=0.0, le=1.0, description="転嫁率 0〜1")


class PriceSimulatorOut(BaseModel):
    contract_amount_jpy: int
    labor_cost_jpy: int
    material_cost_jpy: int
    labor_change_rate: float
    material_change_rate: float
    pass_through_rate: float
    labor_delta_jpy: int
    material_delta_jpy: int
    total_delta_jpy: int
    pass_through_amount_jpy: int
    adjusted_amount_jpy: int
    direction: str  # up / down / flat
