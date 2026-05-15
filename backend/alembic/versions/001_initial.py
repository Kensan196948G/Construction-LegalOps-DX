"""Initial schema — 13 tables for Construction-LegalOps-DX.

Revision ID: 001_initial
Revises:
Create Date: 2026-05-16

Creates every business table defined in ``docs/database_design.md`` together
with the supporting indexes, CHECK constraints, foreign keys, the
``pg_trgm`` extension required by trigram indexes, and the
append-only trigger on ``audit_logs``.

The upgrade is purely additive; the downgrade drops everything in reverse
dependency order so that local resets work cleanly.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Reusable CHECK lists (kept in lock-step with app/models/enums.py)
# ---------------------------------------------------------------------------
USER_ROLES = ("viewer", "drafter", "reviewer", "approver", "admin", "auditor", "guest")
CONTRACT_STATUS = ("draft", "in_review", "approved", "signed", "archived", "rejected")
CONFIDENTIALITY = ("public", "normal", "confidential", "restricted")
REVIEW_TYPE = ("ai", "human", "hybrid")
REVIEW_STATUS = ("pending", "running", "completed", "failed", "rejected", "accepted")
RISK_LEVEL = ("low", "medium", "high", "critical")
RECOMMENDATION = ("required", "recommended", "optional", "prohibited")
RISK_PROB = ("low", "medium", "high")
RISK_IMPACT = ("low", "medium", "high")
RISK_STATUS = (
    "open", "in_progress", "accepted", "transferred",
    "mitigated", "avoided", "closed",
)
WF_STEP_TYPE = (
    "draft", "legal_review", "manager_approval",
    "exec_approval", "sign", "custom",
)
WF_STEP_STATUS = (
    "pending", "in_progress", "approved", "rejected",
    "skipped", "sent_back",
)
COMMENT_VIS = ("internal", "reviewer_only", "public")
ATTACHMENT_STORAGE = ("sharepoint", "directcloud", "local")
NOTIF_CHANNEL = ("mail", "teams", "in_app", "desknets")
NOTIF_STATUS = ("queued", "sent", "failed", "read")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    """Render ``column IN ('a','b',...)`` for a CHECK constraint."""
    rendered = ",".join(f"'{v}'" for v in values)
    return f"{column} IN ({rendered})"


def upgrade() -> None:
    # Required PostgreSQL extensions ----------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # 1. departments --------------------------------------------------------
    op.create_table(
        "departments",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=32), nullable=False, unique=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("parent_id", sa.BigInteger(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["departments.id"],
            name="fk_departments_parent",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_departments_parent", "departments", ["parent_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_departments_active", "departments", ["is_active"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # 2. users --------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("entra_oid", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("email", sa.String(length=256), nullable=False, unique=True),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("department_id", sa.BigInteger(), nullable=True),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "attributes", postgresql.JSONB(astext_type=sa.Text()),
            nullable=False, server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["department_id"], ["departments.id"],
            name="fk_users_department",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(_in_list("role", USER_ROLES), name="ck_users_role"),
    )
    op.create_index(
        "ix_users_department", "users", ["department_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_users_role", "users", ["role"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_users_active", "users", ["is_active"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # 3. contracts ----------------------------------------------------------
    op.create_table(
        "contracts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("contract_no", sa.String(length=64), nullable=False, unique=True),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("counterparty", sa.String(length=256), nullable=False),
        sa.Column("contract_type", sa.String(length=64), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("currency", sa.CHAR(length=3), nullable=False, server_default="JPY"),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("department_id", sa.BigInteger(), nullable=False),
        sa.Column("drafter_id", sa.BigInteger(), nullable=False),
        sa.Column("confidentiality", sa.String(length=16), nullable=False, server_default="normal"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("sharepoint_item_id", sa.String(length=256), nullable=True),
        sa.Column(
            "metadata", postgresql.JSONB(astext_type=sa.Text()),
            nullable=False, server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["drafter_id"], ["users.id"], ondelete="RESTRICT", use_alter=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT", use_alter=True),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT", use_alter=True),
        sa.CheckConstraint("amount IS NULL OR amount >= 0", name="ck_contracts_amount_nonneg"),
        sa.CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name="ck_contracts_date_order",
        ),
        sa.CheckConstraint(_in_list("status", CONTRACT_STATUS), name="ck_contracts_status"),
        sa.CheckConstraint(_in_list("confidentiality", CONFIDENTIALITY), name="ck_contracts_confidentiality"),
    )
    op.create_index(
        "ix_contracts_status", "contracts", ["status"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_contracts_department", "contracts", ["department_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_contracts_drafter", "contracts", ["drafter_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_contracts_dates", "contracts", ["start_date", "end_date"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.execute(
        "CREATE INDEX ix_contracts_title_trgm "
        "ON contracts USING gin (title gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_contracts_counter_trgm "
        "ON contracts USING gin (counterparty gin_trgm_ops)"
    )

    # 4. clause_library -----------------------------------------------------
    op.create_table(
        "clause_library",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=64), nullable=False, unique=True),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.String(length=16), nullable=False, server_default="recommended"),
        sa.Column("tags", postgresql.ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT", use_alter=True),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT", use_alter=True),
        sa.CheckConstraint(_in_list("recommendation", RECOMMENDATION), name="ck_library_recommendation"),
    )
    op.create_index(
        "ix_library_category", "clause_library", ["category"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_library_recom", "clause_library", ["recommendation"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.execute(
        "CREATE INDEX ix_library_tags ON clause_library USING gin (tags)"
    )

    # 5. clauses ------------------------------------------------------------
    op.create_table(
        "clauses",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("contract_id", sa.BigInteger(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("library_clause_id", sa.BigInteger(), nullable=True),
        sa.Column("risk_level", sa.String(length=16), nullable=True),
        sa.Column(
            "ai_findings", postgresql.JSONB(astext_type=sa.Text()),
            nullable=False, server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["library_clause_id"], ["clause_library.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("contract_id", "seq", name="uq_clauses_contract_seq"),
        sa.CheckConstraint(
            f"risk_level IS NULL OR {_in_list('risk_level', RISK_LEVEL)}",
            name="ck_clauses_risk_level",
        ),
    )
    op.create_index(
        "ix_clauses_contract", "clauses", ["contract_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_clauses_risk", "clauses", ["risk_level"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.execute(
        "CREATE INDEX ix_clauses_body_trgm ON clauses USING gin (body gin_trgm_ops)"
    )

    # 6. legal_reviews ------------------------------------------------------
    op.create_table(
        "legal_reviews",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("contract_id", sa.BigInteger(), nullable=False),
        sa.Column("review_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("ai_model", sa.String(length=64), nullable=True),
        sa.Column("ai_input_tokens", sa.Integer(), nullable=True),
        sa.Column("ai_output_tokens", sa.Integer(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("overall_risk", sa.String(length=16), nullable=True),
        sa.Column("risk_score", sa.Integer(), nullable=True),
        sa.Column(
            "result", postgresql.JSONB(astext_type=sa.Text()),
            nullable=False, server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewer_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="RESTRICT", use_alter=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT", use_alter=True),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT", use_alter=True),
        sa.CheckConstraint(_in_list("review_type", REVIEW_TYPE), name="ck_reviews_type"),
        sa.CheckConstraint(_in_list("status", REVIEW_STATUS), name="ck_reviews_status"),
        sa.CheckConstraint(
            f"overall_risk IS NULL OR {_in_list('overall_risk', RISK_LEVEL)}",
            name="ck_reviews_overall_risk",
        ),
        sa.CheckConstraint(
            "risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 100)",
            name="ck_reviews_risk_score_range",
        ),
    )
    op.create_index(
        "ix_reviews_contract", "legal_reviews", ["contract_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_reviews_status", "legal_reviews", ["status"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_reviews_overall", "legal_reviews", ["overall_risk"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # 7. risk_items ---------------------------------------------------------
    op.create_table(
        "risk_items",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("contract_id", sa.BigInteger(), nullable=False),
        sa.Column("clause_id", sa.BigInteger(), nullable=True),
        sa.Column("legal_review_id", sa.BigInteger(), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("probability", sa.String(length=16), nullable=False, server_default="medium"),
        sa.Column("impact", sa.String(length=16), nullable=False, server_default="medium"),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("mitigation", sa.Text(), nullable=True),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("owner_id", sa.BigInteger(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["clause_id"], ["clauses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["legal_review_id"], ["legal_reviews.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="RESTRICT", use_alter=True),
        sa.CheckConstraint(_in_list("severity", RISK_LEVEL), name="ck_risk_severity"),
        sa.CheckConstraint(_in_list("probability", RISK_PROB), name="ck_risk_probability"),
        sa.CheckConstraint(_in_list("impact", RISK_IMPACT), name="ck_risk_impact"),
        sa.CheckConstraint(_in_list("status", RISK_STATUS), name="ck_risk_status"),
    )
    op.create_index(
        "ix_risk_contract", "risk_items", ["contract_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_risk_severity", "risk_items", ["severity"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_risk_status", "risk_items", ["status"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # 8. workflows ----------------------------------------------------------
    op.create_table(
        "workflows",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=64), nullable=False, unique=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("contract_type", sa.String(length=64), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "definition", postgresql.JSONB(astext_type=sa.Text()),
            nullable=False, server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 9. workflow_steps -----------------------------------------------------
    op.create_table(
        "workflow_steps",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("workflow_id", sa.BigInteger(), nullable=False),
        sa.Column("contract_id", sa.BigInteger(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("step_type", sa.String(length=32), nullable=False),
        sa.Column("assignee_id", sa.BigInteger(), nullable=True),
        sa.Column("assignee_role", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assignee_id"], ["users.id"], ondelete="RESTRICT", use_alter=True),
        sa.UniqueConstraint("contract_id", "seq", name="uq_wfsteps_contract_seq"),
        sa.CheckConstraint(_in_list("step_type", WF_STEP_TYPE), name="ck_wfsteps_step_type"),
        sa.CheckConstraint(_in_list("status", WF_STEP_STATUS), name="ck_wfsteps_status"),
    )
    op.create_index(
        "ix_wfsteps_contract", "workflow_steps", ["contract_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_wfsteps_assignee", "workflow_steps", ["assignee_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_wfsteps_status", "workflow_steps", ["status"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # 10. comments ----------------------------------------------------------
    op.create_table(
        "comments",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("contract_id", sa.BigInteger(), nullable=False),
        sa.Column("clause_id", sa.BigInteger(), nullable=True),
        sa.Column("parent_id", sa.BigInteger(), nullable=True),
        sa.Column("author_id", sa.BigInteger(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("visibility", sa.String(length=16), nullable=False, server_default="internal"),
        sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["clause_id"], ["clauses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["parent_id"], ["comments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="RESTRICT", use_alter=True),
        sa.CheckConstraint(_in_list("visibility", COMMENT_VIS), name="ck_comments_visibility"),
    )
    op.create_index(
        "ix_comments_contract", "comments", ["contract_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_comments_clause", "comments", ["clause_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_comments_author", "comments", ["author_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # 11. attachments -------------------------------------------------------
    op.create_table(
        "attachments",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("contract_id", sa.BigInteger(), nullable=False),
        sa.Column("filename", sa.String(length=256), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sharepoint_item_id", sa.String(length=256), nullable=False),
        sa.Column("storage", sa.String(length=32), nullable=False, server_default="sharepoint"),
        sa.Column("checksum_sha256", sa.CHAR(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("uploaded_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="RESTRICT", use_alter=True),
        sa.CheckConstraint("size_bytes >= 0", name="ck_attachments_size_nonneg"),
        sa.CheckConstraint(_in_list("storage", ATTACHMENT_STORAGE), name="ck_attachments_storage"),
    )
    op.create_index(
        "ix_attachments_contract", "attachments", ["contract_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_attachments_primary", "attachments", ["contract_id"],
        postgresql_where=sa.text("is_primary AND deleted_at IS NULL"),
    )

    # 12. notifications -----------------------------------------------------
    op.create_table(
        "notifications",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("recipient_id", sa.BigInteger(), nullable=False),
        sa.Column("contract_id", sa.BigInteger(), nullable=True),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("subject", sa.String(length=256), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column(
            "payload", postgresql.JSONB(astext_type=sa.Text()),
            nullable=False, server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="queued"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"], ondelete="RESTRICT", use_alter=True),
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(_in_list("channel", NOTIF_CHANNEL), name="ck_notifications_channel"),
        sa.CheckConstraint(_in_list("status", NOTIF_STATUS), name="ck_notifications_status"),
    )
    op.create_index(
        "ix_notif_recipient", "notifications", ["recipient_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_notif_status", "notifications", ["status"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_notif_scheduled", "notifications", ["scheduled_at"],
        postgresql_where=sa.text("status = 'queued'"),
    )

    # 13. audit_logs --------------------------------------------------------
    # NOTE: month-range partitioning on occurred_at is planned but deferred
    #       to a later revision per docs/database_design.md section 7.
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("actor_id", sa.BigInteger(), nullable=True),
        sa.Column("actor_role", sa.String(length=32), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.BigInteger(), nullable=True),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column(
            "payload", postgresql.JSONB(astext_type=sa.Text()),
            nullable=False, server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("previous_hash", sa.CHAR(length=64), nullable=True),
        sa.Column("hash_chain", sa.CHAR(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        # SET NULL so deleting a user (very rare; soft delete preferred) does
        # not break the immutable audit history.
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], ondelete="SET NULL", use_alter=True,
        ),
    )
    op.create_index("ix_audit_logs_target", "audit_logs", ["target_type", "target_id"])
    op.create_index("ix_audit_logs_actor", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_time", "audit_logs", ["occurred_at"])

    # Append-only trigger ---------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION forbid_change_audit_logs()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs is append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_logs_no_update
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW EXECUTE FUNCTION forbid_change_audit_logs();
        """
    )


def downgrade() -> None:
    """Reverse the entire schema.

    Tables are dropped in reverse FK order; the append-only trigger and its
    function are removed first so that ``audit_logs`` can be dropped.
    """

    op.execute("DROP TRIGGER IF EXISTS trg_audit_logs_no_update ON audit_logs")
    op.execute("DROP FUNCTION IF EXISTS forbid_change_audit_logs()")

    op.drop_table("audit_logs")
    op.drop_table("notifications")
    op.drop_table("attachments")
    op.drop_table("comments")
    op.drop_table("workflow_steps")
    op.drop_table("workflows")
    op.drop_table("risk_items")
    op.drop_table("legal_reviews")
    op.drop_table("clauses")
    op.drop_table("clause_library")
    op.drop_table("contracts")
    op.drop_table("users")
    op.drop_table("departments")
