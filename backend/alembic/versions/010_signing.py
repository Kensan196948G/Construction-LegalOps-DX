"""電子契約・電子署名エンベロープ（esignature_envelopes / esignature_events）.

Revision ID: 010_signing
Revises: 009_ip_management
Create Date: 2026-09-04

ロードマップ #1〜#4（電子契約連携／署名ステータス管理／同意証跡／締結正本取込）。
ステータス遷移の正は ``app.services.signing_service``。CHECK 制約は
``app.models.signing`` と同一値を列挙する。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "010_signing"
down_revision: str | Sequence[str] | None = "009_ip_management"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_SIGNING_STATUSES = ("draft", "sent", "viewed", "signed", "completed", "cancelled")
_SIGNING_METHODS = ("electronic", "paper")
_SIGNING_PROVIDERS = ("cloudsign", "docusign", "demo", "manual")


def _in_list(values: Sequence[str]) -> str:
    """``('a','b')`` 形式の CHECK 制約値を生成する."""
    return "(" + ",".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.create_table(
        "esignature_envelopes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("contract_id", sa.BigInteger(), nullable=False),
        sa.Column("envelope_no", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "method",
            sa.String(length=32),
            nullable=False,
            server_default="electronic",
        ),
        sa.Column(
            "provider",
            sa.String(length=32),
            nullable=False,
            server_default="demo",
        ),
        sa.Column("provider_envelope_id", sa.String(length=128), nullable=True),
        sa.Column("counterparty_name", sa.String(length=255), nullable=True),
        sa.Column("counterparty_email", sa.String(length=255), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("consent_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consentor_name", sa.String(length=255), nullable=True),
        sa.Column("consentor_email", sa.String(length=255), nullable=True),
        sa.Column("consent_note", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("signer_name", sa.String(length=255), nullable=True),
        sa.Column("signer_email", sa.String(length=255), nullable=True),
        sa.Column("signed_attachment_id", sa.BigInteger(), nullable=True),
        sa.Column("signed_document_id", sa.BigInteger(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
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
            ["contract_id"], ["contracts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["signed_attachment_id"], ["attachments.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["signed_document_id"], ["contract_documents.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "envelope_no", name="uq_esignature_envelopes_envelope_no"
        ),
        sa.CheckConstraint(
            f"status IN {_in_list(_SIGNING_STATUSES)}",
            name="status",
        ),
        sa.CheckConstraint(
            f"method IN {_in_list(_SIGNING_METHODS)}",
            name="method",
        ),
        sa.CheckConstraint(
            f"provider IN {_in_list(_SIGNING_PROVIDERS)}",
            name="provider",
        ),
    )
    op.create_index(
        "ix_esignature_envelopes_contract", "esignature_envelopes", ["contract_id"]
    )
    op.create_index(
        "ix_esignature_envelopes_status", "esignature_envelopes", ["status"]
    )

    op.create_table(
        "esignature_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("envelope_id", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.BigInteger(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
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
            ["envelope_id"], ["esignature_envelopes.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "ix_esignature_events_envelope", "esignature_events", ["envelope_id"]
    )
    op.create_index(
        "ix_esignature_events_type", "esignature_events", ["event_type"]
    )


def downgrade() -> None:
    op.drop_index("ix_esignature_events_type", table_name="esignature_events")
    op.drop_index("ix_esignature_events_envelope", table_name="esignature_events")
    op.drop_table("esignature_events")
    op.drop_index("ix_esignature_envelopes_status", table_name="esignature_envelopes")
    op.drop_index("ix_esignature_envelopes_contract", table_name="esignature_envelopes")
    op.drop_table("esignature_envelopes")
