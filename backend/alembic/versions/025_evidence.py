"""証拠・eDiscovery 管理（evidences / evidence_custody_events /
evidence_hold_release_approvals）.

Revision ID: 025_evidence
Revises: 024_whistleblower
Create Date: 2026-09-06

Phase 3 §5.17（ロードマップ #217-230）/ Issue #124。

RLS（PostgreSQL のみ・SQLite ではスキップ）:

``evidences`` は ``contract_id`` / ``matter_id`` / ``legal_hold_id`` のいずれか
（あるいは複数）で保護対象を持つ。可視性は次の優先順位で判定する。

1. ``legal_hold_id`` が指すレコードの ``ethical_wall = true`` の場合、
   admin/auditor 以外は不可視（Legal Hold の倫理壁を最優先で適用）。
2. admin/auditor は常に可視。
3. ``contract_id`` がある場合は既存 ``legalops_contract_visible`` を継承。
4. ``contract_id`` が無く ``matter_id`` がある場合は、当該 Matter の
   ``assignee_id`` 本人のみ可視（Matter 単位の ACL/RLS 基盤は
   ``app.models.matter`` の設計注記のとおり未整備のため、既存カラムを用いた
   最小限の暫定運用。Matter ACL 統合は別 Issue で追う）。
5. ``contract_id`` / ``matter_id`` がいずれも無い場合は、収集者
   （``collected_by``）または登録者（``created_by``）本人のみ可視。
6. 上記に加えて、Legal Hold の ``started_by`` 本人は常に可視（保存を開始した
   担当者が追跡できるようにする）。

``evidence_custody_events`` / ``evidence_hold_release_approvals`` は親
``evidences``（または解除申請が Hold 全体に対する場合は ``legal_holds``）
経由でスコープを継承する。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "025_evidence"
down_revision: str | Sequence[str] | None = "024_whistleblower"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


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

    # --- RLS（PostgreSQL のみ・M3 CodeRabbit 指摘対応） ---
    if _is_postgres():
        # SECURITY DEFINER が必須の理由: legal_holds は独自の RLS
        # （legal_holds_admin_only・admin/auditor または started_by 本人のみ
        # 可視）を持つ。この関数を SECURITY INVOKER のまま呼び出し元ロールの
        # 権限で legal_holds を EXISTS 参照すると、閲覧不可のロールには
        # ethical_wall 行自体が見えず「EXISTS が偽」＝「倫理壁なし」と誤判定
        # され、最も倫理壁で守るべき対象に素通しされてしまう。SECURITY
        # DEFINER（関数所有者権限で実行）にすることで legal_holds の行の
        # 存否を呼び出し元の可視性に関係なく正しく評価する。
        op.execute(
            """
            CREATE OR REPLACE FUNCTION legalops_evidence_row_visible(
                p_contract_id bigint,
                p_matter_id bigint,
                p_legal_hold_id bigint,
                p_collected_by bigint,
                p_created_by bigint
            ) RETURNS boolean LANGUAGE sql STABLE PARALLEL SAFE
            SECURITY DEFINER SET search_path = public, pg_temp AS
            $$
            SELECT
                (
                    p_legal_hold_id IS NULL
                    OR legalops_actor_role() IN ('admin', 'auditor')
                    OR NOT EXISTS (
                        SELECT 1 FROM legal_holds lh
                        WHERE lh.id = p_legal_hold_id AND lh.ethical_wall = true
                    )
                )
                AND (
                    legalops_actor_role() IN ('admin', 'auditor')
                    OR (p_contract_id IS NOT NULL AND legalops_contract_visible(p_contract_id))
                    OR (
                        p_contract_id IS NULL AND p_matter_id IS NOT NULL
                        AND EXISTS (
                            SELECT 1 FROM legal_matters lm
                            WHERE lm.id = p_matter_id AND lm.assignee_id = legalops_actor_id()
                        )
                    )
                    OR (
                        p_contract_id IS NULL AND p_matter_id IS NULL
                        AND (
                            p_collected_by = legalops_actor_id()
                            OR p_created_by = legalops_actor_id()
                        )
                    )
                    OR (
                        p_legal_hold_id IS NOT NULL
                        AND EXISTS (
                            SELECT 1 FROM legal_holds lh
                            WHERE lh.id = p_legal_hold_id
                              AND lh.started_by = legalops_actor_id()
                        )
                    )
                )
            $$;
            """
        )
        op.execute(
            """
            CREATE OR REPLACE FUNCTION legalops_evidence_visible(eid bigint) RETURNS boolean
            LANGUAGE sql STABLE PARALLEL SAFE
            SECURITY DEFINER SET search_path = public, pg_temp AS
            $$
            SELECT EXISTS (
                SELECT 1 FROM evidences e
                WHERE e.id = eid
                  AND legalops_evidence_row_visible(
                      e.contract_id, e.matter_id, e.legal_hold_id, e.collected_by, e.created_by
                  )
            )
            $$;
            """
        )

        op.execute("ALTER TABLE evidences ENABLE ROW LEVEL SECURITY")
        op.execute(
            """
            CREATE POLICY evidences_tenant_isolation ON evidences
            FOR ALL
            USING (legalops_actor_role() <> '' OR legalops_actor_id() IS NOT NULL)
            WITH CHECK (legalops_actor_role() <> '' OR legalops_actor_id() IS NOT NULL)
            """
        )
        # AS RESTRICTIVE: PERMISSIVE ポリシー同士は OR 結合されるため（C1 指摘と
        # 同じ理由）、tenant_isolation とは別に RESTRICTIVE で AND 結合し、
        # 契約／Matter／Legal Hold の倫理壁スコープを確実に強制する。
        op.execute(
            """
            CREATE POLICY evidences_scope ON evidences
            AS RESTRICTIVE
            FOR ALL
            USING (
                legalops_evidence_row_visible(
                    contract_id, matter_id, legal_hold_id, collected_by, created_by
                )
            )
            WITH CHECK (
                legalops_evidence_row_visible(
                    contract_id, matter_id, legal_hold_id, collected_by, created_by
                )
            )
            """
        )

        op.execute("ALTER TABLE evidence_custody_events ENABLE ROW LEVEL SECURITY")
        op.execute(
            """
            CREATE POLICY evidence_custody_events_tenant_isolation ON evidence_custody_events
            FOR ALL
            USING (legalops_actor_role() <> '' OR legalops_actor_id() IS NOT NULL)
            WITH CHECK (legalops_actor_role() <> '' OR legalops_actor_id() IS NOT NULL)
            """
        )
        op.execute(
            """
            CREATE POLICY evidence_custody_events_scope ON evidence_custody_events
            AS RESTRICTIVE
            FOR ALL
            USING (legalops_evidence_visible(evidence_id))
            WITH CHECK (legalops_evidence_visible(evidence_id))
            """
        )

        op.execute("ALTER TABLE evidence_hold_release_approvals ENABLE ROW LEVEL SECURITY")
        op.execute(
            """
            CREATE POLICY evidence_hold_release_approvals_tenant_isolation
            ON evidence_hold_release_approvals
            FOR ALL
            USING (legalops_actor_role() <> '' OR legalops_actor_id() IS NOT NULL)
            WITH CHECK (legalops_actor_role() <> '' OR legalops_actor_id() IS NOT NULL)
            """
        )
        op.execute(
            """
            CREATE POLICY evidence_hold_release_approvals_scope
            ON evidence_hold_release_approvals
            AS RESTRICTIVE
            FOR ALL
            USING (
                (evidence_id IS NOT NULL AND legalops_evidence_visible(evidence_id))
                OR (
                    evidence_id IS NULL
                    AND (
                        legalops_actor_role() IN ('admin', 'auditor')
                        OR EXISTS (
                            SELECT 1 FROM legal_holds lh
                            WHERE lh.id = evidence_hold_release_approvals.legal_hold_id
                              AND lh.started_by = legalops_actor_id()
                        )
                    )
                )
            )
            WITH CHECK (
                (evidence_id IS NOT NULL AND legalops_evidence_visible(evidence_id))
                OR (
                    evidence_id IS NULL
                    AND (
                        legalops_actor_role() IN ('admin', 'auditor')
                        OR EXISTS (
                            SELECT 1 FROM legal_holds lh
                            WHERE lh.id = evidence_hold_release_approvals.legal_hold_id
                              AND lh.started_by = legalops_actor_id()
                        )
                    )
                )
            )
            """
        )


def downgrade() -> None:
    if _is_postgres():
        op.execute(
            "DROP POLICY IF EXISTS evidence_hold_release_approvals_scope "
            "ON evidence_hold_release_approvals"
        )
        op.execute(
            "DROP POLICY IF EXISTS evidence_hold_release_approvals_tenant_isolation "
            "ON evidence_hold_release_approvals"
        )
        op.execute("ALTER TABLE evidence_hold_release_approvals DISABLE ROW LEVEL SECURITY")

        op.execute("DROP POLICY IF EXISTS evidence_custody_events_scope ON evidence_custody_events")
        op.execute(
            "DROP POLICY IF EXISTS evidence_custody_events_tenant_isolation "
            "ON evidence_custody_events"
        )
        op.execute("ALTER TABLE evidence_custody_events DISABLE ROW LEVEL SECURITY")

        op.execute("DROP POLICY IF EXISTS evidences_scope ON evidences")
        op.execute("DROP POLICY IF EXISTS evidences_tenant_isolation ON evidences")
        op.execute("ALTER TABLE evidences DISABLE ROW LEVEL SECURITY")

        op.execute("DROP FUNCTION IF EXISTS legalops_evidence_visible(bigint)")
        op.execute(
            "DROP FUNCTION IF EXISTS legalops_evidence_row_visible"
            "(bigint, bigint, bigint, bigint, bigint)"
        )

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
