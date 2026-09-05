"""労務費コミットメント（labor_commitments）.

Revision ID: 021_labor_commitment
Revises: 020_partner_ext
Create Date: 2026-09-05

ロードマップ #28（コミットメント条項管理）/ Phase 2。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "021_labor_commitment"
down_revision: str | Sequence[str] | None = "020_partner_ext"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "labor_commitments",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("contract_id", sa.BigInteger(), nullable=False),
        sa.Column("commitment_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("statement", sa.Text(), nullable=True),
        sa.Column("confirmed_at", sa.Date(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_by", sa.BigInteger(), nullable=True),
        sa.Column("verify_note", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["verified_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_check_constraint(
        "ck_labor_commitments_type",
        "labor_commitments",
        "commitment_type IN "
        "('wage_payment', 'proper_allocation', 'no_lump_subcontract', 'improvement', 'other')",
    )
    op.create_check_constraint(
        "ck_labor_commitments_status",
        "labor_commitments",
        "status IN ('active', 'fulfilled', 'violated')",
    )
    op.create_index("ix_labor_commitments_contract", "labor_commitments", ["contract_id"])
    op.create_index("ix_labor_commitments_status", "labor_commitments", ["status"])
    op.create_index("ix_labor_commitments_type", "labor_commitments", ["commitment_type"])


def downgrade() -> None:
    op.drop_index("ix_labor_commitments_type", table_name="labor_commitments")
    op.drop_index("ix_labor_commitments_status", table_name="labor_commitments")
    op.drop_index("ix_labor_commitments_contract", table_name="labor_commitments")
    op.drop_table("labor_commitments")
