"""Add ``deepseek`` to the allowed AI provider set (Claude 代替).

Revision ID: 009_ai_provider_deepseek
Revises: 008_contract_type_master
Create Date: 2026-08-14

``ai_provider_settings.provider`` は CHECK 制約
``ck_ai_provider_settings_provider`` で allowed 値を固定している。DeepSeek を
MVP の既定プロバイダとして受け入れるため、制約を drop → 再作成する。
``claude`` は後方互換のため allowed に残す（UI からは非表示）。
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "009_ai_provider_deepseek"
down_revision: str | Sequence[str] | None = "008_contract_type_master"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_ai_provider_settings_provider",
        "ai_provider_settings",
        type_="check",
    )
    op.create_check_constraint(
        "ck_ai_provider_settings_provider",
        "ai_provider_settings",
        "provider IN ('perplexity','claude','deepseek')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_ai_provider_settings_provider",
        "ai_provider_settings",
        type_="check",
    )
    op.create_check_constraint(
        "ck_ai_provider_settings_provider",
        "ai_provider_settings",
        "provider IN ('perplexity','claude')",
    )
