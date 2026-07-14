"""``attachments`` table model.

Reflects ``docs/database_design.md`` section 4.11. File bytes live in
SharePoint / DirectCloud; this row is the indexed metadata.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

from ._mixins import IntPKMixin, TimestampMixin
from .enums import AttachmentStorage

if TYPE_CHECKING:
    from .contract import Contract
    from .user import User


_ALLOWED_STORAGE = ",".join(f"'{s.value}'" for s in AttachmentStorage)


class Attachment(IntPKMixin, TimestampMixin, Base):
    """File metadata associated with a contract."""

    __tablename__ = "attachments"

    contract_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("contracts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(256), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sharepoint_item_id: Mapped[str] = mapped_column(String(256), nullable=False)
    storage: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="sharepoint",
        server_default="'sharepoint'",
    )
    checksum_sha256: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    uploaded_by: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT", use_alter=True),
        nullable=False,
    )

    contract: Mapped[Contract] = relationship("Contract", back_populates="attachments")
    uploader: Mapped[User] = relationship("User", foreign_keys=[uploaded_by])

    __table_args__ = (
        CheckConstraint("size_bytes >= 0", name="ck_attachments_size_nonneg"),
        CheckConstraint(
            f"storage IN ({_ALLOWED_STORAGE})",
            name="ck_attachments_storage",
        ),
        Index(
            "ix_attachments_contract",
            "contract_id",
            postgresql_where="deleted_at IS NULL",
        ),
        Index(
            "ix_attachments_primary",
            "contract_id",
            postgresql_where="is_primary AND deleted_at IS NULL",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Attachment id={self.id} contract_id={self.contract_id} filename={self.filename!r}>"
        )
