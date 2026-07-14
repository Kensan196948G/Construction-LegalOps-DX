"""Add knowledge_articles table.

Revision ID: 002_knowledge_articles
Revises: 001_initial
Create Date: 2026-05-30
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers
revision: str = "002_knowledge_articles"
down_revision: str | Sequence[str] | None = "001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_articles",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("contract_type", sa.String(64), nullable=True),
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            # Must be sa.text(): a plain str is re-quoted by the DDL compiler
            # ('''[]''') and PostgreSQL rejects it as invalid JSON.
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "citations",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "author_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="RESTRICT", use_alter=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_by",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="RESTRICT", use_alter=True),
            nullable=True,
        ),
        sa.Column(
            "updated_by",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="RESTRICT", use_alter=True),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_knowledge_title", "knowledge_articles", ["title"])
    op.create_index("ix_knowledge_contract_type", "knowledge_articles", ["contract_type"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_contract_type", table_name="knowledge_articles")
    op.drop_index("ix_knowledge_title", table_name="knowledge_articles")
    op.drop_table("knowledge_articles")
