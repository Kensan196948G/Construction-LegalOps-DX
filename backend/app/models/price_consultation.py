"""労務費価格協議・乖離確認（ダンピング警告）モデル.

ロードマップ #21（ダンピング警告確定）・#23（見積変更要求監視）・#24（価格協議履歴）。

* ``price_consultation_logs`` … 労務費に関する価格協議の申出〜回答の証跡。
  契約に紐づかず「工種 × 単価」を記録できる軽量な証跡とし、契約があれば
  任意で ``contract_id`` に紐づける。
  - direction: 下請→元請の引上げ協議申出（from_subcontractor）／
    元請→下請の価格確認・引下げ要求（to_subcontractor）
  - status: open（回答待ち）→ responded（回答済み・証跡確定）／ cancelled（取下げ）
  - 乖離率・深刻度はサービス層のルールエンジンが「基準日時点の最新値」を
    解決して決定論的に算出・保存する（AI 不使用）。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

from ._mixins import AuditedByMixin, IntPKMixin, TimestampMixin
from .enums import ConsultationDirection, ConsultationStatus, DumpingSeverity

if TYPE_CHECKING:
    from .contract import Contract


_ALLOWED_DIRECTION = ",".join(f"'{d.value}'" for d in ConsultationDirection)
_ALLOWED_STATUS = ",".join(f"'{s.value}'" for s in ConsultationStatus)
_ALLOWED_SEVERITY = ",".join(f"'{s.value}'" for s in DumpingSeverity)


class PriceConsultationLog(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """労務費価格協議 1 件（申出〜回答の証跡・#24）."""

    __tablename__ = "price_consultation_logs"

    log_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    direction: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ConsultationStatus.OPEN.value
    )
    # 任意で契約へ紐づけ（契約が無い単価協議も記録可能）
    contract_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("contracts.id", ondelete="SET NULL"),
        nullable=True,
    )
    work_type: Mapped[str] = mapped_column(String(64), nullable=False)
    prefecture: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # 協議対象単価（円/日 など・基準単価との乖離判定に使用）
    quote_day_jpy: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 協議内容（申出の理由・要求内容 等）
    summary: Mapped[str] = mapped_column(String(256), nullable=False)
    request_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    # --- 乖離判定スナップショット（#20/#21/#23・記録時点の基準で算出）---
    standard_day_jpy: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    shortage_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    severity: Mapped[str | None] = mapped_column(
        String(16), nullable=True, default=DumpingSeverity.NONE.value
    )
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # --- 回答（#24・responded への遷移時に記録）---
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    response_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    responded_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    contract: Mapped[Contract | None] = relationship("Contract")

    __table_args__ = (
        CheckConstraint(
            f"direction IN ({_ALLOWED_DIRECTION})",
            name="ck_price_consultations_direction",
        ),
        CheckConstraint(
            f"status IN ({_ALLOWED_STATUS})",
            name="ck_price_consultations_status",
        ),
        CheckConstraint(
            f"severity IN ({_ALLOWED_SEVERITY})",
            name="ck_price_consultations_severity",
        ),
        CheckConstraint(
            "quote_day_jpy IS NULL OR quote_day_jpy >= 0",
            name="ck_price_consultations_quote",
        ),
        Index("ix_price_consultations_status", "status"),
        Index("ix_price_consultations_contract", "contract_id"),
        Index("ix_price_consultations_work_type", "work_type"),
        Index("ix_price_consultations_severity", "severity"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<PriceConsultationLog id={self.id} log_no={self.log_no!r} "
            f"status={self.status!r} severity={self.severity!r}>"
        )


__all__ = ["PriceConsultationLog"]
