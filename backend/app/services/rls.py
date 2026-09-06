"""PostgreSQL RLS 実行時コンテキスト設定とポリシー整合性検証（P0-6）.

アプリは単一 DB ロールで接続するため、認証済みユーザーの識別情報を
``SET LOCAL`` でセッション変数に載せ、RLS ポリシーが
``current_setting('app.actor_id')`` 等を参照して行を絞り込む。

- actor_id     : users.id（数値）
- actor_role   : ロール名
- actor_email  : 外部顧問弁護士用の email（小文字）

SQLite / テスト環境では SET LOCAL は使えないため、アプリ層の
``access_control`` サービスが同等のチェックを実施する。
"""

from __future__ import annotations

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


def _is_sqlite(bind: object | None) -> bool:
    """SQLite 接続かどうかを判定する（Engine/Connection の違いを吸収）。"""
    if bind is None:
        return False
    url = getattr(bind, "url", None)
    if url is None:
        engine = getattr(bind, "engine", None)
        url = getattr(engine, "url", None) if engine is not None else None
    return url is not None and "sqlite" in str(url)


async def set_actor_context(
    session: AsyncSession,
    *,
    actor_id: int | None,
    role: str | None = None,
    email: str | None = None,
) -> None:
    """現在のトランザクションに RLS 用のセッション変数を設定する。

    ``SET LOCAL`` はトランザクション終了時に自動的に戻るため、
    FastAPI の get_db がコミット/ロールバックした後は残留しない。
    """
    if _is_sqlite(session.bind):
        return
    params = {
        "app.actor_id": (str(actor_id) if actor_id is not None else ""),
        "app.role": (role or ""),
        "app.actor_role": (role or ""),
        "app.actor_email": ((email or "").strip().lower()),
    }
    for key, value in params.items():
        await session.execute(
            text("SELECT set_config(:key, :value, true)"),
            {"key": key, "value": value},
        )
    logger.debug("rls.actor_context_set", actor_id=actor_id, role=role)


def policy_sql_statements() -> list[str]:
    """RLS ポリシー定義の正本（migration 006/007 と同期）。"""
    return [
        """CREATE OR REPLACE FUNCTION legalops_actor_id() RETURNS bigint
LANGUAGE sql STABLE PARALLEL SAFE AS
$$ SELECT NULLIF(current_setting('app.actor_id', true), '')::bigint $$""",
        """CREATE OR REPLACE FUNCTION legalops_actor_role() RETURNS text
LANGUAGE sql STABLE PARALLEL SAFE AS
$$ SELECT current_setting('app.role', true) $$""",
        """CREATE OR REPLACE FUNCTION legalops_actor_email() RETURNS text
LANGUAGE sql STABLE PARALLEL SAFE AS
$$ SELECT lower(NULLIF(current_setting('app.actor_email', true), '')) $$""",
        "ALTER TABLE contracts ENABLE ROW LEVEL SECURITY",
        "DROP POLICY IF EXISTS contracts_app_access ON contracts",
        """CREATE POLICY contracts_app_access ON contracts
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
)""",
        "DROP POLICY IF EXISTS contracts_tenant_isolation ON contracts",
        """CREATE POLICY contracts_tenant_isolation ON contracts
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
)""",
        "DROP POLICY IF EXISTS contracts_ethical_wall ON contracts",
        """CREATE POLICY contracts_ethical_wall ON contracts
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
)""",
        "ALTER TABLE access_control_entries ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE contract_documents ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE change_orders ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE change_order_evidence ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE disputes ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE dispute_timeline_events ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE dispute_evidence ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE partners ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE legal_holds ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE retention_rules ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE audit_anchors ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE external_forward_events ENABLE ROW LEVEL SECURITY",
        # --- Issue #123: 内部通報・調査管理（migration 024 と同期） ---
        "ALTER TABLE whistleblower_reports ENABLE ROW LEVEL SECURITY",
        """CREATE POLICY whistleblower_reports_case_access ON whistleblower_reports
USING (
    current_setting('app.role', true) IN ('admin', 'auditor')
    OR EXISTS (
        SELECT 1 FROM whistleblower_case_access wca
        WHERE wca.report_id = whistleblower_reports.id
          AND wca.user_id = NULLIF(current_setting('app.actor_id', true), '')::bigint
          AND wca.revoked_at IS NULL
          AND (wca.expires_at IS NULL OR wca.expires_at > now())
    )
)""",
        "ALTER TABLE whistleblower_reporter_profiles ENABLE ROW LEVEL SECURITY",
        """CREATE POLICY whistleblower_reporter_profiles_identity_access
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
)""",
        "ALTER TABLE whistleblower_case_access ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE whistleblower_evidence ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE whistleblower_interviews ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE whistleblower_timeline_events ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE whistleblower_actions ENABLE ROW LEVEL SECURITY",
    ]


async def rls_enabled_tables(session: AsyncSession) -> dict[str, bool]:
    """現在の DB で RLS が有効化されているテーブルを返す（PG のみ）。"""
    if _is_sqlite(session.bind):
        return {}
    rows = await session.execute(
        text(
            "SELECT relname, relrowsecurity "
            "FROM pg_class WHERE relrowsecurity = true "
            "ORDER BY relname"
        )
    )
    return {name: bool(flag) for name, flag in rows.all()}


__all__ = ["policy_sql_statements", "rls_enabled_tables", "set_actor_context"]
