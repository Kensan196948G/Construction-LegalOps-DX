"""契約パッケージ文書モデル（契約書・約款・特記仕様書等）."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

from ._mixins import AuditedByMixin, IntPKMixin, TimestampMixin

if TYPE_CHECKING:
    from .attachment import Attachment
    from .contract import Contract


class ContractDocument(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """一つの契約パッケージを構成する文書。

    priority は小さいほど上位（契約書=1、約款=2、特記仕様書=3…）。
    金額・工期などの矛盾検出（document_consistency）の判定材料になる。
    """

    __tablename__ = "contract_documents"

    contract_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
    )
    doc_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=10, server_default="10")
    doc_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount_jpy: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_attachment_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("attachments.id", ondelete="SET NULL"),
        nullable=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    contract: Mapped[Contract] = relationship("Contract", back_populates="documents")
    source_attachment: Mapped[Attachment | None] = relationship("Attachment")

    __table_args__ = (
        UniqueConstraint("contract_id", "doc_type", "title", name="uq_documents_package"),
        Index("ix_contract_documents_contract", "contract_id"),
        Index("ix_contract_documents_type", "doc_type"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ContractDocument id={self.id} type={self.doc_type!r} title={self.title!r}>"


__all__ = ["ContractDocument"]
