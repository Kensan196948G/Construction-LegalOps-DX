"""JV（共同企業体）管理（joint_ventures / jv_members / jv_agreements / jv_disputes / jv_settlements）.

Revision ID: 019_joint_venture
Revises: 018_public_works
Create Date: 2026-09-05

ロードマップ #61〜#70 / Phase 2。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "019_joint_venture"
down_revision: str | Sequence[str] | None = "018_public_works"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamp_columns() -> list[sa.Column]:
    return [
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
    ]


def upgrade() -> None:
    op.create_table(
        "joint_ventures",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("jv_no", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="prospecting"),
        sa.Column("representative_name", sa.String(length=256), nullable=True),
        sa.Column("works_title", sa.String(length=256), nullable=True),
        sa.Column("contract_id", sa.BigInteger(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("dissolved_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("jv_no", name="uq_joint_ventures_no"),
    )
    op.create_check_constraint(
        "ck_joint_ventures_status",
        "joint_ventures",
        "status IN ('prospecting', 'active', 'completed', 'dissolved')",
    )
    op.create_check_constraint(
        "ck_joint_ventures_period",
        "joint_ventures",
        "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
    )
    op.create_index("ix_joint_ventures_status", "joint_ventures", ["status"])
    op.create_index("ix_joint_ventures_contract", "joint_ventures", ["contract_id"])

    op.create_table(
        "jv_members",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("jv_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False, server_default="member"),
        sa.Column("company_name", sa.String(length=256), nullable=False),
        sa.Column("equity_ratio", sa.Float(), nullable=True),
        sa.Column("profit_share_ratio", sa.Float(), nullable=True),
        sa.Column("contact_email", sa.String(length=256), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["jv_id"], ["joint_ventures.id"], ondelete="CASCADE"),
    )
    op.create_check_constraint(
        "ck_jv_members_role",
        "jv_members",
        "role IN ('representative', 'member')",
    )
    op.create_check_constraint(
        "ck_jv_members_equity",
        "jv_members",
        "equity_ratio IS NULL OR (equity_ratio >= 0 AND equity_ratio <= 100)",
    )
    op.create_check_constraint(
        "ck_jv_members_profit",
        "jv_members",
        "profit_share_ratio IS NULL OR (profit_share_ratio >= 0 AND profit_share_ratio <= 100)",
    )
    op.create_index("ix_jv_members_jv", "jv_members", ["jv_id"])
    op.create_index("ix_jv_members_role", "jv_members", ["role"])

    op.create_table(
        "jv_agreements",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("jv_id", sa.BigInteger(), nullable=False),
        sa.Column("agreement_no", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("signed_at", sa.Date(), nullable=True),
        sa.Column("terminated_at", sa.Date(), nullable=True),
        sa.Column("document_url", sa.String(length=512), nullable=True),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["jv_id"], ["joint_ventures.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("agreement_no", name="uq_jv_agreements_no"),
    )
    op.create_check_constraint(
        "ck_jv_agreements_status",
        "jv_agreements",
        "status IN ('draft', 'signed', 'terminated')",
    )
    op.create_index("ix_jv_agreements_jv", "jv_agreements", ["jv_id"])

    op.create_table(
        "jv_disputes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("jv_id", sa.BigInteger(), nullable=False),
        sa.Column("dispute_no", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("claimant_name", sa.String(length=256), nullable=True),
        sa.Column("respondent_name", sa.String(length=256), nullable=True),
        sa.Column("amount_claimed_jpy", sa.BigInteger(), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("raised_at", sa.Date(), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("response_note", sa.Text(), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["jv_id"], ["joint_ventures.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("dispute_no", name="uq_jv_disputes_no"),
    )
    op.create_check_constraint(
        "ck_jv_disputes_status",
        "jv_disputes",
        "status IN ('open', 'responded', 'cancelled')",
    )
    op.create_check_constraint(
        "ck_jv_disputes_amount",
        "jv_disputes",
        "amount_claimed_jpy IS NULL OR amount_claimed_jpy >= 0",
    )
    op.create_index("ix_jv_disputes_jv", "jv_disputes", ["jv_id"])
    op.create_index("ix_jv_disputes_status", "jv_disputes", ["status"])

    op.create_table(
        "jv_settlements",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("jv_id", sa.BigInteger(), nullable=False),
        sa.Column("settlement_no", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("settled_at", sa.Date(), nullable=True),
        sa.Column("settlement_amount_jpy", sa.BigInteger(), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("recorded_by", sa.BigInteger(), nullable=True),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["jv_id"], ["joint_ventures.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recorded_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("settlement_no", name="uq_jv_settlements_no"),
    )
    op.create_check_constraint(
        "ck_jv_settlements_status",
        "jv_settlements",
        "status IN ('pending', 'settled')",
    )
    op.create_check_constraint(
        "ck_jv_settlements_amount",
        "jv_settlements",
        "settlement_amount_jpy IS NULL OR settlement_amount_jpy >= 0",
    )
    op.create_index("ix_jv_settlements_jv", "jv_settlements", ["jv_id"])


def downgrade() -> None:
    op.drop_table("jv_settlements")
    op.drop_table("jv_disputes")
    op.drop_table("jv_agreements")
    op.drop_table("jv_members")
    op.drop_index("ix_joint_ventures_contract", table_name="joint_ventures")
    op.drop_index("ix_joint_ventures_status", table_name="joint_ventures")
    op.drop_table("joint_ventures")
