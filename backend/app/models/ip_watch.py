"""競合出願ウォッチのモデル群.

``ip_watch_targets`` — ウォッチ対象（申請人・企業）。
``ip_watch_events`` — 対象出願の経過情報変化を検知したイベント履歴。
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JsonType

from ._mixins import AuditedByMixin, IntPKMixin, TimestampMixin

if TYPE_CHECKING:
    from .ip_asset import IpAsset


class IpWatchTarget(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """競合出願ウォッチ対象（申請人・企業単位）.

    ``applicant_code`` は JPO API の申請人コード。未取得の場合は登録後に
    ``applicant_attorney`` API で解決を試みる。
    """

    __tablename__ = "ip_watch_targets"

    name: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)
    applicant_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    ip_types: Mapped[list[str]] = mapped_column(
        JsonType,
        nullable=False,
        default=lambda: ["patent"],
        server_default="'[\"patent\"]'::jsonb",
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active", server_default="'active'"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    assets: Mapped[list[IpAsset]] = relationship("IpAsset", back_populates="watch_target")
    events: Mapped[list[IpWatchEvent]] = relationship(
        "IpWatchEvent", back_populates="watch_target", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("name", name="uq_ip_watch_targets_name"),
        CheckConstraint(
            "status IN ('active', 'paused')",
            name="ck_ip_watch_targets_status",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<IpWatchTarget id={self.id} name={self.name!r} status={self.status!r}>"


class IpWatchEvent(IntPKMixin, TimestampMixin, Base):
    """ウォッチ検知イベント.

    ``sync_watch_target`` / ``sync_asset`` が経過情報の差分から生成する。
    ``event_type``: new_application / status_change / new_progress /
    registration / publication。
    """

    __tablename__ = "ip_watch_events"

    watch_target_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("ip_watch_targets.id", ondelete="CASCADE"),
        nullable=False,
    )
    ip_asset_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("ip_assets.id", ondelete="SET NULL"),
        nullable=True,
    )
    application_number: Mapped[str | None] = mapped_column(String(16), nullable=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    event_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_data: Mapped[dict[str, Any]] = mapped_column(
        JsonType, nullable=False, default=dict, server_default="'{}'::jsonb"
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    watch_target: Mapped[IpWatchTarget] = relationship("IpWatchTarget", back_populates="events")
    ip_asset: Mapped[IpAsset | None] = relationship("IpAsset", back_populates="watch_events")

    __table_args__ = (
        CheckConstraint(
            "event_type IN ('new_application', 'status_change', 'new_progress', "
            "'registration', 'publication')",
            name="ck_ip_watch_events_type",
        ),
        Index("ix_ip_watch_events_target", "watch_target_id"),
        Index("ix_ip_watch_events_unread", "is_read", postgresql_where="is_read = false"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<IpWatchEvent id={self.id} type={self.event_type!r} "
            f"app={self.application_number!r} read={self.is_read}>"
        )


__all__ = ["IpWatchEvent", "IpWatchTarget"]
