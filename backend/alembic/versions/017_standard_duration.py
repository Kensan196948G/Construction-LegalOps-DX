"""標準工期マスタ（短工期判定用・standard_work_durations）.

Revision ID: 017_standard_duration
Revises: 016_price_consultation
Create Date: 2026-09-05

ロードマップ #22（短工期判定）/ Phase 2。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "017_standard_duration"
down_revision: str | Sequence[str] | None = "016_price_consultation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "standard_work_durations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("work_type", sa.String(length=64), nullable=False),
        sa.Column("prefecture", sa.String(length=16), nullable=True),
        sa.Column("amount_min_jpy", sa.Integer(), nullable=False),
        sa.Column("amount_max_jpy", sa.Integer(), nullable=True),
        sa.Column("standard_days", sa.Integer(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("source_ref", sa.String(length=512), nullable=True),
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
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_check_constraint(
        "ck_standard_durations_amount_min",
        "standard_work_durations",
        "amount_min_jpy >= 0",
    )
    op.create_check_constraint(
        "ck_standard_durations_amount_max",
        "standard_work_durations",
        "amount_max_jpy IS NULL OR amount_max_jpy >= amount_min_jpy",
    )
    op.create_check_constraint(
        "ck_standard_durations_days",
        "standard_work_durations",
        "standard_days > 0",
    )
    op.create_check_constraint(
        "ck_standard_durations_period",
        "standard_work_durations",
        "effective_to IS NULL OR effective_to >= effective_from",
    )
    op.create_index("ix_standard_durations_work_type", "standard_work_durations", ["work_type"])
    op.create_index("ix_standard_durations_pref", "standard_work_durations", ["prefecture"])
    op.create_index(
        "ix_standard_durations_effective",
        "standard_work_durations",
        ["effective_from", "effective_to"],
    )


def downgrade() -> None:
    op.drop_index("ix_standard_durations_effective", table_name="standard_work_durations")
    op.drop_index("ix_standard_durations_pref", table_name="standard_work_durations")
    op.drop_index("ix_standard_durations_work_type", table_name="standard_work_durations")
    op.drop_table("standard_work_durations")
