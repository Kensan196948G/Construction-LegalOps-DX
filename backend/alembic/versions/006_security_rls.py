"""案件単位 ACL・リーガルホールド・セキュリティ設定・監査出力 + 契約 RLS.

Revision ID: 006_security_rls
Revises: 005_contract_templates
Create Date: 2026-08-05

P0-6 対応:
- ``contract_access_grants`` 案件単位 ACL（外部顧問弁護士等の限定アクセス）
- ``legal_hold_cases`` リーガルホールド
- ``security_settings`` 保持期間等のセキュリティ設定
- ``audit_export_jobs`` WORM 相当外部保存ジョブ
- ``contracts`` に対する ROW LEVEL SECURITY + アプリケーションポリシー
  （``app.actor_id`` / ``app.role`` セッション変数を RLS コンテキストとして使用）
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "006_security_rls"
down_revision: str | Sequence[str] | None = "005_contract_templates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_tables() -> None:
    op.create_table(
        "contract_access_grants",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "contract_id",
            sa.BigInteger(),
            sa.ForeignKey("contracts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("access_level", sa.String(length=16), nullable=False, server_default="view"),
        sa.Column("ethical_wall", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "granted_by",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL", use_alter=True),
            nullable=True,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_contract_access_grants"),
        sa.UniqueConstraint("contract_id", "user_id", name="uq_contract_access_grants_pair"),
        sa.CheckConstraint(
            "access_level IN ('view','comment','edit')",
            name="ck_contract_access_grants_level",
        ),
    )
    op.create_index(
        "ix_contract_access_grants_user", "contract_access_grants", ["user_id"]
    )
    op.create_index(
        "ix_contract_access_grants_contract", "contract_access_grants", ["contract_id"]
    )

    op.create_table(
        "legal_hold_cases",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "contract_id",
            sa.BigInteger(),
            sa.ForeignKey("contracts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "requested_by",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL", use_alter=True),
            nullable=True,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_legal_hold_cases"),
    )
    op.create_index("ix_legal_hold_cases_contract", "legal_hold_cases", ["contract_id"])
    op.create_index("ix_legal_hold_cases_active", "legal_hold_cases", ["ended_at"])

    op.create_table(
        "security_settings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.dialects.postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_security_settings"),
        sa.UniqueConstraint("key", name="uq_security_settings_key"),
    )

    op.create_table(
        "audit_export_jobs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("job_no", sa.String(length=64), nullable=False),
        sa.Column("exported_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exported_to", sa.DateTime(timezone=True), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("signature", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_audit_export_jobs"),
        sa.UniqueConstraint("job_no", name="uq_audit_export_jobs_job_no"),
    )


def upgrade() -> None:
    _create_tables()

    # ---- PostgreSQL RLS（SQLite ではスキップ） ----
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE contracts ENABLE ROW LEVEL SECURITY")
        op.execute(
            """
            CREATE POLICY contracts_app_access ON contracts
            USING (
                current_setting('app.role', true) IN ('admin', 'auditor')
                OR contracts.drafter_id = NULLIF(current_setting('app.actor_id', true), '')::bigint
                OR EXISTS (
                    SELECT 1 FROM contract_access_grants g
                    WHERE g.contract_id = contracts.id
                      AND g.user_id = NULLIF(current_setting('app.actor_id', true), '')::bigint
                      AND g.revoked_at IS NULL
                      AND (g.expires_at IS NULL OR g.expires_at > now())
                )
            )
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP POLICY IF EXISTS contracts_app_access ON contracts")
        op.execute("ALTER TABLE contracts DISABLE ROW LEVEL SECURITY")
    op.drop_table("audit_export_jobs")
    op.drop_table("security_settings")
    op.drop_table("legal_hold_cases")
    op.drop_table("contract_access_grants")
