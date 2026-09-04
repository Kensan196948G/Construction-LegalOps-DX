"""Legal Matter Management（legal_matters / matter_events / matter_contracts）.

Revision ID: 013_matters
Revises: 012_obligations
Create Date: 2026-09-05

ロードマップ #71〜#84 / Issue #101。契約を越えた法務案件の台帳・
タイムライン・関係契約リンク・Legal Hold 連動を追加する。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "013_matters"
down_revision: str | Sequence[str] | None = "012_obligations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TYPES = ("contract", "dispute", "compliance", "labor", "regulatory", "other")
_STATUSES = ("open", "in_progress", "waiting", "on_hold", "closed")
_PRIORITIES = ("low", "medium", "high", "critical")
_EVENTS = (
    "created",
    "assigned",
    "status_changed",
    "contract_linked",
    "contract_unlinked",
    "legal_hold_linked",
    "legal_hold_unlinked",
    "note",
)


def _in_list(values: Sequence[str]) -> str:
    return "(" + ",".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.create_table(
        "legal_matters",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("matter_no", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("matter_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("priority", sa.String(length=16), nullable=False, server_default="medium"),
        sa.Column("assignee_id", sa.BigInteger(), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=True),
        sa.Column("source_id", sa.BigInteger(), nullable=True),
        sa.Column("legal_hold_case_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "opened_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_note", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["assignee_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["legal_hold_case_id"], ["legal_hold_cases.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("matter_no", name="uq_legal_matters_matter_no"),
    )
    op.create_check_constraint(
        "ck_legal_matters_type",
        "legal_matters",
        f"matter_type IN {_in_list(_TYPES)}",
    )
    op.create_check_constraint(
        "ck_legal_matters_status",
        "legal_matters",
        f"status IN {_in_list(_STATUSES)}",
    )
    op.create_check_constraint(
        "ck_legal_matters_priority",
        "legal_matters",
        f"priority IN {_in_list(_PRIORITIES)}",
    )
    op.create_index("ix_legal_matters_status", "legal_matters", ["status"])
    op.create_index("ix_legal_matters_assignee", "legal_matters", ["assignee_id"])
    op.create_index("ix_legal_matters_type", "legal_matters", ["matter_type"])

    op.create_table(
        "matter_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("matter_id", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
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
        sa.ForeignKeyConstraint(["matter_id"], ["legal_matters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_check_constraint(
        "ck_matter_events_type",
        "matter_events",
        f"event_type IN {_in_list(_EVENTS)}",
    )
    op.create_index("ix_matter_events_matter", "matter_events", ["matter_id"])
    op.create_index("ix_matter_events_type", "matter_events", ["event_type"])

    op.create_table(
        "matter_contracts",
        sa.Column("matter_id", sa.BigInteger(), nullable=False),
        sa.Column("contract_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["matter_id"], ["legal_matters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("matter_id", "contract_id"),
        sa.UniqueConstraint("matter_id", "contract_id", name="uq_matter_contracts_pair"),
    )


def downgrade() -> None:
    op.drop_table("matter_contracts")
    op.drop_index("ix_matter_events_type", table_name="matter_events")
    op.drop_index("ix_matter_events_matter", table_name="matter_events")
    op.drop_table("matter_events")
    op.drop_index("ix_legal_matters_type", table_name="legal_matters")
    op.drop_index("ix_legal_matters_assignee", table_name="legal_matters")
    op.drop_index("ix_legal_matters_status", table_name="legal_matters")
    op.drop_table("legal_matters")
