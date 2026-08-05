"""SQLAlchemy declarative base and common column mixins."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, MetaData, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Consistent constraint naming convention for Alembic autogenerate.
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Project-wide declarative base."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# JSONB の可搬型エイリアス: PostgreSQL では JSONB、SQLite では JSON。
# モデル定義を単一に保ちつつ、SQLite の create_all / ローカルテストでも
# テーブル生成を可能にする。
JsonType = JSON().with_variant(JSONB, "postgresql")

# INET の可搬型エイリアス（SQLite は VARCHAR(45) で代替）。
InetType = INET().with_variant(String(45), "sqlite")

# UUID の可搬型エイリアス: PostgreSQL では native UUID、SQLite では CHAR(32)。
UuidType = Uuid(as_uuid=True)

# TEXT[] の可搬型エイリアス（SQLite は JSON 配列で代替）。
ArrayTextType = ARRAY(Text).with_variant(JSON, "sqlite")


class UUIDPrimaryKeyMixin:
    """Adds a UUID v4 primary key column named ``id``."""

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )


class TimestampMixin:
    """Adds ``created_at`` and ``updated_at`` columns (UTC, server default)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    """Adds a nullable ``deleted_at`` column for logical deletion."""

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )


__all__ = [
    "NAMING_CONVENTION",
    "ArrayTextType",
    "Base",
    "InetType",
    "JsonType",
    "SoftDeleteMixin",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
    "UuidType",
]
