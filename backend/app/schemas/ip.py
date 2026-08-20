"""知財管理・競合ウォッチ・審査書類の API スキーマ.

設計: docs/architecture/ip_management_design.md
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel, TimestampsMixin

IpType = Literal["patent", "design", "trademark"]
WatchStatus = Literal["active", "paused"]
DocType = Literal["refusal_reason", "opinion_amendment", "decision", "citation"]


# ---------------------------------------------------------------------------
# ip_assets
# ---------------------------------------------------------------------------


class IpAssetCreate(BaseModel):
    application_number: str = Field(
        min_length=6, max_length=16, description="出願番号（例: 2026000001）"
    )
    ip_type: IpType = "patent"
    watch_target_id: int | None = None
    notes: str | None = Field(default=None, max_length=4000)


class IpAssetUpdate(BaseModel):
    notes: str | None = Field(default=None, max_length=4000)
    watch_target_id: int | None = None


class IpAssetOut(ORMModel, TimestampsMixin):
    id: int
    application_number: str
    ip_type: str
    invention_title: str | None = None
    filing_date: date | None = None
    applicants: list[dict[str, Any]] = Field(default_factory=list)
    publication_number: str | None = None
    registration_number: str | None = None
    status: str
    progress_data: dict[str, Any] = Field(default_factory=dict)
    registration_data: dict[str, Any] = Field(default_factory=dict)
    jplatpat_url: str | None = None
    last_synced_at: datetime | None = None
    watch_target_id: int | None = None
    notes: str | None = None


class IpAssetSyncResult(BaseModel):
    """同期実行結果（API 呼び出し回数・生成イベント数）。"""

    asset_id: int
    application_number: str
    api_calls: int = 0
    events_created: int = 0
    updated: bool = False
    message: str = ""


# ---------------------------------------------------------------------------
# ip_watch_targets
# ---------------------------------------------------------------------------


class IpWatchTargetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=256, description="競合企業名")
    applicant_code: str | None = Field(default=None, max_length=16)
    ip_types: list[IpType] = Field(default_factory=lambda: ["patent"])  # type: ignore[arg-type]
    status: WatchStatus = "active"
    notes: str | None = Field(default=None, max_length=4000)


class IpWatchTargetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=256)
    applicant_code: str | None = Field(default=None, max_length=16)
    ip_types: list[IpType] | None = None
    status: WatchStatus | None = None
    notes: str | None = Field(default=None, max_length=4000)


class IpWatchTargetOut(ORMModel, TimestampsMixin):
    id: int
    name: str
    applicant_code: str | None = None
    ip_types: list[str] = Field(default_factory=lambda: ["patent"])
    status: str
    notes: str | None = None
    asset_count: int = 0
    unread_event_count: int = 0


class IpWatchTargetSyncResult(BaseModel):
    target_id: int
    name: str
    api_calls: int = 0
    events_created: int = 0
    scanned_assets: int = 0
    message: str = ""


# ---------------------------------------------------------------------------
# ip_watch_events
# ---------------------------------------------------------------------------


class IpWatchEventOut(ORMModel, TimestampsMixin):
    id: int
    watch_target_id: int
    ip_asset_id: int | None = None
    application_number: str | None = None
    event_type: str
    event_code: str | None = None
    description: str | None = None
    event_data: dict[str, Any] = Field(default_factory=dict)
    is_read: bool = False
    detected_at: datetime


# ---------------------------------------------------------------------------
# ip_documents
# ---------------------------------------------------------------------------


class IpDocumentFetchRequest(BaseModel):
    doc_types: list[DocType] = Field(
        default_factory=lambda: [  # type: ignore[arg-type]
            "refusal_reason",
            "opinion_amendment",
            "decision",
        ]
    )


class IpDocumentOut(ORMModel, TimestampsMixin):
    id: int
    ip_asset_id: int
    doc_type: str
    doc_name: str | None = None
    fetched_at: datetime
    content_text: str | None = None
    ai_summary: str | None = None
    ai_findings: dict[str, Any] = Field(default_factory=dict)
    ai_model: str | None = None
    analyzed_at: datetime | None = None
    error: str | None = None


class IpDocumentFetchResult(BaseModel):
    asset_id: int
    application_number: str
    fetched: list[dict[str, str]] = Field(default_factory=list)
    errors: list[dict[str, str]] = Field(default_factory=list)


class IpDocumentAnalyzeResult(BaseModel):
    document_id: int
    doc_type: str
    ai_model: str
    summary: str
    findings: dict[str, Any]
    analyzed_at: datetime


# ---------------------------------------------------------------------------
# dashboard
# ---------------------------------------------------------------------------


class IpDashboardOut(BaseModel):
    total_assets: int = 0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    total_watch_targets: int = 0
    active_watch_targets: int = 0
    unread_events: int = 0
    recent_events: list[IpWatchEventOut] = Field(default_factory=list)
    documents_total: int = 0
    documents_analyzed: int = 0
    api_mode: str = "demo"
    api_configured: bool = False


class JpoStatusOut(BaseModel):
    mode: str
    configured: bool
    base_url: str
    max_calls_per_minute: int


__all__ = [
    "DocType",
    "IpAssetCreate",
    "IpAssetOut",
    "IpAssetSyncResult",
    "IpAssetUpdate",
    "IpDashboardOut",
    "IpDocumentAnalyzeResult",
    "IpDocumentFetchRequest",
    "IpDocumentFetchResult",
    "IpDocumentOut",
    "IpType",
    "IpWatchEventOut",
    "IpWatchTargetCreate",
    "IpWatchTargetOut",
    "IpWatchTargetSyncResult",
    "IpWatchTargetUpdate",
    "JpoStatusOut",
]
