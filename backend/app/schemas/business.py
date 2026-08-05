"""高優先業務機能・P0-6 関連の Pydantic スキーマ。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any

from pydantic import BaseModel, Field

from .common import ORMModel, TimestampsMixin

# ---------------------------------------------------------------------------
# 支払・出来高・検収コンプライアンス
# ---------------------------------------------------------------------------


class PaymentFindingOut(BaseModel):
    code: str
    severity: str
    message: str
    citation: str
    detail: dict[str, Any] = Field(default_factory=dict)


class PaymentComplianceOut(BaseModel):
    contract_id: int
    order_date: date | None = None
    receipt_date: date | None = None
    inspection_date: date | None = None
    payment_date: date | None = None
    transaction_kind: str | None = None
    is_public_work: bool = False
    law_version: str
    applicable_threshold_days: int
    days_receipt_to_payment: int | None = None
    days_inspection_to_payment: int | None = None
    late_interest_jpy: str = "0"
    overall_status: str
    findings: list[PaymentFindingOut] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 契約パッケージ文書
# ---------------------------------------------------------------------------


class ContractDocumentOut(ORMModel, TimestampsMixin):
    id: int
    contract_id: int
    doc_type: str
    title: str
    priority: int
    doc_date: date | None = None
    amount_jpy: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    content: str | None = None
    source_attachment_id: int | None = None
    version: int


class ContractDocumentCreate(BaseModel):
    doc_type: str
    title: str
    priority: int = 10
    doc_date: date | None = None
    amount_jpy: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    content: str | None = None
    source_attachment_id: int | None = None


class ContractDocumentUpdate(BaseModel):
    doc_type: str | None = None
    title: str | None = None
    priority: int | None = None
    doc_date: date | None = None
    amount_jpy: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    content: str | None = None
    source_attachment_id: int | None = None


class DocumentConsistencyFindingOut(BaseModel):
    code: str
    severity: str
    message: str
    docs: list[str] = Field(default_factory=list)
    detail: dict[str, Any] = Field(default_factory=dict)


class DocumentConsistencyOut(BaseModel):
    contract_id: int
    overall_status: str
    findings: list[DocumentConsistencyFindingOut] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 変更契約・クレーム
# ---------------------------------------------------------------------------


class ChangeOrderOut(ORMModel, TimestampsMixin):
    id: int
    contract_id: int
    change_no: str
    change_type: str
    title: str
    description: str | None = None
    requested_by: str | None = None
    requested_at: date | None = None
    response_deadline: date | None = None
    status: str
    amount_jpy: int | None = None
    schedule_impact_days: int | None = None
    forfeiture_warning: str | None = None
    evidence_summary: dict[str, Any] = Field(default_factory=dict)
    original_amount_jpy: int | None = None
    cumulative_after_jpy: int | None = None


class ChangeOrderCreate(BaseModel):
    change_type: Annotated[
        str,
        Field(
            pattern="^(design_change|additional_work|verbal_direction|schedule_extension|"
            "price_slide|claim|other)$"
        ),
    ]
    title: str = Field(min_length=1, max_length=256)
    description: str | None = None
    requested_by: str | None = None
    requested_at: date | None = None
    response_deadline: date | None = None
    status: str = "registered"
    amount_jpy: int | None = None
    schedule_impact_days: int | None = None
    evidence_summary: dict[str, Any] = Field(default_factory=dict)


class ChangeOrderUpdate(BaseModel):
    change_type: str | None = None
    title: str | None = None
    description: str | None = None
    requested_by: str | None = None
    requested_at: date | None = None
    response_deadline: date | None = None
    status: str | None = None
    amount_jpy: int | None = None
    schedule_impact_days: int | None = None
    evidence_summary: dict[str, Any] | None = None


class ChangeOrderEvidenceOut(ORMModel, TimestampsMixin):
    id: int
    change_order_id: int
    evidence_type: str
    description: str | None = None
    occurred_at: date | None = None
    attachment_id: int | None = None


class ChangeOrderEvidenceCreate(BaseModel):
    evidence_type: Annotated[
        str,
        Field(pattern="^(daily_report|photo|email|minutes|instruction|other)$"),
    ]
    description: str | None = None
    occurred_at: date | None = None
    attachment_id: int | None = None


# ---------------------------------------------------------------------------
# 協力会社台帳
# ---------------------------------------------------------------------------


class PartnerOut(ORMModel, TimestampsMixin):
    id: int
    name: str
    partner_type: str
    permit_number: str | None = None
    permit_types: list[str] = Field(default_factory=list)
    permit_specific: bool | None = None
    permit_expiry: date | None = None
    social_insurance_joined: bool | None = None
    ccus_registered: bool | None = None
    ccus_expiry: date | None = None
    supervisor_qualifications: list[str] = Field(default_factory=list)
    business_evaluation: dict[str, Any] = Field(default_factory=dict)
    anti_social_check: str = "unconfirmed"
    anti_social_checked_at: date | None = None
    bankruptcy_risk: str = "unknown"
    insurance_joined: bool | None = None
    re_subcontract: bool | None = None
    last_transaction: date | None = None
    risk_level: str = "low"
    risk_reasons: list[dict[str, str]] = Field(default_factory=list)
    notes: str | None = None


class PartnerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    partner_type: str
    permit_number: str | None = None
    permit_types: list[str] = Field(default_factory=list)
    permit_specific: bool | None = None
    permit_expiry: date | None = None
    social_insurance_joined: bool | None = None
    ccus_registered: bool | None = None
    ccus_expiry: date | None = None
    supervisor_qualifications: list[str] = Field(default_factory=list)
    business_evaluation: dict[str, Any] = Field(default_factory=dict)
    anti_social_check: str = "unconfirmed"
    anti_social_checked_at: date | None = None
    bankruptcy_risk: str = "unknown"
    insurance_joined: bool | None = None
    re_subcontract: bool | None = None
    last_transaction: date | None = None
    notes: str | None = None


class PartnerUpdate(BaseModel):
    name: str | None = None
    partner_type: str | None = None
    permit_number: str | None = None
    permit_types: list[str] | None = None
    permit_specific: bool | None = None
    permit_expiry: date | None = None
    social_insurance_joined: bool | None = None
    ccus_registered: bool | None = None
    ccus_expiry: date | None = None
    supervisor_qualifications: list[str] | None = None
    business_evaluation: dict[str, Any] | None = None
    anti_social_check: str | None = None
    anti_social_checked_at: date | None = None
    bankruptcy_risk: str | None = None
    insurance_joined: bool | None = None
    re_subcontract: bool | None = None
    last_transaction: date | None = None
    notes: str | None = None


class PartnerSummaryOut(BaseModel):
    total: int
    by_risk_level: dict[str, int] = Field(default_factory=dict)
    antisocial_unconfirmed: int = 0
    permit_expiring_within_90d: int = 0


# ---------------------------------------------------------------------------
# 紛争・事故・債権管理
# ---------------------------------------------------------------------------


class DisputeOut(ORMModel, TimestampsMixin):
    id: int
    dispute_no: str
    contract_id: int | None = None
    dispute_type: str
    title: str
    description: str | None = None
    status: str
    priority: str
    counterparty: str | None = None
    amount_claimed_jpy: int | None = None
    reserve_amount_jpy: int | None = None
    assignee_id: int | None = None
    statute_limitations_date: date | None = None
    notice_deadline: date | None = None
    resolution_method: str = "negotiation"
    legal_hold_id: int | None = None
    exposure: dict[str, Any] = Field(default_factory=dict)
    resolved_at: datetime | None = None


class DisputeCreate(BaseModel):
    dispute_type: Annotated[
        str,
        Field(pattern="^(claim|defect|delay|payment|labor|accident|other)$"),
    ]
    title: str = Field(min_length=1, max_length=256)
    contract_id: int | None = None
    description: str | None = None
    status: str = "open"
    priority: str = "中"
    counterparty: str | None = None
    amount_claimed_jpy: int | None = None
    reserve_amount_jpy: int | None = None
    assignee_id: int | None = None
    statute_limitations_date: date | None = None
    notice_deadline: date | None = None
    resolution_method: str = "negotiation"
    legal_hold_id: int | None = None
    exposure: dict[str, Any] = Field(default_factory=dict)


class DisputeUpdate(BaseModel):
    dispute_type: str | None = None
    title: str | None = None
    contract_id: int | None = None
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    counterparty: str | None = None
    amount_claimed_jpy: int | None = None
    reserve_amount_jpy: int | None = None
    assignee_id: int | None = None
    statute_limitations_date: date | None = None
    notice_deadline: date | None = None
    resolution_method: str | None = None
    legal_hold_id: int | None = None
    exposure: dict[str, Any] | None = None


class DisputeTimelineEventOut(ORMModel, TimestampsMixin):
    id: int
    dispute_id: int
    occurred_at: datetime
    event_type: str
    description: str | None = None


class DisputeTimelineEventCreate(BaseModel):
    event_type: Annotated[
        str,
        Field(pattern="^(fact|notice|hearing|evidence|settlement|escalation|other)$"),
    ]
    occurred_at: datetime | None = None
    description: str | None = None


class DisputeEvidenceOut(ORMModel, TimestampsMixin):
    id: int
    dispute_id: int
    evidence_type: str
    description: str | None = None
    occurred_at: date | None = None
    attachment_id: int | None = None
    preserved: bool = False


class DisputeEvidenceCreate(BaseModel):
    evidence_type: Annotated[
        str,
        Field(pattern="^(contract|email|photo|daily_report|minutes|other)$"),
    ]
    description: str | None = None
    occurred_at: date | None = None
    attachment_id: int | None = None
    preserved: bool = False


class DisputeExposureOut(BaseModel):
    by_status: dict[str, dict[str, int]] = Field(default_factory=dict)
    total_claimed_jpy: int = 0
    total_reserve_jpy: int = 0
    deadlines_within_180d: int = 0


# ---------------------------------------------------------------------------
# P0-6: ACL / Legal Hold / Retention / 監査アンカー / Sentinel
# ---------------------------------------------------------------------------


class AccessControlEntryOut(ORMModel, TimestampsMixin):
    id: int
    contract_id: int
    principal_type: str
    principal_id: str
    access_level: str
    granted_by: int | None = None
    expires_at: datetime | None = None


class AccessControlGrantRequest(BaseModel):
    principal_type: Annotated[
        str,
        Field(pattern="^(user|department|role|external_counsel)$"),
    ]
    principal_id: str = Field(min_length=1, max_length=128)
    access_level: Annotated[
        str,
        Field(pattern="^(read|write|approve|admin)$"),
    ] = "read"
    expires_at: datetime | None = None


class LegalHoldOut(ORMModel, TimestampsMixin):
    id: int
    target_type: str
    target_id: int
    reason: str
    status: str
    started_by: int | None = None
    started_at: datetime
    released_at: datetime | None = None
    released_by: int | None = None
    release_reason: str | None = None
    evidence_ids: list[Any] = Field(default_factory=list)
    ethical_wall: bool = False


class LegalHoldCreate(BaseModel):
    target_type: str = Field(min_length=1, max_length=64)
    target_id: int
    reason: str = Field(min_length=1, max_length=2000)
    evidence_ids: list[Any] = Field(default_factory=list)
    ethical_wall: bool = False


class LegalHoldReleaseRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)


class RetentionRuleOut(ORMModel, TimestampsMixin):
    id: int
    data_type: str
    retention_days: int
    action: str
    enabled: bool
    updated_by: int | None = None
    note: str | None = None


class RetentionRuleUpdate(BaseModel):
    retention_days: int | None = Field(default=None, ge=1)
    action: str | None = Field(default=None, pattern="^(delete|archive)$")
    enabled: bool | None = None
    note: str | None = None


class RetentionRunOut(BaseModel):
    deleted_inputs: int
    deleted_outputs: int
    blocked_by_hold: int


class AuditAnchorOut(BaseModel):
    id: int
    anchor_date: date
    start_event_id: int | None = None
    end_event_id: int | None = None
    event_count: int
    aggregate_hash: str
    signature: str
    external_sink: str | None = None
    external_ref: str | None = None
    anchored_at: datetime


class AuditAnchorVerifyOut(BaseModel):
    ok: bool
    anchor_date: str | None = None
    event_count: int | None = None
    aggregate_hash: str | None = None
    signature_valid: bool | None = None
    external_sink: str | None = None
    external_ref: str | None = None
    detail: str | None = None


class SentinelStatusOut(BaseModel):
    enabled: bool
    configured: bool
    configuration_errors: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 適用法令・根拠検索・改正影響
# ---------------------------------------------------------------------------


class ApplicableLawOut(BaseModel):
    law_code: str
    law_name: str
    applies: bool
    confidence: float
    reason: str
    citation_url: str | None = None


class ApplicableLawResultOut(BaseModel):
    contract_id: int | None = None
    contract_type: str
    laws: list[ApplicableLawOut] = Field(default_factory=list)
    applied: list[ApplicableLawOut] = Field(default_factory=list)


class EvidenceHitOut(BaseModel):
    article_id: int
    title: str
    source_url: str | None = None
    excerpt: str
    law_tags: list[str] = Field(default_factory=list)
    score: float = 0.0
    source_verified: bool = False
    source_kind: str = "knowledge"


class EvidenceLookupOut(BaseModel):
    query: str
    hits: list[EvidenceHitOut] = Field(default_factory=list)
    citation_verification: dict[str, Any] = Field(default_factory=dict)


class LawChangeImpactOut(BaseModel):
    effective_date: str
    law_changes: list[str] = Field(default_factory=list)
    law_change_details: list[dict[str, Any]] = Field(default_factory=list)
    contracts_checked: int
    impacted_contracts: list[dict[str, Any]] = Field(default_factory=list)
    impacted_count: int


__all__ = [
    "AccessControlEntryOut",
    "AccessControlGrantRequest",
    "ApplicableLawOut",
    "ApplicableLawResultOut",
    "AuditAnchorOut",
    "AuditAnchorVerifyOut",
    "ChangeOrderCreate",
    "ChangeOrderEvidenceCreate",
    "ChangeOrderEvidenceOut",
    "ChangeOrderOut",
    "ChangeOrderUpdate",
    "ContractDocumentCreate",
    "ContractDocumentOut",
    "ContractDocumentUpdate",
    "DisputeCreate",
    "DisputeEvidenceCreate",
    "DisputeEvidenceOut",
    "DisputeExposureOut",
    "DisputeOut",
    "DisputeTimelineEventCreate",
    "DisputeTimelineEventOut",
    "DisputeUpdate",
    "DocumentConsistencyFindingOut",
    "DocumentConsistencyOut",
    "EvidenceHitOut",
    "EvidenceLookupOut",
    "LawChangeImpactOut",
    "LegalHoldCreate",
    "LegalHoldOut",
    "LegalHoldReleaseRequest",
    "PartnerCreate",
    "PartnerOut",
    "PartnerSummaryOut",
    "PartnerUpdate",
    "PaymentComplianceOut",
    "PaymentFindingOut",
    "RetentionRuleOut",
    "RetentionRuleUpdate",
    "RetentionRunOut",
    "SentinelStatusOut",
]
