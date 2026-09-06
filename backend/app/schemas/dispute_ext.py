"""紛争・クレーム管理高度化 API スキーマ（ロードマップ #97〜#112 / Issue #121）."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field

from .common import ORMModel

# ---------------------------------------------------------------------------
# #100〜#104 遅延事象台帳・原因分類・追加費用・損害額・EOT
# ---------------------------------------------------------------------------


class DisputeDelayEventCreate(BaseModel):
    cause_category: Annotated[
        str,
        Field(
            pattern="^(owner_caused|contractor_caused|weather|third_party|"
            "force_majeure|design_change|other)$"
        ),
    ]
    title: str = Field(min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=8000)
    occurred_from: date
    occurred_to: date | None = None
    delay_days: int = Field(default=0, ge=0)
    responsible_party: str | None = Field(default=None, max_length=256)
    additional_cost_jpy: int | None = Field(default=None, ge=0)
    damage_amount_jpy: int | None = Field(default=None, ge=0)
    daily_overhead_rate_jpy: int | None = Field(
        default=None,
        ge=0,
        description="損害額の自動算定に用いる日額（未指定なら追加費用のみで算定）",
    )
    eot_days_requested: int | None = Field(default=None, ge=0)


class DisputeDelayEventOut(ORMModel):
    id: int
    dispute_id: int
    cause_category: str
    title: str
    description: str | None = None
    occurred_from: date
    occurred_to: date | None = None
    delay_days: int
    responsible_party: str | None = None
    additional_cost_jpy: int | None = None
    damage_amount_jpy: int | None = None
    eot_days_requested: int | None = None
    eot_days_granted: int | None = None
    eot_status: str
    eot_decided_at: datetime | None = None
    eot_note: str | None = None
    created_at: datetime
    updated_at: datetime


class DisputeDelayEventEotUpdate(BaseModel):
    eot_status: Annotated[str, Field(pattern="^(approved|partial|rejected)$")]
    eot_days_granted: int | None = Field(default=None, ge=0)
    eot_note: str | None = Field(default=None, max_length=4000)


class DisputeDelayCauseSummaryItem(BaseModel):
    cause_category: str
    count: int
    total_delay_days: int
    total_additional_cost_jpy: int
    total_damage_amount_jpy: int


class DisputeDelaySummaryOut(BaseModel):
    dispute_id: int
    by_cause: list[DisputeDelayCauseSummaryItem] = Field(default_factory=list)
    total_delay_days: int = 0
    total_additional_cost_jpy: int = 0
    total_damage_amount_jpy: int = 0
    total_eot_days_granted: int = 0


# ---------------------------------------------------------------------------
# #97 Claim Notice Generator / #98 通知期限自動判定
# ---------------------------------------------------------------------------


class DisputeClaimNoticeRequest(BaseModel):
    sender_name: str = Field(min_length=1, max_length=256)
    recipient_name: str | None = Field(default=None, max_length=256)
    notice_date: date | None = None
    extra_note: str | None = Field(default=None, max_length=4000)


class DisputeClaimNoticeOut(BaseModel):
    dispute_id: int
    subject: str
    recipient: str
    sender: str
    notice_date: date
    notice_deadline: date | None = None
    statute_limitations_date: date | None = None
    formatted_text: str


class DisputeNoticeDeadlineAutoJudgeRequest(BaseModel):
    event_date: date
    override_days: int | None = Field(default=None, gt=0, le=365)
    apply: bool = Field(
        default=False, description="true の場合、算定結果を dispute.notice_deadline へ保存する"
    )


class DisputeNoticeDeadlineAutoJudgeOut(BaseModel):
    dispute_id: int
    dispute_type: str
    event_date: date
    notice_period_days: int
    notice_deadline: date
    applied: bool


# ---------------------------------------------------------------------------
# #99 Time Bar 警告 / #112 消滅時効タイマー
# ---------------------------------------------------------------------------


class DisputeTimeBarAlertOut(BaseModel):
    dispute_id: int
    dispute_no: str
    title: str
    status: str
    statute_limitations_date: date | None = None
    statute_days_remaining: int | None = None
    notice_deadline: date | None = None
    notice_days_remaining: int | None = None
    severity: str  # expired / critical / warning / info


# ---------------------------------------------------------------------------
# #105 証拠充足度スコア / #106 証拠不足検知（ルールベース・AI 不使用）
# ---------------------------------------------------------------------------


class DisputeEvidenceScoreOut(BaseModel):
    dispute_id: int
    score: int = Field(ge=0, le=100)
    required_types: list[str] = Field(default_factory=list)
    present_types: list[str] = Field(default_factory=list)
    missing_types: list[str] = Field(default_factory=list)
    unpreserved_types: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# #107/#108 Claim Chronology（写真・議事録・メール・遅延事象の時系列統合）
# ---------------------------------------------------------------------------


class DisputeChronologyEntryOut(BaseModel):
    source_type: str
    occurred_at: datetime
    title: str
    description: str | None = None
    ref_id: int
    estimated: bool = False


# ---------------------------------------------------------------------------
# #109 主張・反論マトリクス
# ---------------------------------------------------------------------------


class DisputeArgumentPositionCreate(BaseModel):
    issue_no: int = Field(default=1, ge=1)
    issue_title: str = Field(min_length=1, max_length=256)
    party: Annotated[str, Field(pattern="^(ours|counterparty)$")]
    stance: Annotated[str, Field(pattern="^(claim|rebuttal|counter_rebuttal)$")]
    content: str = Field(min_length=1, max_length=8000)
    evidence_refs: list[int] = Field(default_factory=list)


class DisputeArgumentPositionOut(ORMModel):
    id: int
    dispute_id: int
    issue_no: int
    issue_title: str
    party: str
    stance: str
    content: str
    evidence_refs: list[int]
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# #110 和解案比較
# ---------------------------------------------------------------------------


class DisputeSettlementOptionCreate(BaseModel):
    option_no: int = Field(default=1, ge=1)
    title: str = Field(min_length=1, max_length=256)
    settlement_amount_jpy: int | None = Field(default=None, ge=0)
    payment_terms: str | None = Field(default=None, max_length=4000)
    pros: str | None = Field(default=None, max_length=4000)
    cons: str | None = Field(default=None, max_length=4000)
    probability_score: int | None = Field(default=None, ge=0, le=100)
    notes: str | None = Field(default=None, max_length=4000)


class DisputeSettlementOptionUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=256)
    settlement_amount_jpy: int | None = Field(default=None, ge=0)
    payment_terms: str | None = Field(default=None, max_length=4000)
    pros: str | None = Field(default=None, max_length=4000)
    cons: str | None = Field(default=None, max_length=4000)
    probability_score: int | None = Field(default=None, ge=0, le=100)
    status: Annotated[
        str | None,
        Field(default=None, pattern="^(draft|proposed|accepted|rejected|withdrawn)$"),
    ] = None
    notes: str | None = Field(default=None, max_length=4000)


class DisputeSettlementOptionOut(ORMModel):
    id: int
    dispute_id: int
    option_no: int
    title: str
    settlement_amount_jpy: int | None = None
    payment_terms: str | None = None
    pros: str | None = None
    cons: str | None = None
    probability_score: int | None = None
    expected_value_jpy: int | None = None
    status: str
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# #111 訴訟・ADR ステージ管理
# ---------------------------------------------------------------------------


class DisputeProceedingStageCreate(BaseModel):
    stage: Annotated[
        str,
        Field(
            pattern="^(negotiation|mediation|arbitration_filed|arbitration_hearing|"
            "arbitration_award|lawsuit_filed|first_instance|appeal|final_judgment|settled)$"
        ),
    ]
    started_at: date
    ended_at: date | None = None
    forum: str | None = Field(default=None, max_length=256)
    notes: str | None = Field(default=None, max_length=4000)


class DisputeProceedingStageOut(ORMModel):
    id: int
    dispute_id: int
    stage: str
    status: str
    started_at: date
    ended_at: date | None = None
    forum: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


__all__ = [
    "DisputeArgumentPositionCreate",
    "DisputeArgumentPositionOut",
    "DisputeChronologyEntryOut",
    "DisputeClaimNoticeOut",
    "DisputeClaimNoticeRequest",
    "DisputeDelayCauseSummaryItem",
    "DisputeDelayEventCreate",
    "DisputeDelayEventEotUpdate",
    "DisputeDelayEventOut",
    "DisputeDelaySummaryOut",
    "DisputeEvidenceScoreOut",
    "DisputeNoticeDeadlineAutoJudgeOut",
    "DisputeNoticeDeadlineAutoJudgeRequest",
    "DisputeProceedingStageCreate",
    "DisputeProceedingStageOut",
    "DisputeSettlementOptionCreate",
    "DisputeSettlementOptionOut",
    "DisputeSettlementOptionUpdate",
    "DisputeTimeBarAlertOut",
]
