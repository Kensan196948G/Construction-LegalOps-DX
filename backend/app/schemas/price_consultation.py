"""労務費価格協議・乖離確認 API スキーマ（#21/#23/#24）."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import ConsultationDirection

from .common import ORMModel


class PriceConsultationCreate(BaseModel):
    """価格協議ログの登録（#24・申出）."""

    direction: ConsultationDirection
    contract_id: int | None = Field(default=None, description="任意で契約へ紐づけ")
    work_type: str = Field(..., min_length=1, max_length=64)
    prefecture: str | None = Field(default=None, max_length=16)
    quote_day_jpy: int | None = Field(default=None, ge=0, description="協議対象単価（円/日）")
    summary: str = Field(..., min_length=1, max_length=256)
    request_detail: str | None = Field(default=None, max_length=8000)
    requested_at: date | None = None


class PriceConsultationRespond(BaseModel):
    """価格協議への回答（#24・open → responded）."""

    response_summary: str = Field(..., min_length=1, max_length=8000)


class PriceConsultationCancel(BaseModel):
    """価格協議の取下げ（open → cancelled）."""

    reason: str = Field(..., min_length=1, max_length=2000)


class PriceConsultationOut(ORMModel):
    """価格協議ログ 1 件."""

    id: int
    log_no: str
    direction: str
    status: str
    contract_id: int | None
    work_type: str
    prefecture: str | None
    quote_day_jpy: int | None
    summary: str
    request_detail: str | None
    requested_at: date | None
    standard_day_jpy: int | None
    ratio: float | None
    shortage_rate: float | None
    severity: str | None
    effective_from: date | None
    source_ref: str | None
    responded_at: datetime | None
    response_summary: str | None
    responded_by: int | None
    cancel_reason: str | None
    created_by: int | None
    created_at: datetime
    updated_at: datetime


class DumpingCheckOut(BaseModel):
    """#21 ダンピング警告の判定結果（保存はせず即時判定）."""

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
    severity: str  # none / watch / warning / critical
    dumping: bool  # severity in (warning, critical)


__all__ = [
    "DumpingCheckOut",
    "PriceConsultationCancel",
    "PriceConsultationCreate",
    "PriceConsultationOut",
    "PriceConsultationRespond",
]
