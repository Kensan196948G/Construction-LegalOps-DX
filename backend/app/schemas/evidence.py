"""証拠・eDiscovery 管理 API スキーマ（Phase 3 §5.17 / Issue #124）."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from .common import ORMModel


class EvidenceCreate(BaseModel):
    """証拠登録（#217/#218/#219）."""

    title: str = Field(..., min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=8000)
    source_type: str = Field(default="upload", max_length=16)
    matter_id: int | None = None
    contract_id: int | None = None
    filename: str | None = Field(default=None, max_length=256)
    mime_type: str | None = Field(default=None, max_length=128)
    storage: str = Field(default="local", max_length=32)
    storage_ref: str | None = Field(default=None, max_length=256)
    file_content_base64: str | None = Field(
        default=None,
        max_length=14_000_000,
        description=(
            "小容量ファイル（写真等）を base64 で直接送信する場合。"
            "約 10MB 相当（base64 展開後）を上限とする。"
        ),
    )
    checksum_sha256: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-fA-F]{64}$",
        description="クライアント側で事前計算済みの SHA-256（大容量ファイル用）。",
    )
    collected_by_name: str | None = Field(default=None, max_length=128)
    collected_at: datetime | None = None

    @model_validator(mode="after")
    def _require_content_or_checksum(self) -> EvidenceCreate:
        if not self.file_content_base64 and not self.checksum_sha256:
            raise ValueError("file_content_base64 または checksum_sha256 のいずれかが必要です。")
        return self


class EvidenceOut(ORMModel):
    id: int
    evidence_code: str
    matter_id: int | None
    contract_id: int | None
    title: str
    description: str | None
    source_type: str
    filename: str | None
    mime_type: str | None
    size_bytes: int | None
    storage: str
    storage_ref: str | None
    sha256_hash: str
    is_duplicate: bool
    duplicate_of_id: int | None
    exif_metadata: dict[str, Any] | None
    email_metadata: dict[str, Any] | None
    relevance: str
    relevance_score: int | None
    relevance_note: str | None
    collected_by: int | None
    collected_by_name: str | None
    collected_at: datetime | None
    legal_hold_id: int | None
    is_under_hold: bool
    created_by: int | None
    created_at: datetime
    updated_at: datetime


class EvidenceEmailIngestRequest(BaseModel):
    """メール証拠取込（#226）."""

    raw_eml: str = Field(..., min_length=1, description="RFC 822 形式のメール本文（.eml）。")
    matter_id: int | None = None
    contract_id: int | None = None
    collected_by_name: str | None = Field(default=None, max_length=128)


class EvidenceCustodyEventCreate(BaseModel):
    """Chain of Custody 追記（#220）."""

    action: str = Field(..., max_length=16)
    actor_name: str | None = Field(default=None, max_length=128)
    from_custodian: str | None = Field(default=None, max_length=128)
    to_custodian: str | None = Field(default=None, max_length=128)
    notes: str | None = Field(default=None, max_length=4000)


class EvidenceCustodyEventOut(ORMModel):
    id: int
    evidence_id: int
    action: str
    actor_id: int | None
    actor_name: str | None
    from_custodian: str | None
    to_custodian: str | None
    occurred_at: datetime
    notes: str | None
    previous_hash: str | None
    hash_chain: str


class EvidenceTimelineItem(BaseModel):
    type: str
    occurred_at: datetime
    action: str
    actor_id: int | None
    actor_name: str | None
    from_custodian: str | None
    to_custodian: str | None
    notes: str | None
    hash_chain: str | None


class EvidenceViewHistoryItem(BaseModel):
    id: int
    occurred_at: datetime
    action: str
    actor_id: int | None


class EvidenceExportBundle(BaseModel):
    evidence_code: str
    title: str
    description: str | None
    sha256_hash: str
    source_type: str
    filename: str | None
    mime_type: str | None
    collected_at: str | None
    collected_by_name: str | None
    relevance: str
    relevance_score: int | None
    relevance_note: str | None
    is_duplicate: bool
    duplicate_of_id: int | None
    is_under_hold: bool
    exif_metadata: dict[str, Any] | None
    email_metadata: dict[str, Any] | None
    custody_chain_verified: bool
    timeline: list[dict[str, Any]]
    exported_at: str


class EvidenceLegalHoldLinkRequest(BaseModel):
    legal_hold_id: int


class EvidenceHoldReleaseRequestCreate(BaseModel):
    """Legal Hold 解除申請（#230）."""

    legal_hold_id: int
    reason: str = Field(..., min_length=1, max_length=4000)
    evidence_id: int | None = None


class EvidenceHoldReleaseDecision(BaseModel):
    approve: bool
    decision_note: str | None = Field(default=None, max_length=4000)


class EvidenceHoldReleaseApprovalOut(ORMModel):
    id: int
    legal_hold_id: int
    evidence_id: int | None
    requested_by: int | None
    requested_at: datetime
    reason: str
    status: str
    decided_by: int | None
    decided_at: datetime | None
    decision_note: str | None
    created_at: datetime
    updated_at: datetime
