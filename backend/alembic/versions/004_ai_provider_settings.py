"""Add ai_provider_settings table (hybrid AI review provider config).

Revision ID: 004_ai_provider_settings
Revises: 003_knowledge_articles_trgm
Create Date: 2026-06-04

Persists per-provider AI integration settings for the hybrid AI review stack
(Issue #28):

* ``perplexity`` — Agent ① contract research (web-grounded, public sources only)
* ``claude``     — Agents ②/③ contract reading-summary + drafting

SECURITY: ``api_key_encrypted`` stores **Fernet ciphertext only**; the plaintext
API key never touches the database. A partial UNIQUE index keeps one *live* row
per provider while allowing soft-deleted history to coexist.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers
revision: str = "004_ai_provider_settings"
down_revision: str | Sequence[str] | None = "003_knowledge_articles_trgm"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_provider_settings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        # Fernet ciphertext of the API key. NULL = key not yet configured.
        sa.Column("api_key_encrypted", sa.Text(), nullable=True),
        # Optional model override (e.g. "sonar", "claude-opus-4-7").
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        # Most-recent "設定テスト" (connection probe) outcome.
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_status", sa.String(16), nullable=True),
        sa.Column("last_test_message", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "provider IN ('perplexity','claude')",
            name="ck_ai_provider_settings_provider",
        ),
        sa.CheckConstraint(
            "last_test_status IS NULL OR last_test_status IN ('ok','failed','unavailable')",
            name="ck_ai_provider_settings_test_status",
        ),
    )

    # One *live* row per provider; soft-deleted rows are excluded so a provider
    # can be reconfigured after logical deletion without a UNIQUE clash.
    op.create_index(
        "ux_ai_provider_settings_provider",
        "ai_provider_settings",
        ["provider"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ux_ai_provider_settings_provider",
        table_name="ai_provider_settings",
    )
    op.drop_table("ai_provider_settings")
