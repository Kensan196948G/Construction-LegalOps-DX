"""支払・出来高・検収コンプライアンスの正本イベント（発注/受領/検収/支払）."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

from ._mixins import AuditedByMixin, IntPKMixin, TimestampMixin

if TYPE_CHECKING:
    from .contract import Contract


class PaymentRecord(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """契約ごとの支払関連イベント正本。

    発注日・受領日・検収日・支払日を event として記録し、取適法（旧下請法）の
    60 日・特定建設業者の 50 日期限や、手形等禁止の判定材料にする。
    """

    __tablename__ = "payment_records"

    contract_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("contracts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    record_no: Mapped[str] = mapped_column(String(32), nullable=False)
    record_type: Mapped[str] = mapped_column(String(16), nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount_jpy: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    related_to: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payment_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="scheduled", server_default="'scheduled'"
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    contract: Mapped[Contract] = relationship("Contract", back_populates="payment_records")

    __table_args__ = (
        UniqueConstraint("record_no", name="uq_payment_records_no"),
        CheckConstraint(
            "record_type IN ('order', 'receipt', 'inspection', 'payment', "
            "'withholding', 'credit_note', 'other')",
            name="ck_payment_records_type",
        ),
        CheckConstraint(
            "payment_method IS NULL OR payment_method IN "
            "('bank_transfer', 'promissory_note', 'electronic_bond', 'factoring', 'other')",
            name="ck_payment_records_method",
        ),
        CheckConstraint(
            "status IN ('scheduled', 'paid', 'late', 'checked', 'cancelled')",
            name="ck_payment_records_status",
        ),
        Index("ix_payment_records_contract", "contract_id"),
        Index("ix_payment_records_event_date", "event_date"),
        Index("ix_payment_records_status", "status"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<PaymentRecord id={self.id} no={self.record_no!r} "
            f"type={self.record_type!r} status={self.status!r}>"
        )


__all__ = ["PaymentRecord"]
