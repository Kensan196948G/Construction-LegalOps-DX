"""既存 RLS の contract_scope ポリシーを RESTRICTIVE 化（PERMISSIVE OR 結合の是正）.

Revision ID: 026_rls_restrictive_scope
Revises: 025_evidence
Create Date: 2026-09-06

Issue #129（PR #126 の CodeRabbit Critical 指摘 C1 と同型の既存バグ）。

``007_business_domain`` が作成した以下のテーブルは、``{table}_tenant_isolation``
（``FOR ALL``・PERMISSIVE・USING句が
``legalops_actor_role() <> '' OR legalops_actor_id() IS NOT NULL`` という
認証済みならほぼ常に真になる緩い条件）と ``{table}_contract_scope``
（``FOR ALL``・PERMISSIVE・契約可視性を制限する条件）の両方を持つ:

- disputes / dispute_timeline_events / dispute_evidence
- contract_documents / change_orders / change_order_evidence
- payment_records / document_consistency_results

PostgreSQL の PERMISSIVE ポリシー（既定）は同一コマンドに複数存在する場合
``OR`` で結合される。``tenant_isolation`` 側がほぼ常に真になるため、
``contract_scope`` 側の契約可視性チェックが事実上迂回され、閲覧権限のない
案件の子レコードが読める可能性があった。

本 migration は各 ``{table}_contract_scope``（および
``change_order_evidence_contract_scope``、``dispute_timeline_events``/
``dispute_evidence`` の ``_contract_scope``）を ``AS RESTRICTIVE`` へ変更し、
``WITH CHECK`` も同条件で追加することで、``tenant_isolation`` の OR 結果と
AND 結合される制限として機能させる。USING/WITH CHECK の条件式自体は既存の
``007_business_domain`` から変更しない。
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "026_rls_restrictive_scope"
down_revision: str | Sequence[str] | None = "025_evidence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _is_postgres() -> bool:
    bind = op.get_bind()
    return bind.dialect.name == "postgresql"


# table -> (USING条件, WITH CHECK条件) — WITH CHECK は USING と同一条件を使う。
_SIMPLE_CONTRACT_SCOPE_TABLES: dict[str, str] = {
    "contract_documents": "legalops_contract_visible(contract_id)",
    "change_orders": "legalops_contract_visible(contract_id)",
    "payment_records": "legalops_contract_visible(contract_id)",
    "document_consistency_results": "legalops_contract_visible(contract_id)",
}

_DISPUTE_CHILD_TABLES: tuple[str, ...] = ("dispute_timeline_events", "dispute_evidence")

_DISPUTE_CHILD_CONDITION = """
EXISTS (
    SELECT 1 FROM disputes d
    WHERE d.id = {table}.dispute_id
      AND (d.contract_id IS NULL OR legalops_contract_visible(d.contract_id))
)
"""

_DISPUTES_CONDITION = "contract_id IS NULL OR legalops_contract_visible(contract_id)"

_CHANGE_ORDER_EVIDENCE_CONDITION = """
EXISTS (
    SELECT 1 FROM change_orders co
    WHERE co.id = change_order_evidence.change_order_id
      AND legalops_contract_visible(co.contract_id)
)
"""


def upgrade() -> None:
    if not _is_postgres():
        return

    for table, condition in _SIMPLE_CONTRACT_SCOPE_TABLES.items():
        op.execute(f"DROP POLICY IF EXISTS {table}_contract_scope ON {table}")
        op.execute(
            f"""
            CREATE POLICY {table}_contract_scope ON {table}
            AS RESTRICTIVE
            FOR ALL
            USING ({condition})
            WITH CHECK ({condition})
            """
        )

    op.execute("DROP POLICY IF EXISTS disputes_contract_scope ON disputes")
    op.execute(
        f"""
        CREATE POLICY disputes_contract_scope ON disputes
        AS RESTRICTIVE
        FOR ALL
        USING ({_DISPUTES_CONDITION})
        WITH CHECK ({_DISPUTES_CONDITION})
        """
    )

    for table in _DISPUTE_CHILD_TABLES:
        condition = _DISPUTE_CHILD_CONDITION.format(table=table)
        op.execute(f"DROP POLICY IF EXISTS {table}_contract_scope ON {table}")
        op.execute(
            f"""
            CREATE POLICY {table}_contract_scope ON {table}
            AS RESTRICTIVE
            FOR ALL
            USING ({condition})
            WITH CHECK ({condition})
            """
        )

    op.execute(
        "DROP POLICY IF EXISTS change_order_evidence_contract_scope ON change_order_evidence"
    )
    op.execute(
        f"""
        CREATE POLICY change_order_evidence_contract_scope ON change_order_evidence
        AS RESTRICTIVE
        FOR ALL
        USING ({_CHANGE_ORDER_EVIDENCE_CONDITION})
        WITH CHECK ({_CHANGE_ORDER_EVIDENCE_CONDITION})
        """
    )


def downgrade() -> None:
    if not _is_postgres():
        return

    for table, condition in _SIMPLE_CONTRACT_SCOPE_TABLES.items():
        op.execute(f"DROP POLICY IF EXISTS {table}_contract_scope ON {table}")
        op.execute(
            f"""
            CREATE POLICY {table}_contract_scope ON {table}
            FOR ALL
            USING ({condition})
            """
        )

    op.execute("DROP POLICY IF EXISTS disputes_contract_scope ON disputes")
    op.execute(
        f"""
        CREATE POLICY disputes_contract_scope ON disputes
        FOR ALL
        USING ({_DISPUTES_CONDITION})
        """
    )

    for table in _DISPUTE_CHILD_TABLES:
        condition = _DISPUTE_CHILD_CONDITION.format(table=table)
        op.execute(f"DROP POLICY IF EXISTS {table}_contract_scope ON {table}")
        op.execute(
            f"""
            CREATE POLICY {table}_contract_scope ON {table}
            FOR ALL
            USING ({condition})
            """
        )

    op.execute(
        "DROP POLICY IF EXISTS change_order_evidence_contract_scope ON change_order_evidence"
    )
    op.execute(
        f"""
        CREATE POLICY change_order_evidence_contract_scope ON change_order_evidence
        FOR ALL
        USING ({_CHANGE_ORDER_EVIDENCE_CONDITION})
        """
    )
