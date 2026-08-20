"""JPO 特許情報取得 API 連携のモデル群.

知財管理（``ip_assets``）、競合出願ウォッチ（``ip_watch_targets`` /
``ip_watch_events``）、審査書類の収集・AI 解析（``ip_documents``）。

設計の詳細は ``docs/architecture/ip_management_design.md`` を参照。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JsonType

from ._mixins import AuditedByMixin, IntPKMixin, TimestampMixin

if TYPE_CHECKING:
    from .ip_document import IpDocument
    from .ip_watch import IpWatchEvent, IpWatchTarget


_ALLOWED_IP_TYPE = ",".join(f"'{t}'" for t in ("patent", "design", "trademark"))


class IpAsset(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """知財台帳（出願単位）.

    ``application_number``（出願番号）をキーに、特許/意匠/商標の出願情報と
    JPO API から取得した経過情報・登録情報・J-PlatPat 固定アドレスを保持する。
    競合ウォッチ対象に紐づく場合は ``watch_target_id`` が設定される。
    """

    __tablename__ = "ip_assets"

    application_number: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    ip_type: Mapped[str] = mapped_column(String(16), nullable=False, default="patent")
    invention_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    filing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    applicants: Mapped[list[dict[str, Any]]] = mapped_column(
        JsonType, nullable=False, default=list, server_default="'[]'::jsonb"
    )
    publication_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    registration_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unknown", server_default="'unknown'"
    )
    progress_data: Mapped[dict[str, Any]] = mapped_column(
        JsonType, nullable=False, default=dict, server_default="'{}'::jsonb"
    )
    registration_data: Mapped[dict[str, Any]] = mapped_column(
        JsonType, nullable=False, default=dict, server_default="'{}'::jsonb"
    )
    jplatpat_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    watch_target_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("ip_watch_targets.id", ondelete="SET NULL"),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    documents: Mapped[list[IpDocument]] = relationship(
        "IpDocument", back_populates="ip_asset", cascade="all, delete-orphan"
    )
    watch_target: Mapped[IpWatchTarget | None] = relationship(
        "IpWatchTarget", back_populates="assets"
    )
    watch_events: Mapped[list[IpWatchEvent]] = relationship(
        "IpWatchEvent", back_populates="ip_asset"
    )

    __table_args__ = (
        CheckConstraint(
            f"ip_type IN ({_ALLOWED_IP_TYPE})",
            name="ck_ip_assets_type",
        ),
        Index(
            "ix_ip_assets_type_status",
            "ip_type",
            "status",
            postgresql_where="deleted_at IS NULL",
        ),
        Index(
            "ix_ip_assets_watch_target",
            "watch_target_id",
            postgresql_where="deleted_at IS NULL",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<IpAsset id={self.id} app_no={self.application_number!r} "
            f"type={self.ip_type!r} status={self.status!r}>"
        )


__all__ = ["IpAsset"]
