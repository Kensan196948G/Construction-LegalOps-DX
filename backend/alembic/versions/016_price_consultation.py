"""労務費価格協議・乖離確認ログ（price_consultation_logs）.

Revision ID: 016_price_consultation
Revises: 015_labor_wage
Create Date: 2026-09-05

ロードマップ #21（ダンピング警告確定）・#23（見積変更要求監視）・#24（価格協議履歴）。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "016_price_consultation"
down_revision: str | Sequence[str] | None = "015_labor_wage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "price_consultation_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("log_no", sa.String(length=64), nullable=False),
        sa.Column("direction", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("contract_id", sa.BigInteger(), nullable=True),
        sa.Column("work_type", sa.String(length=64), nullable=False),
        sa.Column("prefecture", sa.String(length=16), nullable=True),
        sa.Column("quote_day_jpy", sa.Integer(), nullable=True),
        sa.Column("summary", sa.String(length=256), nullable=False),
        sa.Column("request_detail", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.Date(), nullable=True),
        sa.Column("standard_day_jpy", sa.Integer(), nullable=True),
        sa.Column("ratio", sa.Float(), nullable=True),
        sa.Column("shortage_rate", sa.Float(), nullable=True),
        sa.Column("severity", sa.String(length=16), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("source_ref", sa.String(length=512), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("response_summary", sa.Text(), nullable=True),
        sa.Column("responded_by", sa.BigInteger(), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
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
        sa.UniqueConstraint("log_no", name="uq_price_consultations_log_no"),
    )
    op.create_check_constraint(
        "ck_price_consultations_direction",
        "price_consultation_logs",
        "direction IN ('from_subcontractor', 'to_subcontractor')",
    )
    op.create_check_constraint(
        "ck_price_consultations_status",
        "price_consultation_logs",
        "status IN ('open', 'responded', 'cancelled')",
    )
    op.create_check_constraint(
        "ck_price_consultations_severity",
        "price_consultation_logs",
        "severity IS NULL OR severity IN ('none', 'watch', 'warning', 'critical')",
    )
    op.create_check_constraint(
        "ck_price_consultations_quote",
        "price_consultation_logs",
        "quote_day_jpy IS NULL OR quote_day_jpy >= 0",
    )
    op.create_index(
        "ix_price_consultations_status", "price_consultation_logs", ["status"]
    )
    op.create_index(
        "ix_price_consultations_contract", "price_consultation_logs", ["contract_id"]
    )
    op.create_index(
        "ix_price_consultations_work_type", "price_consultation_logs", ["work_type"]
    )
    op.create_index(
        "ix_price_consultations_severity", "price_consultation_logs", ["severity"]
    )


def downgrade() -> None:
    op.drop_index("ix_price_consultations_status", table_name="price_consultation_logs")
    op.drop_index("ix_price_consultations_contract", table_name="price_consultation_logs")
    op.drop_index("ix_price_consultations_work_type", table_name="price_consultation_logs")
    op.drop_index("ix_price_consultations_severity", table_name="price_consultation_logs")
    op.drop_table("price_consultation_logs")
