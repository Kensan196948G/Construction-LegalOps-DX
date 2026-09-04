"""契約交渉・Redline 管理（clauses 拡張 + clause_negotiation_events）.

Revision ID: 011_negotiation
Revises: 010_signing
Create Date: 2026-09-05

ロードマップ #5〜#8（Redline 管理／交渉履歴／条項ステータス／条項オーナー）
Issue #98 対応。条項に ``negotiation_status`` / ``clause_owner`` /
``negotiated_text`` を追加し、交渉イベントを追記専用テーブルで証跡化する。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "011_negotiation"
down_revision: str | Sequence[str] | None = "010_signing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEGO_STATUS = ("accepted", "rejected", "negotiating")
_OWNERS = ("法務", "工事", "営業", "購買", "その他")
_ACTIONS = (
    "demand",
    "concession",
    "comment",
    "redline",
    "status_change",
    "owner_change",
)


def upgrade() -> None:
    # ---- clauses: 交渉管理カラム追加（既存行は NULL のまま） ----
    op.add_column(
        "clauses", sa.Column("negotiation_status", sa.String(length=16), nullable=True)
    )
    op.add_column("clauses", sa.Column("clause_owner", sa.String(length=32), nullable=True))
    op.add_column("clauses", sa.Column("negotiated_text", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_clauses_negotiation_status",
        "clauses",
        f"negotiation_status IS NULL OR negotiation_status IN {_in_list(_NEGO_STATUS)}",
    )
    op.create_check_constraint(
        "ck_clauses_clause_owner",
        "clauses",
        f"clause_owner IS NULL OR clause_owner IN {_in_list(_OWNERS)}",
    )
    op.create_index("ix_clauses_nego_status", "clauses", ["negotiation_status"])

    # ---- clause_negotiation_events: 交渉履歴（追記専用） ----
    op.create_table(
        "clause_negotiation_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("contract_id", sa.BigInteger(), nullable=False),
        sa.Column("clause_id", sa.BigInteger(), nullable=True),
        sa.Column("round_no", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("status_from", sa.String(length=16), nullable=True),
        sa.Column("status_to", sa.String(length=16), nullable=True),
        sa.Column("owner_from", sa.String(length=32), nullable=True),
        sa.Column("owner_to", sa.String(length=32), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("proposed_text", sa.Text(), nullable=True),
        sa.Column("actor_id", sa.BigInteger(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["contract_id"], ["contracts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["clause_id"], ["clauses.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], ondelete="SET NULL"
        ),
    )
    op.create_check_constraint(
        "ck_clause_negotiation_events_action",
        "clause_negotiation_events",
        f"action IN {_in_list(_ACTIONS)}",
    )
    op.create_check_constraint(
        "ck_clause_negotiation_events_status_from",
        "clause_negotiation_events",
        f"status_from IS NULL OR status_from IN {_in_list(_NEGO_STATUS)}",
    )
    op.create_check_constraint(
        "ck_clause_negotiation_events_status_to",
        "clause_negotiation_events",
        f"status_to IS NULL OR status_to IN {_in_list(_NEGO_STATUS)}",
    )
    op.create_check_constraint(
        "ck_clause_negotiation_events_owner_from",
        "clause_negotiation_events",
        f"owner_from IS NULL OR owner_from IN {_in_list(_OWNERS)}",
    )
    op.create_check_constraint(
        "ck_clause_negotiation_events_owner_to",
        "clause_negotiation_events",
        f"owner_to IS NULL OR owner_to IN {_in_list(_OWNERS)}",
    )
    op.create_index(
        "ix_nego_events_contract", "clause_negotiation_events", ["contract_id"]
    )
    op.create_index(
        "ix_nego_events_clause", "clause_negotiation_events", ["clause_id"]
    )
    op.create_index("ix_nego_events_action", "clause_negotiation_events", ["action"])


def _in_list(values: Sequence[str]) -> str:
    return "(" + ",".join(f"'{v}'" for v in values) + ")"


def downgrade() -> None:
    op.drop_index("ix_nego_events_action", table_name="clause_negotiation_events")
    op.drop_index("ix_nego_events_clause", table_name="clause_negotiation_events")
    op.drop_index("ix_nego_events_contract", table_name="clause_negotiation_events")
    op.drop_table("clause_negotiation_events")
    op.drop_index("ix_clauses_nego_status", table_name="clauses")
    op.drop_constraint("ck_clauses_clause_owner", "clauses", type_="check")
    op.drop_constraint("ck_clauses_negotiation_status", "clauses", type_="check")
    op.drop_column("clauses", "negotiated_text")
    op.drop_column("clauses", "clause_owner")
    op.drop_column("clauses", "negotiation_status")
