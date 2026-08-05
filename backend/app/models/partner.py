"""協力会社コンプライアンス台帳（建設業許可・社会保険・CCUS・反社等）."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JsonType

from ._mixins import AuditedByMixin, IntPKMixin, TimestampMixin

if TYPE_CHECKING:
    pass


class Partner(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """取引先・協力会社の正本台帳。"""

    __tablename__ = "partners"

    name: Mapped[str] = mapped_column(String(256), nullable=False)
    partner_type: Mapped[str] = mapped_column(String(32), nullable=False)
    permit_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    permit_types: Mapped[list[str]] = mapped_column(
        JsonType, nullable=False, default=list, server_default="'[]'::jsonb"
    )
    permit_specific: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    permit_expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    social_insurance_joined: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    ccus_registered: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    ccus_expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    supervisor_qualifications: Mapped[list[str]] = mapped_column(
        JsonType, nullable=False, default=list, server_default="'[]'::jsonb"
    )
    business_evaluation: Mapped[dict[str, object]] = mapped_column(
        JsonType, nullable=False, default=dict, server_default="'{}'::jsonb"
    )
    anti_social_check: Mapped[str] = mapped_column(
        String(16), nullable=False, default="unconfirmed", server_default="'unconfirmed'"
    )
    anti_social_checked_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    bankruptcy_risk: Mapped[str] = mapped_column(
        String(16), nullable=False, default="unknown", server_default="'unknown'"
    )
    insurance_joined: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    re_subcontract: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    last_transaction: Mapped[date | None] = mapped_column(Date, nullable=True)
    risk_level: Mapped[str] = mapped_column(
        String(16), nullable=False, default="low", server_default="'low'"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("name", name="uq_partners_name"),
        CheckConstraint(
            "partner_type IN ('元請', '下請', '専門工事', '材料', '輸送', 'その他')",
            name="ck_partners_type",
        ),
        CheckConstraint(
            "anti_social_check IN ('confirmed', 'unconfirmed', 'pending')",
            name="ck_partners_antisocial",
        ),
        CheckConstraint(
            "bankruptcy_risk IN ('low', 'medium', 'high', 'unknown')",
            name="ck_partners_bankruptcy",
        ),
        CheckConstraint(
            "risk_level IN ('low', 'medium', 'high', 'critical')",
            name="ck_partners_risk",
        ),
        Index("ix_partners_type", "partner_type"),
        Index("ix_partners_permit_expiry", "permit_expiry"),
        Index("ix_partners_risk", "risk_level"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Partner id={self.id} name={self.name!r} type={self.partner_type!r}>"


__all__ = ["Partner"]
