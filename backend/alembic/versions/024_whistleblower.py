"""内部通報・調査管理（whistleblower_*）.

Revision ID: 024_whistleblower
Revises: 021_labor_commitment
Create Date: 2026-09-06

ロードマップ #125〜#135 / Issue #123（Phase 3 §5.10）。

最重要要件: 通報者を特定できる情報（``whistleblower_reporter_profiles``）
を通報内容本体（``whistleblower_reports``）と分離したテーブルに保持し、
調査担当者限定 ACL（``whistleblower_case_access``）を持つ利用者と
admin/auditor のみがアクセスできるよう RLS ポリシーで強制する
（PostgreSQL のみ・既存 migration 006/007 のパターンを踏襲）。

NOTE: このリポジトリでは Issue #123 と並行して 022/023 番の migration が
他ブランチで作成される想定のため、本ファイルは意図的に revision "024" を
使用し、down_revision は現時点の worktree 上の head（021_labor_commitment）
を指す。統合時に 022 → 023 → 024 の順で down_revision を繋ぎ直すこと。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "024_whistleblower"
down_revision: str | Sequence[str] | None = "023_antitrust_compliance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CATEGORIES = ("harassment", "compliance", "safety", "labor", "corruption", "fraud", "other")
_STATUSES = ("received", "triage", "investigating", "corrective_action", "closed", "dismissed")
_SEVERITIES = ("low", "medium", "high", "critical")
_CASE_ROLES = ("lead_investigator", "investigator", "observer")
_EVIDENCE_TYPES = (
    "document",
    "email",
    "photo",
    "recording",
    "testimony",
    "system_log",
    "other",
)
_INTERVIEWEE_TYPES = ("reporter", "witness", "subject", "other")
_TIMELINE_TYPES = (
    "received",
    "triaged",
    "assigned",
    "status_changed",
    "evidence_added",
    "interview_conducted",
    "matter_linked",
    "action_added",
    "access_granted",
    "access_revoked",
    "note",
    "closed",
)
_ACTION_CATEGORIES = ("corrective", "preventive")
_ACTION_STATUSES = ("open", "in_progress", "completed", "verified", "overdue")


def _in_list(values: Sequence[str]) -> str:
    return "(" + ",".join(f"'{v}'" for v in values) + ")"


def _now_default() -> sa.TextClause:
    return sa.text("now()")


def _timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now_default(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now_default(),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "whistleblower_reports",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("report_no", sa.String(length=32), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="received"),
        sa.Column("severity", sa.String(length=16), nullable=False, server_default="medium"),
        sa.Column("is_anonymous", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("occurred_at", sa.Date(), nullable=True),
        sa.Column(
            "received_at", sa.DateTime(timezone=True), nullable=False, server_default=_now_default()
        ),
        sa.Column("matter_id", sa.BigInteger(), nullable=True),
        sa.Column("lead_investigator_id", sa.BigInteger(), nullable=True),
        sa.Column("substantiated", sa.Boolean(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["matter_id"], ["legal_matters.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["lead_investigator_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("report_no", name="uq_whistleblower_reports_report_no"),
    )
    op.create_check_constraint(
        "ck_whistleblower_reports_category",
        "whistleblower_reports",
        f"category IN {_in_list(_CATEGORIES)}",
    )
    op.create_check_constraint(
        "ck_whistleblower_reports_status",
        "whistleblower_reports",
        f"status IN {_in_list(_STATUSES)}",
    )
    op.create_check_constraint(
        "ck_whistleblower_reports_severity",
        "whistleblower_reports",
        f"severity IN {_in_list(_SEVERITIES)}",
    )
    op.create_index("ix_whistleblower_reports_status", "whistleblower_reports", ["status"])
    op.create_index("ix_whistleblower_reports_category", "whistleblower_reports", ["category"])
    op.create_index("ix_whistleblower_reports_matter", "whistleblower_reports", ["matter_id"])

    # --- 通報者識別情報（隔離テーブル・最重要） --------------------------
    op.create_table(
        "whistleblower_reporter_profiles",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("report_id", sa.BigInteger(), nullable=False),
        sa.Column("reporter_name", sa.String(length=128), nullable=True),
        sa.Column("contact_email", sa.String(length=256), nullable=True),
        sa.Column("contact_phone", sa.String(length=32), nullable=True),
        sa.Column("department", sa.String(length=128), nullable=True),
        sa.Column("relationship_to_subject", sa.String(length=64), nullable=True),
        sa.Column(
            "consent_identity_disclosure",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["report_id"], ["whistleblower_reports.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("report_id", name="uq_whistleblower_reporter_profiles_report"),
    )
    op.create_index(
        "ix_whistleblower_reporter_profiles_report",
        "whistleblower_reporter_profiles",
        ["report_id"],
    )

    # --- 調査担当者限定 ACL ------------------------------------------------
    op.create_table(
        "whistleblower_case_access",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("report_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "role_in_case", sa.String(length=24), nullable=False, server_default="investigator"
        ),
        sa.Column(
            "can_view_reporter_identity",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("granted_by", sa.BigInteger(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["report_id"], ["whistleblower_reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["granted_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("report_id", "user_id", name="uq_whistleblower_case_access_pair"),
    )
    op.create_check_constraint(
        "ck_whistleblower_case_access_role",
        "whistleblower_case_access",
        f"role_in_case IN {_in_list(_CASE_ROLES)}",
    )
    op.create_index(
        "ix_whistleblower_case_access_report", "whistleblower_case_access", ["report_id"]
    )
    op.create_index("ix_whistleblower_case_access_user", "whistleblower_case_access", ["user_id"])

    # --- 証拠保全（#129） ---------------------------------------------------
    op.create_table(
        "whistleblower_evidence",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("report_id", sa.BigInteger(), nullable=False),
        sa.Column("evidence_type", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.Date(), nullable=True),
        sa.Column("attachment_id", sa.BigInteger(), nullable=True),
        sa.Column("preserved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("chain_of_custody", sa.Text(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["report_id"], ["whistleblower_reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["attachment_id"], ["attachments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_check_constraint(
        "ck_whistleblower_evidence_type",
        "whistleblower_evidence",
        f"evidence_type IN {_in_list(_EVIDENCE_TYPES)}",
    )
    op.create_index("ix_whistleblower_evidence_report", "whistleblower_evidence", ["report_id"])

    # --- ヒアリング記録（#130） -----------------------------------------
    op.create_table(
        "whistleblower_interviews",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("report_id", sa.BigInteger(), nullable=False),
        sa.Column("interviewee_type", sa.String(length=16), nullable=False),
        sa.Column("interviewee_name", sa.String(length=128), nullable=True),
        sa.Column("conducted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("conducted_by", sa.BigInteger(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["report_id"], ["whistleblower_reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conducted_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_check_constraint(
        "ck_whistleblower_interviews_type",
        "whistleblower_interviews",
        f"interviewee_type IN {_in_list(_INTERVIEWEE_TYPES)}",
    )
    op.create_index("ix_whistleblower_interviews_report", "whistleblower_interviews", ["report_id"])

    # --- 調査タイムライン（#131・追記専用） ------------------------------
    op.create_table(
        "whistleblower_timeline_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("report_id", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("actor_id", sa.BigInteger(), nullable=True),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["report_id"], ["whistleblower_reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_check_constraint(
        "ck_whistleblower_timeline_type",
        "whistleblower_timeline_events",
        f"event_type IN {_in_list(_TIMELINE_TYPES)}",
    )
    op.create_index(
        "ix_whistleblower_timeline_report", "whistleblower_timeline_events", ["report_id"]
    )

    # --- 是正措置・再発防止管理（#132/#133） -----------------------------
    op.create_table(
        "whistleblower_actions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("report_id", sa.BigInteger(), nullable=False),
        sa.Column("action_category", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.BigInteger(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_by", sa.BigInteger(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verification_note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["report_id"], ["whistleblower_reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["verified_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_check_constraint(
        "ck_whistleblower_actions_category",
        "whistleblower_actions",
        f"action_category IN {_in_list(_ACTION_CATEGORIES)}",
    )
    op.create_check_constraint(
        "ck_whistleblower_actions_status",
        "whistleblower_actions",
        f"status IN {_in_list(_ACTION_STATUSES)}",
    )
    op.create_index("ix_whistleblower_actions_report", "whistleblower_actions", ["report_id"])
    op.create_index("ix_whistleblower_actions_status", "whistleblower_actions", ["status"])

    # ---- PostgreSQL RLS（SQLite ではスキップ・既存 006/007 のパターン踏襲） ----
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE whistleblower_reports ENABLE ROW LEVEL SECURITY")
        op.execute(
            """
            CREATE POLICY whistleblower_reports_case_access ON whistleblower_reports
            USING (
                current_setting('app.role', true) IN ('admin', 'auditor')
                OR EXISTS (
                    SELECT 1 FROM whistleblower_case_access wca
                    WHERE wca.report_id = whistleblower_reports.id
                      AND wca.user_id = NULLIF(current_setting('app.actor_id', true), '')::bigint
                      AND wca.revoked_at IS NULL
                      AND (wca.expires_at IS NULL OR wca.expires_at > now())
                )
            )
            """
        )

        op.execute("ALTER TABLE whistleblower_reporter_profiles ENABLE ROW LEVEL SECURITY")
        op.execute(
            """
            CREATE POLICY whistleblower_reporter_profiles_identity_access
            ON whistleblower_reporter_profiles
            USING (
                current_setting('app.role', true) IN ('admin', 'auditor')
                OR EXISTS (
                    SELECT 1 FROM whistleblower_case_access wca
                    WHERE wca.report_id = whistleblower_reporter_profiles.report_id
                      AND wca.user_id = NULLIF(current_setting('app.actor_id', true), '')::bigint
                      AND wca.can_view_reporter_identity = true
                      AND wca.revoked_at IS NULL
                      AND (wca.expires_at IS NULL OR wca.expires_at > now())
                )
            )
            """
        )

        for child_table in (
            "whistleblower_evidence",
            "whistleblower_interviews",
            "whistleblower_timeline_events",
            "whistleblower_actions",
        ):
            op.execute(f"ALTER TABLE {child_table} ENABLE ROW LEVEL SECURITY")
            op.execute(
                f"""
                CREATE POLICY {child_table}_case_access ON {child_table}
                USING (
                    current_setting('app.role', true) IN ('admin', 'auditor')
                    OR EXISTS (
                        SELECT 1 FROM whistleblower_case_access wca
                        WHERE wca.report_id = {child_table}.report_id
                          AND wca.user_id = NULLIF(current_setting('app.actor_id', true), '')::bigint
                          AND wca.revoked_at IS NULL
                          AND (wca.expires_at IS NULL OR wca.expires_at > now())
                    )
                )
                """
            )

        op.execute("ALTER TABLE whistleblower_case_access ENABLE ROW LEVEL SECURITY")
        op.execute(
            """
            CREATE POLICY whistleblower_case_access_self_or_admin ON whistleblower_case_access
            USING (
                current_setting('app.role', true) IN ('admin', 'auditor')
                OR user_id = NULLIF(current_setting('app.actor_id', true), '')::bigint
            )
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "DROP POLICY IF EXISTS whistleblower_case_access_self_or_admin ON whistleblower_case_access"
        )
        op.execute("ALTER TABLE whistleblower_case_access DISABLE ROW LEVEL SECURITY")
        for child_table in (
            "whistleblower_actions",
            "whistleblower_timeline_events",
            "whistleblower_interviews",
            "whistleblower_evidence",
        ):
            op.execute(f"DROP POLICY IF EXISTS {child_table}_case_access ON {child_table}")
            op.execute(f"ALTER TABLE {child_table} DISABLE ROW LEVEL SECURITY")
        op.execute(
            "DROP POLICY IF EXISTS whistleblower_reporter_profiles_identity_access "
            "ON whistleblower_reporter_profiles"
        )
        op.execute("ALTER TABLE whistleblower_reporter_profiles DISABLE ROW LEVEL SECURITY")
        op.execute(
            "DROP POLICY IF EXISTS whistleblower_reports_case_access ON whistleblower_reports"
        )
        op.execute("ALTER TABLE whistleblower_reports DISABLE ROW LEVEL SECURITY")

    op.drop_table("whistleblower_actions")
    op.drop_table("whistleblower_timeline_events")
    op.drop_table("whistleblower_interviews")
    op.drop_table("whistleblower_evidence")
    op.drop_table("whistleblower_case_access")
    op.drop_table("whistleblower_reporter_profiles")
    op.drop_index("ix_whistleblower_reports_matter", table_name="whistleblower_reports")
    op.drop_index("ix_whistleblower_reports_category", table_name="whistleblower_reports")
    op.drop_index("ix_whistleblower_reports_status", table_name="whistleblower_reports")
    op.drop_table("whistleblower_reports")
