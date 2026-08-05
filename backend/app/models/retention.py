"""保存期間ポリシー / 外部転送アウトボックス（P0-6 対応）."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JsonType

from ._mixins import IntPKMixin, TimestampMixin

if TYPE_CHECKING:
    pass


class RetentionRule(IntPKMixin, TimestampMixin, Base):
    """データ種別ごとの保存期間ルール。"""

    __tablename__ = "retention_rules"

    data_type: Mapped[str] = mapped_column(String(32), nullable=False)
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(
        String(16), nullable=False, default="delete", server_default="'delete'"
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    updated_by: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("data_type", name="uq_retention_rules_type"),
        CheckConstraint(
            "action IN ('delete', 'archive')", name="ck_retention_rules_action"
        ),
    )


class ExternalForwardEvent(IntPKMixin, TimestampMixin, Base):
    """Sentinel / Purview / WORM 等への外部転送イベント（耐久性のあるアウトボックス）。

    payload_hash はペイロードの SHA-256。転送先が未設定の場合は
    status=blocked のまま留まり、false-positive の外部送信を防止する。
    """

    __tablename__ = "external_forward_events"

    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(
        JsonType, nullable=False, default=dict, server_default="'{}'::jsonb"
    )
    payload_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default="'pending'"
    )
    forwarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'sent', 'failed', 'blocked')",
            name="ck_external_forward_status",
        ),
        Index("ix_external_forward_status", "status"),
        Index("ix_external_forward_source", "source_type", "source_id"),
    )


__all__ = ["ExternalForwardEvent", "RetentionRule"]
