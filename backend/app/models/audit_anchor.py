"""監査ログ日次アンカー（WORM 相当外部保管の検証起点）."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    CHAR,
    BigInteger,
    Date,
    DateTime,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

from ._mixins import IntPKMixin


class AuditAnchor(IntPKMixin, Base):
    """1 日 1 行の監査ログ整合性アンカー。

    aggregate_hash は当日イベントのハッシュ連結をさらに SHA-256 した値。
    signature は HASH_CHAIN_SECRET による HMAC-SHA256（16 進）。
    external_sink / external_ref は WORM 相当外部ストレージへの
    書き込み成功時にのみ設定される。
    """

    __tablename__ = "audit_anchors"

    anchor_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_event_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    end_event_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    aggregate_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    signature: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    external_sink: Mapped[str | None] = mapped_column(String(256), nullable=True)
    external_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    anchored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )

    __table_args__ = (
        UniqueConstraint("anchor_date", name="uq_audit_anchors_date"),
        UniqueConstraint("signature", name="uq_audit_anchors_signature"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AuditAnchor date={self.anchor_date} events={self.event_count}>"


__all__ = ["AuditAnchor"]
