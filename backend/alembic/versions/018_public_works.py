"""公共工事特化（contracting_agencies / owner_notifications / public_works_consultations）.

Revision ID: 018_public_works
Revises: 017_standard_duration
Create Date: 2026-09-05

ロードマップ #41/#42（発注機関マスタ・機関別契約条件）/ #54（発注者通知期限）/
#55 工期延伸・#56 スライド請求・#57 設計変更（発注者との協議プロセス）。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "018_public_works"
down_revision: str | Sequence[str] | None = "017_standard_duration"
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
    # --- 発注機関マスタ＋機関別契約条件（#41/#42） ---
    op.create_table(
        "contracting_agencies",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("agency_type", sa.String(length=32), nullable=False),
        sa.Column("prefecture", sa.String(length=16), nullable=True),
        sa.Column("contact_email", sa.String(length=256), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("payment_deadline_days", sa.Integer(), nullable=True),
        sa.Column("advance_payment_ratio", sa.Float(), nullable=True),
        sa.Column("warranty_period_months", sa.Integer(), nullable=True),
        sa.Column(
            "requires_slide_clause",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        *_timestamp_columns(),
        sa.UniqueConstraint("code", name="uq_contracting_agencies_code"),
    )
    op.create_check_constraint(
        "ck_contracting_agencies_type",
        "contracting_agencies",
        "agency_type IN ('national', 'prefectural', 'municipal', 'public_corp', 'other')",
    )
    op.create_check_constraint(
        "ck_contracting_agencies_payment_days",
        "contracting_agencies",
        "payment_deadline_days IS NULL OR payment_deadline_days > 0",
    )
    op.create_check_constraint(
        "ck_contracting_agencies_advance",
        "contracting_agencies",
        "advance_payment_ratio IS NULL OR "
        "(advance_payment_ratio >= 0 AND advance_payment_ratio <= 1)",
    )
    op.create_index("ix_contracting_agencies_type", "contracting_agencies", ["agency_type"])
    op.create_index("ix_contracting_agencies_active", "contracting_agencies", ["is_active"])

    # --- 発注者通知期限（#54） ---
    op.create_table(
        "owner_notifications",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("notification_no", sa.String(length=64), nullable=False),
        sa.Column("contract_id", sa.BigInteger(), nullable=True),
        sa.Column("agency_id", sa.BigInteger(), nullable=True),
        sa.Column("notification_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notified_by", sa.BigInteger(), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["contract_id"], ["contracts.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["agency_id"], ["contracting_agencies.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["notified_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("notification_no", name="uq_owner_notifications_no"),
    )
    op.create_check_constraint(
        "ck_owner_notifications_type",
        "owner_notifications",
        "notification_type IN "
        "('design_change', 'delay', 'suspension', 'claim', 'completion', 'other')",
    )
    op.create_check_constraint(
        "ck_owner_notifications_status",
        "owner_notifications",
        "status IN ('open', 'notified', 'cancelled')",
    )
    op.create_index("ix_owner_notifications_status", "owner_notifications", ["status"])
    op.create_index("ix_owner_notifications_contract", "owner_notifications", ["contract_id"])
    op.create_index("ix_owner_notifications_due", "owner_notifications", ["due_date"])

    # --- 発注者との協議プロセス（#55/#56/#57） ---
    op.create_table(
        "public_works_consultations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("consultation_no", sa.String(length=64), nullable=False),
        sa.Column("contract_id", sa.BigInteger(), nullable=True),
        sa.Column("agency_id", sa.BigInteger(), nullable=True),
        sa.Column("consultation_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("claimed_days", sa.Integer(), nullable=True),
        sa.Column("claimed_amount_jpy", sa.BigInteger(), nullable=True),
        sa.Column("resolved_days", sa.Integer(), nullable=True),
        sa.Column("resolved_amount_jpy", sa.BigInteger(), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("response_note", sa.Text(), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["contract_id"], ["contracts.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["agency_id"], ["contracting_agencies.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint("consultation_no", name="uq_public_works_consultations_no"),
    )
    op.create_check_constraint(
        "ck_public_works_consultations_type",
        "public_works_consultations",
        "consultation_type IN "
        "('extension_of_time', 'design_change', 'price_slide', 'suspension', 'other')",
    )
    op.create_check_constraint(
        "ck_public_works_consultations_status",
        "public_works_consultations",
        "status IN ('open', 'responded', 'cancelled')",
    )
    op.create_check_constraint(
        "ck_public_works_consultations_days",
        "public_works_consultations",
        "claimed_days IS NULL OR claimed_days > 0",
    )
    op.create_check_constraint(
        "ck_public_works_consultations_amount",
        "public_works_consultations",
        "claimed_amount_jpy IS NULL OR claimed_amount_jpy >= 0",
    )
    op.create_index(
        "ix_public_works_consultations_status",
        "public_works_consultations",
        ["status"],
    )
    op.create_index(
        "ix_public_works_consultations_type",
        "public_works_consultations",
        ["consultation_type"],
    )
    op.create_index(
        "ix_public_works_consultations_contract",
        "public_works_consultations",
        ["contract_id"],
    )
    op.create_index(
        "ix_public_works_consultations_agency",
        "public_works_consultations",
        ["agency_id"],
    )


def downgrade() -> None:
    op.drop_table("public_works_consultations")
    op.drop_table("owner_notifications")
    op.drop_index("ix_contracting_agencies_active", table_name="contracting_agencies")
    op.drop_index("ix_contracting_agencies_type", table_name="contracting_agencies")
    op.drop_table("contracting_agencies")
