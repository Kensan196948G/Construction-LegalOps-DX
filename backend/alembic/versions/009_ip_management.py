"""JPO 特許情報取得 API 連携（知財管理・競合ウォッチ・審査書類）のテーブル群.

Revision ID: 009_ip_management
Revises: 008_contract_type_master
Create Date: 2026-08-20

追加:
- ip_assets（知財台帳・出願単位）
- ip_watch_targets（競合ウォッチ対象・申請人）
- ip_watch_events（ウォッチ検知イベント）
- ip_documents（審査書類の収集・AI 解析結果）

設計: docs/architecture/ip_management_design.md
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "009_ip_management"
down_revision: str | Sequence[str] | None = "009_ai_provider_deepseek"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _jsonb() -> sa.types.TypeEngine:
    return JSONB() if _is_postgres() else sa.Text()


def upgrade() -> None:
    # ------------------------------------------------------------------
    # ip_watch_targets（先に作成: ip_assets が FK 参照する）
    # ------------------------------------------------------------------
    op.create_table(
        "ip_watch_targets",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("applicant_code", sa.String(length=16), nullable=True),
        sa.Column("ip_types", _jsonb(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
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
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ip_watch_targets")),
        sa.UniqueConstraint("name", name=op.f("uq_ip_watch_targets_name")),
        sa.CheckConstraint(
            "status IN ('active', 'paused')",
            name=op.f("ck_ip_watch_targets_status"),
        ),
    )
    if _is_postgres():
        # SQLite のデモ用シードではデフォルト JSON を文字列で指定する。
        op.execute(
            "ALTER TABLE ip_watch_targets ALTER COLUMN ip_types SET DEFAULT '[\"patent\"]'::jsonb"
        )

    # ------------------------------------------------------------------
    # ip_assets
    # ------------------------------------------------------------------
    op.create_table(
        "ip_assets",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("application_number", sa.String(length=16), nullable=False),
        sa.Column("ip_type", sa.String(length=16), nullable=False, server_default="patent"),
        sa.Column("invention_title", sa.String(length=512), nullable=True),
        sa.Column("filing_date", sa.Date(), nullable=True),
        sa.Column("applicants", _jsonb(), nullable=False),
        sa.Column("publication_number", sa.String(length=32), nullable=True),
        sa.Column("registration_number", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="unknown"),
        sa.Column("progress_data", _jsonb(), nullable=False),
        sa.Column("registration_data", _jsonb(), nullable=False),
        sa.Column("jplatpat_url", sa.String(length=512), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("watch_target_id", sa.BigInteger(), nullable=True),
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
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ip_assets")),
        sa.UniqueConstraint("application_number", name=op.f("uq_ip_assets_application_number")),
        sa.CheckConstraint(
            "ip_type IN ('patent', 'design', 'trademark')",
            name=op.f("ck_ip_assets_type"),
        ),
        sa.ForeignKeyConstraint(
            ["watch_target_id"],
            ["ip_watch_targets.id"],
            name=op.f("fk_ip_assets_watch_target_id_ip_watch_targets"),
            ondelete="SET NULL",
        ),
    )
    if _is_postgres():
        op.execute("ALTER TABLE ip_assets ALTER COLUMN applicants SET DEFAULT '[]'::jsonb")
        op.execute("ALTER TABLE ip_assets ALTER COLUMN progress_data SET DEFAULT '{}'::jsonb")
        op.execute("ALTER TABLE ip_assets ALTER COLUMN registration_data SET DEFAULT '{}'::jsonb")
    op.create_index(
        "ix_ip_assets_type_status",
        "ip_assets",
        ["ip_type", "status"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_ip_assets_watch_target",
        "ip_assets",
        ["watch_target_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # ------------------------------------------------------------------
    # ip_watch_events
    # ------------------------------------------------------------------
    op.create_table(
        "ip_watch_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("watch_target_id", sa.BigInteger(), nullable=False),
        sa.Column("ip_asset_id", sa.BigInteger(), nullable=True),
        sa.Column("application_number", sa.String(length=16), nullable=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("event_code", sa.String(length=32), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("event_data", _jsonb(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ip_watch_events")),
        sa.CheckConstraint(
            "event_type IN ('new_application', 'status_change', 'new_progress', "
            "'registration', 'publication')",
            name=op.f("ck_ip_watch_events_type"),
        ),
        sa.ForeignKeyConstraint(
            ["ip_asset_id"],
            ["ip_assets.id"],
            name=op.f("fk_ip_watch_events_ip_asset_id_ip_assets"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["watch_target_id"],
            ["ip_watch_targets.id"],
            name=op.f("fk_ip_watch_events_watch_target_id_ip_watch_targets"),
            ondelete="CASCADE",
        ),
    )
    if _is_postgres():
        op.execute("ALTER TABLE ip_watch_events ALTER COLUMN event_data SET DEFAULT '{}'::jsonb")
    op.create_index("ix_ip_watch_events_target", "ip_watch_events", ["watch_target_id"])
    op.create_index(
        "ix_ip_watch_events_unread",
        "ip_watch_events",
        ["is_read"],
        postgresql_where=sa.text("is_read = false"),
    )

    # ------------------------------------------------------------------
    # ip_documents
    # ------------------------------------------------------------------
    op.create_table(
        "ip_documents",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ip_asset_id", sa.BigInteger(), nullable=False),
        sa.Column("doc_type", sa.String(length=32), nullable=False),
        sa.Column("doc_name", sa.String(length=256), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("ai_summary", sa.Text(), nullable=True),
        sa.Column("ai_findings", _jsonb(), nullable=False),
        sa.Column("ai_model", sa.String(length=64), nullable=True),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ip_documents")),
        sa.CheckConstraint(
            "doc_type IN ('refusal_reason', 'opinion_amendment', 'decision', 'citation')",
            name=op.f("ck_ip_documents_type"),
        ),
        sa.ForeignKeyConstraint(
            ["ip_asset_id"],
            ["ip_assets.id"],
            name=op.f("fk_ip_documents_ip_asset_id_ip_assets"),
            ondelete="CASCADE",
        ),
    )
    if _is_postgres():
        op.execute("ALTER TABLE ip_documents ALTER COLUMN ai_findings SET DEFAULT '{}'::jsonb")
    op.create_index("ix_ip_documents_asset", "ip_documents", ["ip_asset_id"])

    # ------------------------------------------------------------------
    # SQLite（テスト）用の index は postgresql_where が効かないため、
    # PG のみ部分インデックスを追加する。
    # ------------------------------------------------------------------
    if _is_postgres():
        pass  # create_index の postgresql_where で対応済み


def downgrade() -> None:
    op.drop_table("ip_documents")
    op.drop_table("ip_watch_events")
    op.drop_table("ip_assets")
    op.drop_table("ip_watch_targets")
