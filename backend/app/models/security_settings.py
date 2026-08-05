"""セキュリティ設定（保持期間・WORM 出力先等）モデル."""

from __future__ import annotations

from typing import Any

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JsonType

from ._mixins import IntPKMixin, TimestampMixin


class SecuritySetting(IntPKMixin, TimestampMixin, Base):
    """キー・バリュー形式のセキュリティ設定.

    例: ``ai_retention_days`` / ``audit_export_dir``。
    """

    __tablename__ = "security_settings"

    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    value: Mapped[dict[str, Any]] = mapped_column(
        JsonType, nullable=False, default=dict, server_default="'{}'::jsonb"
    )
    updated_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<SecuritySetting key={self.key!r}>"
