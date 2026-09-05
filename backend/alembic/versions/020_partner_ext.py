"""協力会社拡張（partner_reviews + partner 列追加）.

Revision ID: 020_partner_ext
Revises: 019_joint_venture
Create Date: 2026-09-05

ロードマップ #136〜#152 / Phase 2。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "020_partner_ext"
down_revision: str | Sequence[str] | None = "019_joint_venture"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- Partner への列追加（#146/#150/#151/#152） ---
    op.add_column(
        "partners",
        sa.Column("insurance_expiry", sa.Date(), nullable=True),
    )
    op.add_column(
        "partners",
        sa.Column("risk_score", sa.Integer(), nullable=True),
    )
    op.add_column(
        "partners",
        sa.Column("self_registered", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "partners",
        sa.Column("next_review_due", sa.Date(), nullable=True),
    )

    # --- 定期再審査（#147-#149・#151） ---
    op.create_table(
        "partner_reviews",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("partner_id", sa.BigInteger(), nullable=False),
        sa.Column("review_no", sa.String(length=64), nullable=False),
        sa.Column("review_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("safety_score", sa.Integer(), nullable=True),
        sa.Column("findings", sa.Text(), nullable=True),
        sa.Column("violation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("incident_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("extra_data", sa.JSON(), nullable=True),
        sa.Column("reviewed_at", sa.Date(), nullable=True),
        sa.Column("next_review_due", sa.Date(), nullable=True),
        sa.Column("reviewed_by", sa.BigInteger(), nullable=True),
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
        sa.ForeignKeyConstraint(["partner_id"], ["partners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("review_no", name="uq_partner_reviews_no"),
    )
    op.create_check_constraint(
        "ck_partner_reviews_type",
        "partner_reviews",
        "review_type IN ('periodic', 'incident', 'violation')",
    )
    op.create_check_constraint(
        "ck_partner_reviews_status",
        "partner_reviews",
        "status IN ('open', 'completed')",
    )
    op.create_check_constraint(
        "ck_partner_reviews_safety",
        "partner_reviews",
        "safety_score IS NULL OR (safety_score >= 0 AND safety_score <= 100)",
    )
    op.create_check_constraint(
        "ck_partner_reviews_counts",
        "partner_reviews",
        "violation_count >= 0 AND incident_count >= 0",
    )
    op.create_index("ix_partner_reviews_partner", "partner_reviews", ["partner_id"])
    op.create_index("ix_partner_reviews_status", "partner_reviews", ["status"])
    op.create_index("ix_partner_reviews_next_due", "partner_reviews", ["next_review_due"])


def downgrade() -> None:
    op.drop_index("ix_partner_reviews_next_due", table_name="partner_reviews")
    op.drop_index("ix_partner_reviews_status", table_name="partner_reviews")
    op.drop_index("ix_partner_reviews_partner", table_name="partner_reviews")
    op.drop_table("partner_reviews")
    op.drop_column("partners", "next_review_due")
    op.drop_column("partners", "self_registered")
    op.drop_column("partners", "risk_score")
    op.drop_column("partners", "insurance_expiry")
