"""電子契約・電子署名（エンベロープ）モデル.

ロードマップ #1〜#4（電子契約連携／署名ステータス管理／同意証跡／締結正本取込）の
永続化層。``esignature_envelopes`` が 1 契約 1 締結プロセスの状態を持ち、
``esignature_events`` が遷移・承諾の証跡（追記専用運用）を保持する。

設計方針（docs/LEGALOPS_BUSINESS_OS_ROADMAP_2026-09.md §3.2）:
* 電子署名の状態遷移は ``app.services.signing_service`` のルールエンジンが唯一の正。
* ``electronic`` 方式では建設業法 19 条の相手方承諾（電磁的方法による交付の承諾）を
  ``consent_*`` 列と ``consent_received`` イベントとして必ず残す。
* イベントは INSERT 専用とし、UPDATE / DELETE の API を公開しない
  （監査ログの追記専用方針に同じ。DB トリガー強制は監査基盤と同様に後続整備）。
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JsonType

from ._mixins import AuditedByMixin, IntPKMixin, TimestampMixin, VersionedMixin
from .enums import SigningMethod, SigningProviderId, SigningStatus

if TYPE_CHECKING:
    from .attachment import Attachment
    from .contract import Contract
    from .contract_document import ContractDocument
    from .user import User


_ALLOWED_STATUS = ",".join(f"'{s.value}'" for s in SigningStatus)
_ALLOWED_METHOD = ",".join(f"'{m.value}'" for m in SigningMethod)
_ALLOWED_PROVIDER = ",".join(f"'{p.value}'" for p in SigningProviderId)


class ESignatureEnvelope(IntPKMixin, TimestampMixin, VersionedMixin, AuditedByMixin, Base):
    """契約 1 件に対する電子署名（締結）エンベロープ.

    ``envelope_no`` は発番後に ``ES-<id 8桁>`` で確定する（内部 id を基に
    サービス層で採番。ロードマップ #72 の Matter ID 採番と同方針）。
    """

    __tablename__ = "esignature_envelopes"

    contract_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("contracts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    envelope_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=SigningStatus.DRAFT.value
    )
    method: Mapped[str] = mapped_column(
        String(32), nullable=False, default=SigningMethod.ELECTRONIC.value
    )
    provider: Mapped[str] = mapped_column(
        String(32), nullable=False, default=SigningProviderId.DEMO.value
    )
    provider_envelope_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    counterparty_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    counterparty_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # --- 承諾証跡（建設業法 19 条・電磁的方法による交付の相手方承諾） ---
    consent_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    consentor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    consentor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    consent_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # --- 署名プロセス時刻 ---
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    signer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    signer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # --- 締結済み正本（ロードマップ #4 締結済み文書自動取込） ---
    signed_attachment_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("attachments.id", ondelete="SET NULL"),
        nullable=True,
    )
    signed_document_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("contract_documents.id", ondelete="SET NULL"),
        nullable=True,
    )

    contract: Mapped[Contract] = relationship("Contract")
    signed_attachment: Mapped[Attachment | None] = relationship("Attachment")
    signed_document: Mapped[ContractDocument | None] = relationship("ContractDocument")
    events: Mapped[list[ESignatureEvent]] = relationship(
        "ESignatureEvent",
        back_populates="envelope",
        cascade="all, delete-orphan",
        order_by="ESignatureEvent.id",
    )

    __table_args__ = (
        CheckConstraint(
            f"status IN ({_ALLOWED_STATUS})",
            name="status",
        ),
        CheckConstraint(
            f"method IN ({_ALLOWED_METHOD})",
            name="method",
        ),
        CheckConstraint(
            f"provider IN ({_ALLOWED_PROVIDER})",
            name="provider",
        ),
        Index("ix_esignature_envelopes_contract", "contract_id"),
        Index("ix_esignature_envelopes_status", "status"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<ESignatureEnvelope id={self.id} contract_id={self.contract_id} "
            f"status={self.status!r}>"
        )


class ESignatureEvent(IntPKMixin, TimestampMixin, Base):
    """エンベロープの証跡イベント（追記専用・INSERT のみ）.

    例: ``created`` / ``consent_received`` / ``sent`` / ``viewed`` /
    ``signed`` / ``completed`` / ``cancelled``
    """

    __tablename__ = "esignature_events"

    envelope_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("esignature_envelopes.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    payload: Mapped[dict[str, Any] | None] = mapped_column(JsonType, nullable=True)

    envelope: Mapped[ESignatureEnvelope] = relationship(
        "ESignatureEnvelope", back_populates="events"
    )
    actor: Mapped[User | None] = relationship("User")

    __table_args__ = (
        Index("ix_esignature_events_envelope", "envelope_id"),
        Index("ix_esignature_events_type", "event_type"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<ESignatureEvent id={self.id} type={self.event_type!r} "
            f"envelope_id={self.envelope_id}>"
        )


__all__ = ["ESignatureEnvelope", "ESignatureEvent"]
