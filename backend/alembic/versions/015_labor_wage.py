"""労務費基準マスタ（labor_wage_standards）.

Revision ID: 015_labor_wage
Revises: 014_outside_counsel
Create Date: 2026-09-05

ロードマップ #16〜#20 / Issue #111。国交省労務費基準の更新型データ基盤。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "015_labor_wage"
down_revision: str | Sequence[str] | None = "014_outside_counsel"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "labor_wage_standards",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("work_type", sa.String(length=64), nullable=False),
        sa.Column("prefecture", sa.String(length=16), nullable=True),
        sa.Column("amount_jpy", sa.Integer(), nullable=False),
        sa.Column("amount_unit", sa.String(length=16), nullable=False, server_default="日"),
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
        "ck_labor_wage_standards_amount", "labor_wage_standards", "amount_jpy >= 0"
    )
    op.create_check_constraint(
        "ck_labor_wage_standards_period",
        "labor_wage_standards",
        "effective_to IS NULL OR effective_to >= effective_from",
    )
    op.create_index("ix_labor_wage_work_type", "labor_wage_standards", ["work_type"])
    op.create_index("ix_labor_wage_pref", "labor_wage_standards", ["prefecture"])
    op.create_index(
        "ix_labor_wage_effective", "labor_wage_standards", ["effective_from", "effective_to"]
    )


def downgrade() -> None:
    op.drop_index("ix_labor_wage_effective", table_name="labor_wage_standards")
    op.drop_index("ix_labor_wage_pref", table_name="labor_wage_standards")
    op.drop_index("ix_labor_wage_work_type", table_name="labor_wage_standards")
    op.drop_table("labor_wage_standards")
