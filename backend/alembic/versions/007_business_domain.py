"""高優先業務機能（紛争・変更契約・協力会社・支払・文書パッケージ）のテーブル群 + PostgreSQL RLS.

Revision ID: 007_business_domain
Revises: 006_security_rls
Create Date: 2026-08-05

追加:
- contracts に法令適用・支払コンプライアンスの正本カラム
- access_control_entries / legal_holds / audit_anchors
- contract_documents / change_orders / change_order_evidence
- partners / disputes / dispute_timeline_events / dispute_evidence
- payment_records / document_consistency_results
- retention_rules / external_forward_events
- PostgreSQL のみ RLS (CREATE POLICY / ENABLE ROW LEVEL SECURITY)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "007_business_domain"
down_revision: str | Sequence[str] | None = "006_security_rls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _pk() -> sa.Column:
    return sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False)


def _audit_cols() -> tuple[sa.Column, ...]:
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )


def upgrade() -> None:
    bind = op.get_bind()

    # ------------------------------------------------------------------
    # contracts 正本カラム
    # ------------------------------------------------------------------
    op.add_column(
        "contracts",
        sa.Column("order_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "contracts",
        sa.Column("receipt_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "contracts",
        sa.Column("inspection_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "contracts",
        sa.Column("payment_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "contracts",
        sa.Column("transaction_kind", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "contracts",
        sa.Column("is_public_work", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "contracts",
        sa.Column("handles_personal_data", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "contracts",
        sa.Column("our_capital_jpy", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "contracts",
        sa.Column("counterparty_capital_jpy", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "contracts",
        sa.Column("our_employees", sa.Integer(), nullable=True),
    )
    op.add_column(
        "contracts",
        sa.Column("counterparty_employees", sa.Integer(), nullable=True),
    )
    op.add_column(
        "contracts",
        sa.Column("case_category", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "contracts",
        sa.Column("ethical_wall", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    # ------------------------------------------------------------------
    # access_control_entries
    # ------------------------------------------------------------------
    op.create_table(
        "access_control_entries",
        _pk(),
        sa.Column("contract_id", sa.BigInteger(), nullable=False),
        sa.Column("principal_type", sa.String(length=16), nullable=False),
        sa.Column("principal_id", sa.String(length=128), nullable=False),
        sa.Column("access_level", sa.String(length=16), nullable=False, server_default="read"),
        sa.Column("granted_by", sa.BigInteger(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["granted_by"], ["users.id"], ondelete="SET NULL", use_alter=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("contract_id", "principal_type", "principal_id", name="uq_access_entries_scope"),
        sa.CheckConstraint(
            "principal_type IN ('user', 'department', 'role', 'external_counsel')",
            name="ck_access_entries_principal_type",
        ),
        sa.CheckConstraint(
            "access_level IN ('read', 'write', 'approve', 'admin')",
            name="ck_access_entries_access_level",
        ),
    )
    op.create_index("ix_access_entries_contract", "access_control_entries", ["contract_id"])
    op.create_index(
        "ix_access_entries_principal", "access_control_entries", ["principal_type", "principal_id"]
    )

    # ------------------------------------------------------------------
    # legal_holds
    # ------------------------------------------------------------------
    op.create_table(
        "legal_holds",
        _pk(),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("started_by", sa.BigInteger(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_by", sa.BigInteger(), nullable=True),
        sa.Column("release_reason", sa.Text(), nullable=True),
        sa.Column("evidence_ids", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("ethical_wall", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["started_by"], ["users.id"], ondelete="SET NULL", use_alter=True),
        sa.ForeignKeyConstraint(["released_by"], ["users.id"], ondelete="SET NULL", use_alter=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("status IN ('active', 'released')", name="ck_legal_holds_status"),
    )
    op.create_index("ix_legal_holds_target", "legal_holds", ["target_type", "target_id"])
    op.create_index("ix_legal_holds_status", "legal_holds", ["status"])

    # ------------------------------------------------------------------
    # audit_anchors
    # ------------------------------------------------------------------
    op.create_table(
        "audit_anchors",
        _pk(),
        sa.Column("anchor_date", sa.Date(), nullable=False),
        sa.Column("start_event_id", sa.BigInteger(), nullable=True),
        sa.Column("end_event_id", sa.BigInteger(), nullable=True),
        sa.Column("event_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("aggregate_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("signature", sa.CHAR(length=64), nullable=False),
        sa.Column("external_sink", sa.String(length=256), nullable=True),
        sa.Column("external_ref", sa.String(length=512), nullable=True),
        sa.Column("anchored_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("anchor_date", name="uq_audit_anchors_date"),
        sa.UniqueConstraint("signature", name="uq_audit_anchors_signature"),
    )

    # ------------------------------------------------------------------
    # contract_documents
    # ------------------------------------------------------------------
    op.create_table(
        "contract_documents",
        _pk(),
        sa.Column("contract_id", sa.BigInteger(), nullable=False),
        sa.Column("doc_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("doc_date", sa.Date(), nullable=True),
        sa.Column("amount_jpy", sa.BigInteger(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("source_attachment_id", sa.BigInteger(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        *_audit_cols(),
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_attachment_id"], ["attachments.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("contract_id", "doc_type", "title", name="uq_documents_package"),
    )
    op.create_index("ix_contract_documents_contract", "contract_documents", ["contract_id"])
    op.create_index("ix_contract_documents_type", "contract_documents", ["doc_type"])

    # ------------------------------------------------------------------
    # change_orders / change_order_evidence
    # ------------------------------------------------------------------
    op.create_table(
        "change_orders",
        _pk(),
        sa.Column("contract_id", sa.BigInteger(), nullable=False),
        sa.Column("change_no", sa.String(length=32), nullable=False),
        sa.Column("change_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("requested_by", sa.String(length=128), nullable=True),
        sa.Column("requested_at", sa.Date(), nullable=True),
        sa.Column("response_deadline", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="registered"),
        sa.Column("amount_jpy", sa.BigInteger(), nullable=True),
        sa.Column("schedule_impact_days", sa.Integer(), nullable=True),
        sa.Column("forfeiture_warning", sa.Text(), nullable=True),
        sa.Column("evidence_summary", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("original_amount_jpy", sa.BigInteger(), nullable=True),
        sa.Column("cumulative_after_jpy", sa.BigInteger(), nullable=True),
        *_audit_cols(),
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("contract_id", "change_no", name="uq_change_orders_no"),
        sa.CheckConstraint(
            "change_type IN ('design_change', 'additional_work', 'verbal_direction', "
            "'schedule_extension', 'price_slide', 'claim', 'other')",
            name="ck_change_orders_type",
        ),
        sa.CheckConstraint(
            "status IN ('registered', 'notice_sent', 'in_consultation', 'approved', "
            "'rejected', 'forfeited')",
            name="ck_change_orders_status",
        ),
    )
    op.create_index("ix_change_orders_contract", "change_orders", ["contract_id"])
    op.create_index("ix_change_orders_status", "change_orders", ["status"])
    op.create_index("ix_change_orders_deadline", "change_orders", ["response_deadline"])

    op.create_table(
        "change_order_evidence",
        _pk(),
        sa.Column("change_order_id", sa.BigInteger(), nullable=False),
        sa.Column("evidence_type", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.Date(), nullable=True),
        sa.Column("attachment_id", sa.BigInteger(), nullable=True),
        *_audit_cols(),
        sa.ForeignKeyConstraint(["change_order_id"], ["change_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["attachment_id"], ["attachments.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "evidence_type IN ('daily_report', 'photo', 'email', 'minutes', "
            "'instruction', 'other')",
            name="ck_change_order_evidence_type",
        ),
    )
    op.create_index("ix_change_order_evidence_order", "change_order_evidence", ["change_order_id"])

    # ------------------------------------------------------------------
    # partners
    # ------------------------------------------------------------------
    op.create_table(
        "partners",
        _pk(),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("partner_type", sa.String(length=32), nullable=False),
        sa.Column("permit_number", sa.String(length=64), nullable=True),
        sa.Column("permit_types", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("permit_specific", sa.Boolean(), nullable=True),
        sa.Column("permit_expiry", sa.Date(), nullable=True),
        sa.Column("social_insurance_joined", sa.Boolean(), nullable=True),
        sa.Column("ccus_registered", sa.Boolean(), nullable=True),
        sa.Column("ccus_expiry", sa.Date(), nullable=True),
        sa.Column("supervisor_qualifications", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("business_evaluation", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("anti_social_check", sa.String(length=16), nullable=False, server_default="unconfirmed"),
        sa.Column("anti_social_checked_at", sa.Date(), nullable=True),
        sa.Column("bankruptcy_risk", sa.String(length=16), nullable=False, server_default="unknown"),
        sa.Column("insurance_joined", sa.Boolean(), nullable=True),
        sa.Column("re_subcontract", sa.Boolean(), nullable=True),
        sa.Column("last_transaction", sa.Date(), nullable=True),
        sa.Column("risk_level", sa.String(length=16), nullable=False, server_default="low"),
        sa.Column("notes", sa.Text(), nullable=True),
        *_audit_cols(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_partners_name"),
        sa.CheckConstraint(
            "partner_type IN ('元請', '下請', '専門工事', '材料', '輸送', 'その他')",
            name="ck_partners_type",
        ),
        sa.CheckConstraint(
            "anti_social_check IN ('confirmed', 'unconfirmed', 'pending')",
            name="ck_partners_antisocial",
        ),
        sa.CheckConstraint(
            "bankruptcy_risk IN ('low', 'medium', 'high', 'unknown')",
            name="ck_partners_bankruptcy",
        ),
        sa.CheckConstraint(
            "risk_level IN ('low', 'medium', 'high', 'critical')",
            name="ck_partners_risk",
        ),
    )
    op.create_index("ix_partners_type", "partners", ["partner_type"])
    op.create_index("ix_partners_permit_expiry", "partners", ["permit_expiry"])
    op.create_index("ix_partners_risk", "partners", ["risk_level"])

    # ------------------------------------------------------------------
    # disputes / timeline / evidence
    # ------------------------------------------------------------------
    op.create_table(
        "disputes",
        _pk(),
        sa.Column("dispute_no", sa.String(length=32), nullable=False),
        sa.Column("contract_id", sa.BigInteger(), nullable=True),
        sa.Column("dispute_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="open"),
        sa.Column("priority", sa.String(length=4), nullable=False, server_default="中"),
        sa.Column("counterparty", sa.String(length=256), nullable=True),
        sa.Column("amount_claimed_jpy", sa.BigInteger(), nullable=True),
        sa.Column("reserve_amount_jpy", sa.BigInteger(), nullable=True),
        sa.Column("assignee_id", sa.BigInteger(), nullable=True),
        sa.Column("statute_limitations_date", sa.Date(), nullable=True),
        sa.Column("notice_deadline", sa.Date(), nullable=True),
        sa.Column("resolution_method", sa.String(length=32), nullable=False, server_default="negotiation"),
        sa.Column("legal_hold_id", sa.BigInteger(), nullable=True),
        sa.Column("exposure", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_cols(),
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assignee_id"], ["users.id"], ondelete="SET NULL", use_alter=True),
        sa.ForeignKeyConstraint(["legal_hold_id"], ["legal_holds.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dispute_no", name="uq_disputes_no"),
        sa.CheckConstraint(
            "dispute_type IN ('claim', 'defect', 'delay', 'payment', 'labor', "
            "'accident', 'other')",
            name="ck_disputes_type",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'investigating', 'escalated', 'resolved', 'closed')",
            name="ck_disputes_status",
        ),
        sa.CheckConstraint("priority IN ('高', '中', '低')", name="ck_disputes_priority"),
        sa.CheckConstraint(
            "resolution_method IN ('negotiation', 'mediation', 'arbitration', 'lawsuit', "
            "'construction_dispute_review', 'other')",
            name="ck_disputes_resolution",
        ),
    )
    op.create_index("ix_disputes_status", "disputes", ["status"])
    op.create_index("ix_disputes_contract", "disputes", ["contract_id"])
    op.create_index(
        "ix_disputes_deadlines", "disputes", ["statute_limitations_date", "notice_deadline"]
    )

    op.create_table(
        "dispute_timeline_events",
        _pk(),
        sa.Column("dispute_id", sa.BigInteger(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        *_audit_cols(),
        sa.ForeignKeyConstraint(["dispute_id"], ["disputes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "event_type IN ('fact', 'notice', 'hearing', 'evidence', 'settlement', "
            "'escalation', 'other')",
            name="ck_dispute_timeline_type",
        ),
    )
    op.create_index("ix_dispute_timeline_dispute", "dispute_timeline_events", ["dispute_id", "occurred_at"])

    op.create_table(
        "dispute_evidence",
        _pk(),
        sa.Column("dispute_id", sa.BigInteger(), nullable=False),
        sa.Column("evidence_type", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.Date(), nullable=True),
        sa.Column("attachment_id", sa.BigInteger(), nullable=True),
        sa.Column("preserved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        *_audit_cols(),
        sa.ForeignKeyConstraint(["dispute_id"], ["disputes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["attachment_id"], ["attachments.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "evidence_type IN ('contract', 'email', 'photo', 'daily_report', 'minutes', "
            "'other')",
            name="ck_dispute_evidence_type",
        ),
    )
    op.create_index("ix_dispute_evidence_dispute", "dispute_evidence", ["dispute_id"])

    # ------------------------------------------------------------------
    # retention_rules / external_forward_events
    # ------------------------------------------------------------------
    op.create_table(
        "retention_rules",
        _pk(),
        sa.Column("data_type", sa.String(length=32), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False, server_default="delete"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("data_type", name="uq_retention_rules_type"),
        sa.CheckConstraint("action IN ('delete', 'archive')", name="ck_retention_rules_action"),
    )

    op.create_table(
        "external_forward_events",
        _pk(),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.BigInteger(), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("payload_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("forwarded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('pending', 'sent', 'failed', 'blocked')",
            name="ck_external_forward_status",
        ),
    )
    op.create_index("ix_external_forward_status", "external_forward_events", ["status"])
    op.create_index(
        "ix_external_forward_source", "external_forward_events", ["source_type", "source_id"]
    )

    # ------------------------------------------------------------------
    # payment_records（発注/受領/検収/支払の正本イベント）
    # ------------------------------------------------------------------
    op.create_table(
        "payment_records",
        _pk(),
        sa.Column("contract_id", sa.BigInteger(), nullable=False),
        sa.Column("record_no", sa.String(length=32), nullable=False),
        sa.Column("record_type", sa.String(length=16), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("amount_jpy", sa.BigInteger(), nullable=True),
        sa.Column("related_to", sa.String(length=128), nullable=True),
        sa.Column("payment_due_date", sa.Date(), nullable=True),
        sa.Column("payment_method", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="scheduled"),
        sa.Column("note", sa.Text(), nullable=True),
        *_audit_cols(),
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("record_no", name="uq_payment_records_no"),
        sa.CheckConstraint(
            "record_type IN ('order', 'receipt', 'inspection', 'payment', "
            "'withholding', 'credit_note', 'other')",
            name="ck_payment_records_type",
        ),
        sa.CheckConstraint(
            "payment_method IS NULL OR payment_method IN "
            "('bank_transfer', 'promissory_note', 'electronic_bond', 'factoring', 'other')",
            name="ck_payment_records_method",
        ),
        sa.CheckConstraint(
            "status IN ('scheduled', 'paid', 'late', 'checked', 'cancelled')",
            name="ck_payment_records_status",
        ),
    )
    op.create_index("ix_payment_records_contract", "payment_records", ["contract_id"])
    op.create_index("ix_payment_records_event_date", "payment_records", ["event_date"])
    op.create_index("ix_payment_records_status", "payment_records", ["status"])

    # ------------------------------------------------------------------
    # document_consistency_results（文書間の金額・工期・日付矛盾チェック結果）
    # ------------------------------------------------------------------
    op.create_table(
        "document_consistency_results",
        _pk(),
        sa.Column("contract_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="needs_review"),
        sa.Column("findings", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("checked_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["checked_by"], ["users.id"], ondelete="SET NULL", use_alter=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('consistent', 'inconsistent', 'needs_review')",
            name="ck_consistency_status",
        ),
    )
    op.create_index(
        "ix_consistency_contract", "document_consistency_results", ["contract_id", "checked_at"]
    )

    # ------------------------------------------------------------------
    # PostgreSQL RLS（SQLite ではスキップ）
    # ------------------------------------------------------------------
    if bind.dialect.name != "postgresql":
        return

    # アプリコンテキスト設定関数の冪等作成
    op.execute(
        """
        CREATE OR REPLACE FUNCTION legalops_actor_id() RETURNS bigint
        LANGUAGE sql STABLE PARALLEL SAFE AS
        $$ SELECT NULLIF(current_setting('app.actor_id', true), '')::bigint $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION legalops_actor_role() RETURNS text
        LANGUAGE sql STABLE PARALLEL SAFE AS
        $$ SELECT current_setting('app.role', true) $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION legalops_actor_email() RETURNS text
        LANGUAGE sql STABLE PARALLEL SAFE AS
        $$ SELECT lower(NULLIF(current_setting('app.actor_email', true), '')) $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION legalops_contract_visible(pid bigint)
        RETURNS boolean LANGUAGE sql STABLE PARALLEL SAFE AS
        $$
        SELECT EXISTS (
            SELECT 1 FROM contracts c
            WHERE c.id = pid
              AND (
                c.ethical_wall = false
                AND (
                    c.drafter_id = legalops_actor_id()
                    OR legalops_actor_role() IN ('admin', 'auditor')
                    OR EXISTS (
                        SELECT 1 FROM access_control_entries ace
                        WHERE ace.contract_id = c.id
                          AND (
                                (ace.principal_type = 'user'
                                 AND ace.principal_id = legalops_actor_id()::text)
                             OR (ace.principal_type = 'role'
                                 AND ace.principal_id = legalops_actor_role())
                             OR (ace.principal_type = 'department'
                                 AND ace.principal_id::bigint IN (
                                     SELECT department_id FROM users
                                     WHERE id = legalops_actor_id()))
                             OR (ace.principal_type = 'external_counsel'
                                 AND ace.principal_id = legalops_actor_email())
                          )
                          AND (ace.expires_at IS NULL OR ace.expires_at > now())
                    )
                )
                OR (
                    c.ethical_wall = true
                    AND (
                        legalops_actor_role() IN ('admin', 'auditor')
                        OR EXISTS (
                            SELECT 1 FROM access_control_entries ace
                            WHERE ace.contract_id = c.id
                              AND ace.principal_type = 'user'
                              AND ace.principal_id = legalops_actor_id()::text
                              AND (ace.expires_at IS NULL OR ace.expires_at > now())
                        )
                    )
                )
            )
        )
        $$;
        """
    )

    op.execute("ALTER TABLE contracts ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY contracts_tenant_isolation ON contracts
        FOR ALL
        USING (
            ethical_wall = false
            AND (
                drafter_id = legalops_actor_id()
                OR legalops_actor_role() IN ('admin', 'auditor')
                OR EXISTS (
                    SELECT 1 FROM access_control_entries ace
                    WHERE ace.contract_id = contracts.id
                      AND (
                            (ace.principal_type = 'user'
                             AND ace.principal_id = legalops_actor_id()::text)
                         OR (ace.principal_type = 'role'
                             AND ace.principal_id = legalops_actor_role())
                         OR (ace.principal_type = 'department'
                             AND ace.principal_id::bigint IN (
                                 SELECT department_id FROM users
                                 WHERE id = legalops_actor_id()))
                         OR (ace.principal_type = 'external_counsel'
                             AND ace.principal_id = legalops_actor_email())
                      )
                      AND (ace.expires_at IS NULL OR ace.expires_at > now())
                )
            )
        )
        WITH CHECK (
            drafter_id = legalops_actor_id()
            OR legalops_actor_role() IN ('admin', 'auditor')
        )
        """
    )
    op.execute(
        """
        CREATE POLICY contracts_ethical_wall ON contracts
        FOR SELECT
        USING (
            ethical_wall = true
            AND (
                legalops_actor_role() IN ('admin', 'auditor')
                OR EXISTS (
                    SELECT 1 FROM access_control_entries ace
                    WHERE ace.contract_id = contracts.id
                      AND ace.principal_type = 'user'
                      AND ace.principal_id = legalops_actor_id()::text
                      AND (ace.expires_at IS NULL OR ace.expires_at > now())
                )
            )
        )
        """
    )

    for table in (
        "access_control_entries",
        "contract_documents",
        "change_orders",
        "change_order_evidence",
        "disputes",
        "dispute_timeline_events",
        "dispute_evidence",
        "payment_records",
        "document_consistency_results",
    ):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_isolation ON {table}
            FOR ALL
            USING (legalops_actor_role() <> '' OR legalops_actor_id() IS NOT NULL)
            WITH CHECK (legalops_actor_role() <> '' OR legalops_actor_id() IS NOT NULL)
            """
        )
        if table in {
            "contract_documents",
            "change_orders",
            "payment_records",
            "document_consistency_results",
        }:
            op.execute(
                f"""
                CREATE POLICY {table}_contract_scope ON {table}
                FOR ALL
                USING (legalops_contract_visible(contract_id))
                """
            )
        if table == "change_order_evidence":
            op.execute(
                """
                CREATE POLICY change_order_evidence_contract_scope ON change_order_evidence
                FOR ALL
                USING (
                    EXISTS (
                        SELECT 1 FROM change_orders co
                        WHERE co.id = change_order_evidence.change_order_id
                          AND legalops_contract_visible(co.contract_id)
                    )
                )
                """
            )
        if table == "disputes":
            op.execute(
                f"""
                CREATE POLICY {table}_contract_scope ON {table}
                FOR ALL
                USING (
                    contract_id IS NULL
                    OR legalops_contract_visible(contract_id)
                )
                """
            )

    for child in ("dispute_timeline_events", "dispute_evidence"):
        op.execute(
            f"""
            CREATE POLICY {child}_contract_scope ON {child}
            FOR ALL
            USING (
                EXISTS (
                    SELECT 1 FROM disputes d
                    WHERE d.id = {child}.dispute_id
                      AND (d.contract_id IS NULL OR legalops_contract_visible(d.contract_id))
                )
            )
            """
        )

    op.execute("ALTER TABLE partners ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY partners_tenant_isolation ON partners
        FOR ALL
        USING (legalops_actor_role() <> '' OR legalops_actor_id() IS NOT NULL)
        WITH CHECK (legalops_actor_role() <> '' OR legalops_actor_id() IS NOT NULL)
        """
    )

    op.execute("ALTER TABLE legal_holds ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY legal_holds_admin_only ON legal_holds
        FOR ALL
        USING (
            legalops_actor_role() IN ('admin', 'auditor')
            OR started_by = legalops_actor_id()
        )
        WITH CHECK (legalops_actor_role() IN ('admin', 'auditor'))
        """
    )

    op.execute("ALTER TABLE retention_rules ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY retention_rules_admin_only ON retention_rules
        FOR ALL
        USING (legalops_actor_role() IN ('admin', 'auditor'))
        WITH CHECK (legalops_actor_role() IN ('admin', 'auditor'))
        """
    )

    op.execute("ALTER TABLE audit_anchors ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY audit_anchors_admin_only ON audit_anchors
        FOR ALL
        USING (legalops_actor_role() IN ('admin', 'auditor'))
        WITH CHECK (legalops_actor_role() IN ('admin', 'auditor'))
        """
    )

    op.execute("ALTER TABLE external_forward_events ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY external_forward_admin_only ON external_forward_events
        FOR ALL
        USING (legalops_actor_role() IN ('admin', 'auditor'))
        WITH CHECK (legalops_actor_role() IN ('admin', 'auditor'))
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table in (
            "external_forward_events",
            "audit_anchors",
            "retention_rules",
            "document_consistency_results",
            "payment_records",
            "dispute_evidence",
            "dispute_timeline_events",
            "disputes",
            "partners",
            "change_order_evidence",
            "change_orders",
            "contract_documents",
            "legal_holds",
            "access_control_entries",
            "contracts",
        ):
            op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
            op.execute(f"DROP POLICY IF EXISTS {table}_contract_scope ON {table}")
            op.execute(f"DROP POLICY IF EXISTS {table}_admin_only ON {table}")
            op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
        op.execute("DROP POLICY IF EXISTS contracts_ethical_wall ON contracts")

    for table in (
        "external_forward_events",
        "retention_rules",
        "document_consistency_results",
        "payment_records",
        "dispute_evidence",
        "dispute_timeline_events",
        "disputes",
        "partners",
        "change_order_evidence",
        "change_orders",
        "contract_documents",
        "audit_anchors",
        "legal_holds",
        "access_control_entries",
    ):
        op.drop_table(table)

    for column in (
        "ethical_wall",
        "case_category",
        "counterparty_employees",
        "our_employees",
        "counterparty_capital_jpy",
        "our_capital_jpy",
        "handles_personal_data",
        "is_public_work",
        "transaction_kind",
        "payment_date",
        "inspection_date",
        "receipt_date",
        "order_date",
    ):
        op.drop_column("contracts", column)
