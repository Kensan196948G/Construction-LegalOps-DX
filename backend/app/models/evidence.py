"""証拠・eDiscovery 管理モデル（ロードマップ Phase 3 §5.17 / Issue #124・#217-230）.

* ``evidences`` … 証拠保管庫（Evidence Repository）。Evidence ID 採番・SHA-256
  ハッシュ・EXIF・関連性分類・重複検出フラグを保持する。実ファイルバイト列は
  ``attachments`` と同様に外部ストレージ（SharePoint/DirectCloud/local）が正本
  であり、本テーブルはインデックス済みメタデータを保持する。
* ``evidence_custody_events`` … Chain of Custody（証拠の受け渡し記録）。
  ``audit_logs`` と同様の SHA-256 ハッシュチェーンを証拠単位で保持する追記専用
  ログ（INSERT のみ・UPDATE/DELETE しない）。
* ``evidence_hold_release_approvals`` … Legal Hold 解除承認ワークフロー。
  申請者と決裁者を分離する職務分掌（two-person rule）は
  ``app.services.evidence_service`` が唯一の正とする。

証拠閲覧履歴は専用テーブルを持たず、既存の ``audit_logs``
（``target_type="evidence"``）に統合する（#222・監査ログ基盤の再利用）。
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JsonType

from ._mixins import AuditedByMixin, IntPKMixin, TimestampMixin
from .enums import (
    EvidenceCustodyAction,
    EvidenceHoldApprovalStatus,
    EvidenceRelevance,
    EvidenceSourceType,
)

if TYPE_CHECKING:
    from .access_control import LegalHold
    from .contract import Contract
    from .matter import LegalMatter
    from .user import User

_ALLOWED_SOURCE = ",".join(f"'{s.value}'" for s in EvidenceSourceType)
_ALLOWED_RELEVANCE = ",".join(f"'{r.value}'" for r in EvidenceRelevance)
_ALLOWED_CUSTODY_ACTION = ",".join(f"'{a.value}'" for a in EvidenceCustodyAction)
_ALLOWED_APPROVAL_STATUS = ",".join(f"'{s.value}'" for s in EvidenceHoldApprovalStatus)


class Evidence(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """証拠保管庫の 1 レコード（#217 Evidence Repository・#218 Evidence ID 採番）."""

    __tablename__ = "evidences"

    evidence_code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    matter_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("legal_matters.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    contract_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("contracts.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default=EvidenceSourceType.UPLOAD.value
    )
    filename: Mapped[str | None] = mapped_column(String(256), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    storage: Mapped[str] = mapped_column(String(32), nullable=False, default="local")
    storage_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # #219 証拠ハッシュ（SHA-256・サーバ側計算 or クライアント事前計算値）
    sha256_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)

    # #225 重複ファイル検出
    is_duplicate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    duplicate_of_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("evidences.id", ondelete="SET NULL"),
        nullable=True,
    )

    # #227 写真 EXIF 保持 / #226 メール証拠取込メタデータ
    exif_metadata: Mapped[dict[str, Any] | None] = mapped_column(JsonType, nullable=True)
    email_metadata: Mapped[dict[str, Any] | None] = mapped_column(JsonType, nullable=True)

    # #228 証拠関連性 AI（ルールベース）分類
    relevance: Mapped[str] = mapped_column(
        String(16), nullable=False, default=EvidenceRelevance.UNCLASSIFIED.value
    )
    relevance_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    relevance_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # #221 収集者記録 / #222 収集日時
    collected_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    collected_by_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # #230 Legal Hold 解除承認（既存の汎用 LegalHold と連携）
    legal_hold_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("legal_holds.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    is_under_hold: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    matter: Mapped[LegalMatter | None] = relationship("LegalMatter", viewonly=True)
    contract: Mapped[Contract | None] = relationship("Contract", viewonly=True)
    legal_hold: Mapped[LegalHold | None] = relationship("LegalHold", viewonly=True)
    collector: Mapped[User | None] = relationship(
        "User", foreign_keys=[collected_by], viewonly=True
    )

    __table_args__ = (
        CheckConstraint(f"source_type IN ({_ALLOWED_SOURCE})", name="ck_evidences_source_type"),
        CheckConstraint(f"relevance IN ({_ALLOWED_RELEVANCE})", name="ck_evidences_relevance"),
        Index("ix_evidences_hash", "sha256_hash"),
        Index("ix_evidences_matter", "matter_id"),
        Index("ix_evidences_contract", "contract_id"),
        Index("ix_evidences_legal_hold", "legal_hold_id"),
        Index("ix_evidences_relevance", "relevance"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Evidence id={self.id} code={self.evidence_code!r} title={self.title!r}>"


class EvidenceCustodyEvent(IntPKMixin, Base):
    """Chain of Custody（証拠の受け渡し記録）— 追記専用（#220）.

    ``audit_logs``（``app.models.audit_log.AuditLog``）と同じ設計思想の
    SHA-256 ハッシュチェーンを証拠単位で保持する。ORM 層は常に INSERT のみ
    行い、``session.merge`` / ``session.delete`` を呼んではならない。
    """

    __tablename__ = "evidence_custody_events"

    evidence_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("evidences.id", ondelete="CASCADE"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    actor_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    from_custodian: Mapped[str | None] = mapped_column(String(128), nullable=True)
    to_custodian: Mapped[str | None] = mapped_column(String(128), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    previous_hash: Mapped[str | None] = mapped_column(CHAR(64), nullable=True)
    hash_chain: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    evidence: Mapped[Evidence] = relationship("Evidence", viewonly=True)

    __table_args__ = (
        CheckConstraint(
            f"action IN ({_ALLOWED_CUSTODY_ACTION})", name="ck_evidence_custody_events_action"
        ),
        Index("ix_evidence_custody_events_evidence", "evidence_id"),
        Index("ix_evidence_custody_events_time", "occurred_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<EvidenceCustodyEvent id={self.id} evidence_id={self.evidence_id} "
            f"action={self.action!r}>"
        )


class EvidenceHoldReleaseApproval(IntPKMixin, TimestampMixin, Base):
    """Legal Hold 解除承認申請（#230）.

    申請者（``requested_by``）と決裁者（``decided_by``）の分離（職務分掌）は
    ``app.services.evidence_service.decide_hold_release`` が enforce する。
    """

    __tablename__ = "evidence_hold_release_approvals"

    legal_hold_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("legal_holds.id", ondelete="CASCADE"),
        nullable=False,
    )
    evidence_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("evidences.id", ondelete="CASCADE"),
        nullable=True,
    )
    requested_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=EvidenceHoldApprovalStatus.PENDING.value
    )
    decided_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    legal_hold: Mapped[LegalHold] = relationship("LegalHold", viewonly=True)
    evidence: Mapped[Evidence | None] = relationship("Evidence", viewonly=True)

    __table_args__ = (
        CheckConstraint(
            f"status IN ({_ALLOWED_APPROVAL_STATUS})",
            name="ck_evidence_hold_release_approvals_status",
        ),
        Index("ix_evidence_hold_release_approvals_hold", "legal_hold_id"),
        Index("ix_evidence_hold_release_approvals_status", "status"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<EvidenceHoldReleaseApproval id={self.id} legal_hold_id={self.legal_hold_id} "
            f"status={self.status!r}>"
        )


__all__ = ["Evidence", "EvidenceCustodyEvent", "EvidenceHoldReleaseApproval"]
