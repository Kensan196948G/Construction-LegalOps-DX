"""監査ログ WORM 出力ジョブモデル."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

from ._mixins import IntPKMixin, TimestampMixin

if TYPE_CHECKING:
    from .user import User


class AuditExportJob(IntPKMixin, TimestampMixin, Base):
    """監査ログ外部保存（WORM 相当）ジョブの記録."""

    __tablename__ = "audit_export_jobs"

    job_no: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    exported_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    exported_to: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    record_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", server_default="'pending'"
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )

    creator: Mapped[User | None] = relationship("User")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<AuditExportJob id={self.id} job_no={self.job_no!r} status={self.status!r}>"
