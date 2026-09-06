"""紛争・クレーム管理高度化（dispute_delay_events / dispute_argument_positions /
dispute_settlement_options / dispute_proceeding_stages）.

Revision ID: 022_dispute_ext
Revises: 021_labor_commitment
Create Date: 2026-09-06

ロードマップ #97〜#112（紛争・クレーム管理の高度化）/ Issue #121 / Phase 3。

Claim Notice Generator（#97）・通知期限自動判定（#98）・Time Bar 警告／消滅時効
タイマー（#99・#112）・証拠充足度スコア／AI 証拠不足検知（#105・#106）・
Claim Chronology 自動生成（#107・#108）は既存 ``disputes`` /
``dispute_timeline_events`` / ``dispute_evidence`` と本 migration の
``dispute_delay_events`` を集計・生成するのみで、新規テーブルを追加しない。

RLS: 既存 ``disputes`` の RLS（migration 007）は
``contract_id IS NULL OR legalops_contract_visible(contract_id)`` で保護されて
いる。本 migration の子テーブルは ``dispute_timeline_events`` /
``dispute_evidence`` と同様に、親 ``disputes`` 経由のスコープポリシーを追加する
（PostgreSQL のみ・SQLite ではスキップ）。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "022_dispute_ext"
down_revision: str | Sequence[str] | None = "021_labor_commitment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CHILD_TABLES = (
    "dispute_delay_events",
    "dispute_argument_positions",
    "dispute_settlement_options",
    "dispute_proceeding_stages",
)


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    # --- #100〜#104 遅延事象台帳（原因分類・追加費用・損害額・EOT） ---
    op.create_table(
        "dispute_delay_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("dispute_id", sa.BigInteger(), nullable=False),
        sa.Column("cause_category", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("occurred_from", sa.Date(), nullable=False),
        sa.Column("occurred_to", sa.Date(), nullable=True),
        sa.Column("delay_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("responsible_party", sa.String(length=256), nullable=True),
        sa.Column("additional_cost_jpy", sa.BigInteger(), nullable=True),
        sa.Column("damage_amount_jpy", sa.BigInteger(), nullable=True),
        sa.Column("eot_days_requested", sa.Integer(), nullable=True),
        sa.Column("eot_days_granted", sa.Integer(), nullable=True),
        sa.Column("eot_status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("eot_decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("eot_decided_by", sa.BigInteger(), nullable=True),
        sa.Column("eot_note", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["dispute_id"], ["disputes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["eot_decided_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_check_constraint(
        "ck_dispute_delay_cause",
        "dispute_delay_events",
        "cause_category IN ('owner_caused', 'contractor_caused', 'weather', 'third_party', "
        "'force_majeure', 'design_change', 'other')",
    )
    op.create_check_constraint(
        "ck_dispute_delay_eot_status",
        "dispute_delay_events",
        "eot_status IN ('pending', 'approved', 'partial', 'rejected')",
    )
    op.create_check_constraint(
        "ck_dispute_delay_days_nonneg", "dispute_delay_events", "delay_days >= 0"
    )
    op.create_index("ix_dispute_delay_events_dispute", "dispute_delay_events", ["dispute_id"])
    op.create_index("ix_dispute_delay_events_cause", "dispute_delay_events", ["cause_category"])

    # --- #109 主張・反論マトリクス ---
    op.create_table(
        "dispute_argument_positions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("dispute_id", sa.BigInteger(), nullable=False),
        sa.Column("issue_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("issue_title", sa.String(length=256), nullable=False),
        sa.Column("party", sa.String(length=16), nullable=False),
        sa.Column("stance", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False, server_default="[]"),
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
        sa.ForeignKeyConstraint(["dispute_id"], ["disputes.id"], ondelete="CASCADE"),
    )
    op.create_check_constraint(
        "ck_dispute_argument_party",
        "dispute_argument_positions",
        "party IN ('ours', 'counterparty')",
    )
    op.create_check_constraint(
        "ck_dispute_argument_stance",
        "dispute_argument_positions",
        "stance IN ('claim', 'rebuttal', 'counter_rebuttal')",
    )
    op.create_index(
        "ix_dispute_argument_positions_dispute",
        "dispute_argument_positions",
        ["dispute_id", "issue_no"],
    )

    # --- #110 和解案比較 ---
    op.create_table(
        "dispute_settlement_options",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("dispute_id", sa.BigInteger(), nullable=False),
        sa.Column("option_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("settlement_amount_jpy", sa.BigInteger(), nullable=True),
        sa.Column("payment_terms", sa.Text(), nullable=True),
        sa.Column("pros", sa.Text(), nullable=True),
        sa.Column("cons", sa.Text(), nullable=True),
        sa.Column("probability_score", sa.Integer(), nullable=True),
        sa.Column("expected_value_jpy", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["dispute_id"], ["disputes.id"], ondelete="CASCADE"),
    )
    op.create_check_constraint(
        "ck_dispute_settlement_status",
        "dispute_settlement_options",
        "status IN ('draft', 'proposed', 'accepted', 'rejected', 'withdrawn')",
    )
    op.create_check_constraint(
        "ck_dispute_settlement_probability",
        "dispute_settlement_options",
        "probability_score IS NULL OR (probability_score >= 0 AND probability_score <= 100)",
    )
    op.create_index(
        "ix_dispute_settlement_options_dispute", "dispute_settlement_options", ["dispute_id"]
    )

    # --- #111 訴訟・ADR ステージ管理 ---
    op.create_table(
        "dispute_proceeding_stages",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("dispute_id", sa.BigInteger(), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("started_at", sa.Date(), nullable=False),
        sa.Column("ended_at", sa.Date(), nullable=True),
        sa.Column("forum", sa.String(length=256), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("extra_data", sa.JSON(), nullable=False, server_default="{}"),
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
        sa.ForeignKeyConstraint(["dispute_id"], ["disputes.id"], ondelete="CASCADE"),
    )
    op.create_check_constraint(
        "ck_dispute_stage_type",
        "dispute_proceeding_stages",
        "stage IN ('negotiation', 'mediation', 'arbitration_filed', 'arbitration_hearing', "
        "'arbitration_award', 'lawsuit_filed', 'first_instance', 'appeal', 'final_judgment', "
        "'settled')",
    )
    op.create_check_constraint(
        "ck_dispute_stage_status",
        "dispute_proceeding_stages",
        "status IN ('active', 'completed')",
    )
    op.create_index(
        "ix_dispute_proceeding_stages_dispute",
        "dispute_proceeding_stages",
        ["dispute_id", "started_at"],
    )

    # --- RLS（PostgreSQL のみ・親 disputes 経由のスコープを継承） ---
    if _is_postgres():
        for table in _CHILD_TABLES:
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(
                f"""
                CREATE POLICY {table}_tenant_isolation ON {table}
                FOR ALL
                USING (legalops_actor_role() <> '' OR legalops_actor_id() IS NOT NULL)
                WITH CHECK (legalops_actor_role() <> '' OR legalops_actor_id() IS NOT NULL)
                """
            )
            # AS RESTRICTIVE: PostgreSQL の PERMISSIVE ポリシー（デフォルト）は
            # 同一コマンドで複数存在する場合 OR 結合される。tenant_isolation の
            # USING がほぼ常に真になるため、PERMISSIVE のままでは本ポリシーの
            # 契約スコープ制限が事実上無効化されてしまう。RESTRICTIVE にする
            # ことで PERMISSIVE 群の結果と AND 結合し、確実に絞り込む。
            # WITH CHECK も付与し、他契約の dispute_id を指定した
            # INSERT/UPDATE を拒否する。
            op.execute(
                f"""
                CREATE POLICY {table}_contract_scope ON {table}
                AS RESTRICTIVE
                FOR ALL
                USING (
                    EXISTS (
                        SELECT 1 FROM disputes d
                        WHERE d.id = {table}.dispute_id
                          AND (d.contract_id IS NULL OR legalops_contract_visible(d.contract_id))
                    )
                )
                WITH CHECK (
                    EXISTS (
                        SELECT 1 FROM disputes d
                        WHERE d.id = {table}.dispute_id
                          AND (d.contract_id IS NULL OR legalops_contract_visible(d.contract_id))
                    )
                )
                """
            )


def downgrade() -> None:
    if _is_postgres():
        for table in _CHILD_TABLES:
            op.execute(f"DROP POLICY IF EXISTS {table}_contract_scope ON {table}")
            op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
            op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_dispute_proceeding_stages_dispute", table_name="dispute_proceeding_stages")
    op.drop_table("dispute_proceeding_stages")

    op.drop_index("ix_dispute_settlement_options_dispute", table_name="dispute_settlement_options")
    op.drop_table("dispute_settlement_options")

    op.drop_index("ix_dispute_argument_positions_dispute", table_name="dispute_argument_positions")
    op.drop_table("dispute_argument_positions")

    op.drop_index("ix_dispute_delay_events_cause", table_name="dispute_delay_events")
    op.drop_index("ix_dispute_delay_events_dispute", table_name="dispute_delay_events")
    op.drop_table("dispute_delay_events")
