"""協力会社定期再審査モデル.

ロードマップ #136〜#152（協力会社コンプライアンス拡張）/ Phase 2。

* ``partner_reviews`` … #151 定期再審査（#147 安全成績・#148 過去トラブル・
  #149 契約違反の記録を含む）。review_type で periodic / incident / violation を
  区分し、completed 時に next_review_due を更新する。

 Partner 本体の拡張（#146 保険証券期限・#150 Risk Score 入力・#152 セルフ登録
フラグ）は本 migration で Partner に列追加する。Risk Score の算出は
``app.services.partner_ext_service`` が既存 ``assess_risk`` と連携して
決定論的に行う（AI 不使用）。
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JsonType

from ._mixins import AuditedByMixin, IntPKMixin, TimestampMixin
from .enums import PartnerReviewStatus, PartnerReviewType

if TYPE_CHECKING:
    from .partner import Partner

_ALLOWED_REVIEW_TYPE = ",".join(f"'{t.value}'" for t in PartnerReviewType)
_ALLOWED_REVIEW_STATUS = ",".join(f"'{s.value}'" for s in PartnerReviewStatus)


class PartnerReview(IntPKMixin, TimestampMixin, AuditedByMixin, Base):
    """協力会社の定期再審査・ incident / violation 記録（#147-#149・#151）."""

    __tablename__ = "partner_reviews"

    partner_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("partners.id", ondelete="CASCADE"),
        nullable=False,
    )
    review_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    review_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=PartnerReviewStatus.OPEN.value
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    # #147 安全成績（0〜100・任意）
    safety_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # #148 過去トラブル / #149 契約違反の記録
    findings: Mapped[str | None] = mapped_column(Text, nullable=True)
    violation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    incident_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extra_data: Mapped[dict[str, object] | None] = mapped_column(JsonType, nullable=True)
    reviewed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_review_due: Mapped[date | None] = mapped_column(Date, nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    partner: Mapped[Partner] = relationship("Partner")

    __table_args__ = (
        CheckConstraint(
            f"review_type IN ({_ALLOWED_REVIEW_TYPE})",
            name="ck_partner_reviews_type",
        ),
        CheckConstraint(
            f"status IN ({_ALLOWED_REVIEW_STATUS})",
            name="ck_partner_reviews_status",
        ),
        CheckConstraint(
            "safety_score IS NULL OR (safety_score >= 0 AND safety_score <= 100)",
            name="ck_partner_reviews_safety",
        ),
        CheckConstraint(
            "violation_count >= 0 AND incident_count >= 0",
            name="ck_partner_reviews_counts",
        ),
        Index("ix_partner_reviews_partner", "partner_id"),
        Index("ix_partner_reviews_status", "status"),
        Index("ix_partner_reviews_next_due", "next_review_due"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<PartnerReview id={self.id} no={self.review_no!r} status={self.status!r}>"


__all__ = ["PartnerReview"]
