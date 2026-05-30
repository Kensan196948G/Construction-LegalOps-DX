"""Add pg_trgm full-text search indexes to knowledge_articles.

Revision ID: 003_knowledge_articles_trgm
Revises: 002_knowledge_articles
Create Date: 2026-05-30

Adds GIN trigram indexes on knowledge_articles.title and body for
fast ILIKE / similarity search (Issue #21).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "003_knowledge_articles_trgm"
down_revision: str | Sequence[str] | None = "002_knowledge_articles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enable pg_trgm extension (idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # GIN trigram index on title for fast ILIKE '%keyword%' queries
    op.create_index(
        "ix_knowledge_title_trgm",
        "knowledge_articles",
        ["title"],
        postgresql_using="gin",
        postgresql_ops={"title": "gin_trgm_ops"},
    )

    # GIN trigram index on body for full-text keyword search
    op.create_index(
        "ix_knowledge_body_trgm",
        "knowledge_articles",
        ["body"],
        postgresql_using="gin",
        postgresql_ops={"body": "gin_trgm_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_body_trgm", table_name="knowledge_articles")
    op.drop_index("ix_knowledge_title_trgm", table_name="knowledge_articles")
    # Note: pg_trgm extension is not dropped (may be shared with other tables)
