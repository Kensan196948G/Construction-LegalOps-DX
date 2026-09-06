"""証拠・eDiscovery 管理（evidences / evidence_custody_events /
evidence_hold_release_approvals）.

Revision ID: 025_evidence
Revises: 021_labor_commitment
Create Date: 2026-09-06

Phase 3 §5.17（ロードマップ #217-230）/ Issue #124。

このリビジョンは 021_labor_commitment の直後に連結する。022〜024 は並列
実装中の別 Issue が採番済みのため、本 Issue は 025 を使用する
（コーディネーター指示）。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "025_evidence"
down_revision: str | Sequence[str] | None = "021_labor_commitment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "evidences",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("evidence_code", sa.String(length=32), nullable=False),
        sa.Column("matter_id", sa.BigInteger(), nullable=True),
        sa.Column("contract_id", sa.BigInteger(), nullable=True),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=16), nullable=False, server_default="upload"),
        sa.Column("filename", sa.String(length=256), nullable=True),
        sa.Column("mime_type", sa.String(length=128), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("storage", sa.String(length=32), nullable=False, server_default="local"),
        sa.Column("storage_ref", sa.String(length=256), nullable=True),
        sa.Column("sha256_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("is_duplicate", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("duplicate_of_id", sa.BigInteger(), nullable=True),
        sa.Column("exif_metadata", sa.JSON(), nullable=True),
        sa.Column("email_metadata", sa.JSON(), nullable=True),
        sa.Column("relevance", sa.String(length=16), nullable=False, server_default="unclassified"),
        sa.Column("relevance_score", sa.Integer(), nullable=True),
        sa.Column("relevance_note", sa.Text(), nullable=True),
        sa.Column("collected_by", sa.BigInteger(), nullable=True),
        sa.Column("collected_by_name", sa.String(length=128), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("legal_hold_id", sa.BigInteger(), nullable=True),
        sa.Column("is_under_hold", sa.Boolean(), nullable=False, server_default=sa.false()),
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
        sa.UniqueConstraint("evidence_code", name="uq_evidences_evidence_code"),
        sa.ForeignKeyConstraint(["matter_id"], ["legal_matters.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["duplicate_of_id"], ["evidences.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["collected_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["legal_hold_id"], ["legal_holds.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_check_constraint(
        "ck_evidences_source_type",
        "evidences",
        "source_type IN ('upload', 'email', 'photo', 'scan', 'other')",
    )
    op.create_check_constraint(
        "ck_evidences_relevance",
        "evidences",
        "relevance IN ('unclassified', 'relevant', 'not_relevant', 'privileged')",
    )
    op.create_index("ix_evidences_hash", "evidences", ["sha256_hash"])
    op.create_index("ix_evidences_matter", "evidences", ["matter_id"])
    op.create_index("ix_evidences_contract", "evidences", ["contract_id"])
    op.create_index("ix_evidences_legal_hold", "evidences", ["legal_hold_id"])
    op.create_index("ix_evidences_relevance", "evidences", ["relevance"])

    op.create_table(
        "evidence_custody_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("evidence_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("actor_id", sa.BigInteger(), nullable=True),
        sa.Column("actor_name", sa.String(length=128), nullable=True),
        sa.Column("from_custodian", sa.String(length=128), nullable=True),
        sa.Column("to_custodian", sa.String(length=128), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("previous_hash", sa.CHAR(length=64), nullable=True),
        sa.Column("hash_chain", sa.CHAR(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["evidence_id"], ["evidences.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_check_constraint(
        "ck_evidence_custody_events_action",
        "evidence_custody_events",
        "action IN ('collected', 'received', 'transferred', 'analyzed', 'copied', "
        "'returned', 'destroyed', 'hold_applied', 'hold_released')",
    )
    op.create_index(
        "ix_evidence_custody_events_evidence", "evidence_custody_events", ["evidence_id"]
    )
    op.create_index("ix_evidence_custody_events_time", "evidence_custody_events", ["occurred_at"])

    op.create_table(
        "evidence_hold_release_approvals",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("legal_hold_id", sa.BigInteger(), nullable=False),
        sa.Column("evidence_id", sa.BigInteger(), nullable=True),
        sa.Column("requested_by", sa.BigInteger(), nullable=True),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("decided_by", sa.BigInteger(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["legal_hold_id"], ["legal_holds.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evidence_id"], ["evidences.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_check_constraint(
        "ck_evidence_hold_release_approvals_status",
        "evidence_hold_release_approvals",
        "status IN ('pending', 'approved', 'rejected')",
    )
    op.create_index(
        "ix_evidence_hold_release_approvals_hold",
        "evidence_hold_release_approvals",
        ["legal_hold_id"],
    )
    op.create_index(
        "ix_evidence_hold_release_approvals_status",
        "evidence_hold_release_approvals",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_evidence_hold_release_approvals_status", table_name="evidence_hold_release_approvals"
    )
    op.drop_index(
        "ix_evidence_hold_release_approvals_hold", table_name="evidence_hold_release_approvals"
    )
    op.drop_table("evidence_hold_release_approvals")

    op.drop_index("ix_evidence_custody_events_time", table_name="evidence_custody_events")
    op.drop_index("ix_evidence_custody_events_evidence", table_name="evidence_custody_events")
    op.drop_table("evidence_custody_events")

    op.drop_index("ix_evidences_relevance", table_name="evidences")
    op.drop_index("ix_evidences_legal_hold", table_name="evidences")
    op.drop_index("ix_evidences_contract", table_name="evidences")
    op.drop_index("ix_evidences_matter", table_name="evidences")
    op.drop_index("ix_evidences_hash", table_name="evidences")
    op.drop_table("evidences")
