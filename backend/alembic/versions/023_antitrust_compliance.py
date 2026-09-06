"""独禁法・入札談合コンプライアンス（antitrust_checks / antitrust_prior_applications /
antitrust_consultations / compliance_trainings）.

Revision ID: 023_antitrust_compliance
Revises: 021_labor_commitment
Create Date: 2026-09-06

ロードマップ #113〜#124（Issue #122）/ Phase 3 §5.9。

.. note::
   このリポジトリでは複数の Issue が並行して migration を作成しているため、
   ``down_revision`` は本ワークツリー上の最新ヘッド（``021_labor_commitment``）
   を指す。022 系（別 Issue）が先にマージされた場合、統合担当が
   ``down_revision`` を実際のヘッドへ張り替えること（内容の変更は不要）。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "023_antitrust_compliance"
down_revision: str | Sequence[str] | None = "021_labor_commitment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # -----------------------------------------------------------------
    # antitrust_checks — #113/#114/#117/#118/#119 決定論的ルールベースチェック
    # -----------------------------------------------------------------
    op.create_table(
        "antitrust_checks",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("check_no", sa.String(length=64), nullable=False, unique=True),
        sa.Column("check_type", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False, server_default="info"),
        sa.Column("subject", sa.String(length=256), nullable=False),
        sa.Column("contract_id", sa.BigInteger(), nullable=True),
        sa.Column("jv_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "input_context",
            sa.JSON(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "findings",
            sa.JSON(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "checked_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["jv_id"], ["joint_ventures.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_check_constraint(
        "ck_antitrust_checks_type",
        "antitrust_checks",
        "check_type IN "
        "('general', 'bid_rigging', 'price_exchange', 'jv_formation', 'joint_research')",
    )
    op.create_check_constraint(
        "ck_antitrust_checks_severity",
        "antitrust_checks",
        "severity IN ('info', 'warn', 'block')",
    )
    op.create_index("ix_antitrust_checks_type", "antitrust_checks", ["check_type"])
    op.create_index("ix_antitrust_checks_severity", "antitrust_checks", ["severity"])
    op.create_index("ix_antitrust_checks_contract", "antitrust_checks", ["contract_id"])
    op.create_index("ix_antitrust_checks_jv", "antitrust_checks", ["jv_id"])

    # -----------------------------------------------------------------
    # antitrust_prior_applications — #115/#116/#121/#122/#123
    # -----------------------------------------------------------------
    op.create_table(
        "antitrust_prior_applications",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("application_no", sa.String(length=64), nullable=False, unique=True),
        sa.Column("application_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="submitted"),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("counterparty_name", sa.String(length=256), nullable=True),
        sa.Column("counterparty_organization", sa.String(length=256), nullable=True),
        sa.Column("purpose", sa.Text(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("location", sa.String(length=256), nullable=True),
        sa.Column("amount_jpy", sa.BigInteger(), nullable=True),
        sa.Column("attendees", sa.JSON(), nullable=True),
        sa.Column("contract_id", sa.BigInteger(), nullable=True),
        sa.Column("jv_id", sa.BigInteger(), nullable=True),
        sa.Column("approved_by", sa.BigInteger(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome_note", sa.Text(), nullable=True),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["jv_id"], ["joint_ventures.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_check_constraint(
        "ck_antitrust_applications_type",
        "antitrust_prior_applications",
        "application_type IN "
        "('competitor_contact', 'meeting_social', 'entertainment_gift', "
        "'public_official_contact', 'donation_sponsorship')",
    )
    op.create_check_constraint(
        "ck_antitrust_applications_status",
        "antitrust_prior_applications",
        "status IN ('submitted', 'approved', 'rejected', 'completed', 'cancelled')",
    )
    op.create_check_constraint(
        "ck_antitrust_applications_amount",
        "antitrust_prior_applications",
        "amount_jpy IS NULL OR amount_jpy >= 0",
    )
    op.create_index(
        "ix_antitrust_applications_type", "antitrust_prior_applications", ["application_type"]
    )
    op.create_index("ix_antitrust_applications_status", "antitrust_prior_applications", ["status"])

    # -----------------------------------------------------------------
    # antitrust_consultations — #120 競争法 AI 相談
    # -----------------------------------------------------------------
    op.create_table(
        "antitrust_consultations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("citations", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("contract_id", sa.BigInteger(), nullable=True),
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
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_antitrust_consultations_contract", "antitrust_consultations", ["contract_id"]
    )

    # -----------------------------------------------------------------
    # compliance_trainings — #124 コンプライアンス研修履歴
    # -----------------------------------------------------------------
    op.create_table(
        "compliance_trainings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("attendee_name", sa.String(length=256), nullable=True),
        sa.Column("training_title", sa.String(length=256), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False, server_default="antitrust"),
        sa.Column("completed_at", sa.Date(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("certificate_url", sa.String(length=512), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_check_constraint(
        "ck_compliance_trainings_score",
        "compliance_trainings",
        "score IS NULL OR (score >= 0 AND score <= 100)",
    )
    op.create_index("ix_compliance_trainings_user", "compliance_trainings", ["user_id"])
    op.create_index("ix_compliance_trainings_category", "compliance_trainings", ["category"])
    op.create_index("ix_compliance_trainings_completed", "compliance_trainings", ["completed_at"])


def downgrade() -> None:
    op.drop_index("ix_compliance_trainings_completed", table_name="compliance_trainings")
    op.drop_index("ix_compliance_trainings_category", table_name="compliance_trainings")
    op.drop_index("ix_compliance_trainings_user", table_name="compliance_trainings")
    op.drop_table("compliance_trainings")

    op.drop_index("ix_antitrust_consultations_contract", table_name="antitrust_consultations")
    op.drop_table("antitrust_consultations")

    op.drop_index("ix_antitrust_applications_status", table_name="antitrust_prior_applications")
    op.drop_index("ix_antitrust_applications_type", table_name="antitrust_prior_applications")
    op.drop_table("antitrust_prior_applications")

    op.drop_index("ix_antitrust_checks_jv", table_name="antitrust_checks")
    op.drop_index("ix_antitrust_checks_contract", table_name="antitrust_checks")
    op.drop_index("ix_antitrust_checks_severity", table_name="antitrust_checks")
    op.drop_index("ix_antitrust_checks_type", table_name="antitrust_checks")
    op.drop_table("antitrust_checks")
