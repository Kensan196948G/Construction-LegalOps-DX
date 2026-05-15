"""``notifications`` table model.

Reflects ``docs/database_design.md`` section 4.12.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

from ._mixins import IntPKMixin, TimestampMixin
from .enums import NotificationChannel, NotificationStatus

if TYPE_CHECKING:
    from .contract import Contract
    from .user import User


_ALLOWED_CHANNEL = ",".join(f"'{c.value}'" for c in NotificationChannel)
_ALLOWED_STATUS = ",".join(f"'{s.value}'" for s in NotificationStatus)


class Notification(IntPKMixin, TimestampMixin, Base):
    """Outbound notification to a user via mail/teams/in-app/desknets."""

    __tablename__ = "notifications"

    recipient_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT", use_alter=True),
        nullable=False,
    )
    contract_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("contracts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    subject: Mapped[str] = mapped_column(String(256), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="'{}'::jsonb"
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="queued", server_default="queued"
    )
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    recipient: Mapped["User"] = relationship("User", foreign_keys=[recipient_id])
    contract: Mapped[Optional["Contract"]] = relationship("Contract")

    __table_args__ = (
        CheckConstraint(
            f"channel IN ({_ALLOWED_CHANNEL})",
            name="ck_notifications_channel",
        ),
        CheckConstraint(
            f"status IN ({_ALLOWED_STATUS})",
            name="ck_notifications_status",
        ),
        Index(
            "ix_notif_recipient",
            "recipient_id",
            postgresql_where="deleted_at IS NULL",
        ),
        Index(
            "ix_notif_status",
            "status",
            postgresql_where="deleted_at IS NULL",
        ),
        Index(
            "ix_notif_scheduled",
            "scheduled_at",
            postgresql_where="status = 'queued'",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Notification id={self.id} recipient_id={self.recipient_id} "
            f"channel={self.channel!r}>"
        )
