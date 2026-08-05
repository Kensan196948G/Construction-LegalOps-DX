"""``contracts`` table model.

Reflects ``docs/database_design.md`` section 4.3 and ``api_design.md``
section 5. ``contracts`` is the central business entity; most other tables
have a FK to it.

Notable invariants enforced by CHECK constraints:

* ``amount IS NULL OR amount >= 0``
* ``end_date IS NULL OR start_date IS NULL OR end_date >= start_date``
* ``status`` and ``confidentiality`` are constrained to known values.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JsonType

from ._mixins import AuditedByMixin, IntPKMixin, TimestampMixin
from .enums import Confidentiality, ContractStatus

if TYPE_CHECKING:
    from .access_control import AccessControlEntry
    from .attachment import Attachment
    from .change_order import ChangeOrder
    from .clause import Clause
    from .comment import Comment
    from .contract_document import ContractDocument
    from .legal_review import LegalReview
    from .payment_record import PaymentRecord
    from .risk_item import RiskItem
    from .workflow import WorkflowStep


_ALLOWED_STATUS = ",".join(f"'{s.value}'" for s in ContractStatus)
_ALLOWED_CONF = ",".join(f"'{c.value}'" for c in Confidentiality)


class Contract(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """Construction-industry contract record.

    The ``contract_no`` is a human-readable identifier (e.g. ``C-2026-000123``)
    assigned at creation; numeric ``id`` is the internal primary key.
    """

    __tablename__ = "contracts"

    contract_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    counterparty: Mapped[str] = mapped_column(String(256), nullable=False)
    contract_type: Mapped[str] = mapped_column(String(64), nullable=False)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    currency: Mapped[str] = mapped_column(
        CHAR(3), nullable=False, default="JPY", server_default="'JPY'"
    )
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    department_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    drafter_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT", use_alter=True),
        nullable=False,
    )
    confidentiality: Mapped[str] = mapped_column(
        String(16), nullable=False, default="normal", server_default="'normal'"
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="draft", server_default="'draft'"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    sharepoint_item_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    # --- 法令適用・支払コンプライアンスの正本項目（評価 P0-1/P0-2/P0-3 対応） ---
    order_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    receipt_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    inspection_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    payment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    transaction_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_public_work: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    handles_personal_data: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    our_capital_jpy: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    counterparty_capital_jpy: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    our_employees: Mapped[int | None] = mapped_column(Integer, nullable=True)
    counterparty_employees: Mapped[int | None] = mapped_column(Integer, nullable=True)
    case_category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ethical_wall: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JsonType,
        nullable=False,
        default=dict,
        server_default="'{}'::jsonb",
    )

    # --- Relationships -----------------------------------------------------
    clauses: Mapped[list[Clause]] = relationship(
        "Clause", back_populates="contract", cascade="all, delete-orphan"
    )
    legal_reviews: Mapped[list[LegalReview]] = relationship(
        "LegalReview", back_populates="contract", cascade="all, delete-orphan"
    )
    risk_items: Mapped[list[RiskItem]] = relationship(
        "RiskItem", back_populates="contract", cascade="all, delete-orphan"
    )
    attachments: Mapped[list[Attachment]] = relationship(
        "Attachment", back_populates="contract", cascade="all, delete-orphan"
    )
    comments: Mapped[list[Comment]] = relationship(
        "Comment", back_populates="contract", cascade="all, delete-orphan"
    )
    workflow_steps: Mapped[list[WorkflowStep]] = relationship(
        "WorkflowStep", back_populates="contract", cascade="all, delete-orphan"
    )
    access_entries: Mapped[list[AccessControlEntry]] = relationship(
        "AccessControlEntry", back_populates="contract", cascade="all, delete-orphan"
    )
    documents: Mapped[list[ContractDocument]] = relationship(
        "ContractDocument", back_populates="contract", cascade="all, delete-orphan"
    )
    change_orders: Mapped[list[ChangeOrder]] = relationship(
        "ChangeOrder", back_populates="contract", cascade="all, delete-orphan"
    )
    payment_records: Mapped[list[PaymentRecord]] = relationship(
        "PaymentRecord", back_populates="contract", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "amount IS NULL OR amount >= 0",
            name="ck_contracts_amount_nonneg",
        ),
        CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name="ck_contracts_date_order",
        ),
        CheckConstraint(
            f"status IN ({_ALLOWED_STATUS})",
            name="ck_contracts_status",
        ),
        CheckConstraint(
            f"confidentiality IN ({_ALLOWED_CONF})",
            name="ck_contracts_confidentiality",
        ),
        CheckConstraint(
            "case_category IS NULL OR case_category IN "
            "('normal', 'hr', 'bid_rigging', 'whistleblowing', 'legal')",
            name="ck_contracts_case_category",
        ),
        CheckConstraint(
            "transaction_kind IS NULL OR transaction_kind IN "
            "('manufacturing', 'repair', 'information', 'service', 'transport', 'construction')",
            name="ck_contracts_transaction_kind",
        ),
        CheckConstraint(
            "payment_date IS NULL OR receipt_date IS NULL OR payment_date >= receipt_date",
            name="ck_contracts_payment_after_receipt",
        ),
        CheckConstraint(
            "inspection_date IS NULL OR receipt_date IS NULL OR inspection_date >= receipt_date",
            name="ck_contracts_inspection_after_receipt",
        ),
        Index(
            "ix_contracts_status",
            "status",
            postgresql_where="deleted_at IS NULL",
        ),
        Index(
            "ix_contracts_department",
            "department_id",
            postgresql_where="deleted_at IS NULL",
        ),
        Index(
            "ix_contracts_drafter",
            "drafter_id",
            postgresql_where="deleted_at IS NULL",
        ),
        Index(
            "ix_contracts_dates",
            "start_date",
            "end_date",
            postgresql_where="deleted_at IS NULL",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Contract id={self.id} no={self.contract_no!r} status={self.status!r}>"
