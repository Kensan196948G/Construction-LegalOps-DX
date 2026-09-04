"""顧問弁護士・外部法律事務所管理（law_firms / counsel_lawyers / legal_engagements）.

Revision ID: 014_outside_counsel
Revises: 013_matters
Create Date: 2026-09-05

ロードマップ #85〜#96 / Issue #102。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "014_outside_counsel"
down_revision: str | Sequence[str] | None = "013_matters"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STATUSES = ("open", "answered", "confirmed", "cancelled")


def _in_list(values: Sequence[str]) -> str:
    return "(" + ",".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.create_table(
        "law_firms",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("firm_name", sa.String(length=256), nullable=False),
        sa.Column("contact_email", sa.String(length=256), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("address", sa.String(length=512), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
        sa.UniqueConstraint("firm_name", name="uq_law_firms_firm_name"),
    )
    op.create_index("ix_law_firms_active", "law_firms", ["is_active"])

    op.create_table(
        "counsel_lawyers",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("firm_id", sa.BigInteger(), nullable=False),
        sa.Column("lawyer_name", sa.String(length=128), nullable=False),
        sa.Column("email", sa.String(length=256), nullable=True),
        sa.Column("bar_number", sa.String(length=64), nullable=True),
        sa.Column("specialties", sa.String(length=512), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
        sa.ForeignKeyConstraint(["firm_id"], ["law_firms.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_counsel_lawyers_firm", "counsel_lawyers", ["firm_id"])
    op.create_index("ix_counsel_lawyers_active", "counsel_lawyers", ["is_active"])

    op.create_table(
        "legal_engagements",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("engagement_no", sa.String(length=64), nullable=False),
        sa.Column("firm_id", sa.BigInteger(), nullable=False),
        sa.Column("lawyer_id", sa.BigInteger(), nullable=True),
        sa.Column("matter_id", sa.BigInteger(), nullable=True),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("answered_by", sa.BigInteger(), nullable=True),
        sa.Column(
            "conflict_of_interest", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("conflict_note", sa.Text(), nullable=True),
        sa.Column("confidential", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("fee_estimate_jpy", sa.BigInteger(), nullable=True),
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
        sa.ForeignKeyConstraint(["firm_id"], ["law_firms.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["lawyer_id"], ["counsel_lawyers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["matter_id"], ["legal_matters.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["answered_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("engagement_no", name="uq_legal_engagements_no"),
    )
    op.create_check_constraint(
        "ck_legal_engagements_status",
        "legal_engagements",
        f"status IN {_in_list(_STATUSES)}",
    )
    op.create_index("ix_legal_engagements_firm", "legal_engagements", ["firm_id"])
    op.create_index("ix_legal_engagements_status", "legal_engagements", ["status"])
    op.create_index("ix_legal_engagements_matter", "legal_engagements", ["matter_id"])
    op.create_index("ix_legal_engagements_due", "legal_engagements", ["due_date"])


def downgrade() -> None:
    op.drop_index("ix_legal_engagements_due", table_name="legal_engagements")
    op.drop_index("ix_legal_engagements_matter", table_name="legal_engagements")
    op.drop_index("ix_legal_engagements_status", table_name="legal_engagements")
    op.drop_index("ix_legal_engagements_firm", table_name="legal_engagements")
    op.drop_table("legal_engagements")
    op.drop_index("ix_counsel_lawyers_active", table_name="counsel_lawyers")
    op.drop_index("ix_counsel_lawyers_firm", table_name="counsel_lawyers")
    op.drop_table("counsel_lawyers")
    op.drop_index("ix_law_firms_active", table_name="law_firms")
    op.drop_table("law_firms")
