"""契約義務（contract_obligations）と自動更新列（contracts 拡張）.

Revision ID: 012_obligations
Revises: 011_negotiation
Create Date: 2026-09-05

ロードマップ #9〜#13 / Issue #99（契約義務管理・Obligations Calendar・
条件成就・自動更新判定・終了チェック）。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "012_obligations"
down_revision: str | Sequence[str] | None = "011_negotiation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TYPES = (
    "report",
    "notice",
    "submit",
    "insurance",
    "renewal",
    "condition",
    "closing",
    "other",
)
_STATUSES = ("open", "in_progress", "completed", "waived")


def _in_list(values: Sequence[str]) -> str:
    return "(" + ",".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    # ---- contracts: 自動更新判定用列（#12） ----
    op.add_column(
        "contracts",
        sa.Column(
            "auto_renewal", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )
    op.add_column(
        "contracts",
        sa.Column(
            "renewal_notice_days",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("60"),
        ),
    )
    op.create_check_constraint(
        "ck_contracts_renewal_notice_days",
        "contracts",
        "renewal_notice_days >= 0",
    )

    # ---- contract_obligations: 契約義務（#9/#10/#11/#13） ----
    op.create_table(
        "contract_obligations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("contract_id", sa.BigInteger(), nullable=False),
        sa.Column("obligation_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("assignee_id", sa.BigInteger(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["contract_id"], ["contracts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["assignee_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_check_constraint(
        "ck_contract_obligations_type",
        "contract_obligations",
        f"obligation_type IN {_in_list(_TYPES)}",
    )
    op.create_check_constraint(
        "ck_contract_obligations_status",
        "contract_obligations",
        f"status IN {_in_list(_STATUSES)}",
    )
    op.create_index("ix_obligations_contract", "contract_obligations", ["contract_id"])
    op.create_index("ix_obligations_due_date", "contract_obligations", ["due_date"])
    op.create_index("ix_obligations_status", "contract_obligations", ["status"])
    op.create_index("ix_obligations_type", "contract_obligations", ["obligation_type"])


def downgrade() -> None:
    op.drop_index("ix_obligations_type", table_name="contract_obligations")
    op.drop_index("ix_obligations_status", table_name="contract_obligations")
    op.drop_index("ix_obligations_due_date", table_name="contract_obligations")
    op.drop_index("ix_obligations_contract", table_name="contract_obligations")
    op.drop_table("contract_obligations")
    op.drop_constraint("ck_contracts_renewal_notice_days", "contracts", type_="check")
    op.drop_column("contracts", "renewal_notice_days")
    op.drop_column("contracts", "auto_renewal")
