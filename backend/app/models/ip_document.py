"""審査書類の収集・AI 解析結果モデル.

``ip_documents`` — JPO API の書類系エンドポイント（拒絶理由通知書・意見書・
補正書・発送書類）から収集した書類のテキストと AI 解析結果を保持する。
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

from ._mixins import IntPKMixin, TimestampMixin

if TYPE_CHECKING:
    from .ip_asset import IpAsset


class IpDocument(IntPKMixin, TimestampMixin, Base):
    """出願番号に紐づく審査書類とその AI 解析結果."""

    __tablename__ = "ip_documents"

    ip_asset_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("ip_assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    doc_type: Mapped[str] = mapped_column(String(32), nullable=False)
    doc_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_findings: Mapped[dict[str, Any]] = mapped_column(
        JsonType, nullable=False, default=dict, server_default="'{}'::jsonb"
    )
    ai_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    ip_asset: Mapped[IpAsset] = relationship("IpAsset", back_populates="documents")

    __table_args__ = (
        CheckConstraint(
            "doc_type IN ('refusal_reason', 'opinion_amendment', 'decision', 'citation')",
            name="ck_ip_documents_type",
        ),
        Index("ix_ip_documents_asset", "ip_asset_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<IpDocument id={self.id} asset={self.ip_asset_id} type={self.doc_type!r}>"


__all__ = ["IpDocument"]
