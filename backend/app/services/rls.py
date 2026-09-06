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
        # NOTE(CodeRabbit M6/N2): USING 句のみの CREATE POLICY は PostgreSQL では
        # FOR ALL（SELECT/INSERT/UPDATE/DELETE 全て）に適用され、かつ同じ条件が
        # WITH CHECK にも流用される。ACL 保有者が既存行を更新・削除できてしまう
        # うえ、通報作成時（ACL 行がまだ無い段階）は admin/auditor 以外の INSERT
        # が拒否される。そのため reports / reporter_profiles は FOR SELECT に
        # 限定し、INSERT・UPDATE 用の別ポリシーを用意する。
        #
        # 実 PostgreSQL（テーブル所有者以外の DB ロールで接続する構成）での
        # 検証で判明した残課題（このタスクの修正範囲外・フォローアップ Issue 化
        # 対象）: SQLAlchemy の INSERT は既定で RETURNING を使い、また
        # ``create_report`` は flush 後に ``session.refresh(report)`` で読み戻す
        # ため、ACL 行がまだ無い時点でも自分が作成した行を SELECT できる必要が
        # ある。非匿名通報は下記 ``created_by = actor_id`` 条件で救済されるが、
        # 匿名通報（``created_by`` を意図的に NULL のまま保存する設計）はこの
        # 条件でも救済できない。匿名性の隔離を緩めずに解決するには、匿名時のみ
        # INSERT 直後の read-back を admin 相当のシステムコンテキストで行う、
        # または RETURNING/refresh に依存しない ORM 経路へ変更する等の設計変更が
        # 必要であり、本 PR の CodeRabbit 指摘対応の範囲を超えるため別 Issue とする。
        # 現行の単一 DB ロール構成（アプリ = テーブル所有者）では所有者が RLS を
        # バイパスするため、上記は実運用には影響しない（rls.py 冒頭の NOTE 参照）。
        "ALTER TABLE whistleblower_reports ENABLE ROW LEVEL SECURITY",
        "DROP POLICY IF EXISTS whistleblower_reports_case_access ON whistleblower_reports",
        """CREATE POLICY whistleblower_reports_case_access ON whistleblower_reports
FOR SELECT
USING (
    current_setting('app.role', true) IN ('admin', 'auditor')
    OR whistleblower_reports.created_by = NULLIF(current_setting('app.actor_id', true), '')::bigint
    OR EXISTS (
        SELECT 1 FROM whistleblower_case_access wca
        WHERE wca.report_id = whistleblower_reports.id
          AND wca.user_id = NULLIF(current_setting('app.actor_id', true), '')::bigint
          AND wca.revoked_at IS NULL
          AND (wca.expires_at IS NULL OR wca.expires_at > now())
    )
)""",
        "DROP POLICY IF EXISTS whistleblower_reports_insert ON whistleblower_reports",
        """CREATE POLICY whistleblower_reports_insert ON whistleblower_reports
FOR INSERT
WITH CHECK (
    COALESCE(NULLIF(current_setting('app.role', true), ''), 'guest') <> 'guest'
)""",
        "DROP POLICY IF EXISTS whistleblower_reports_update ON whistleblower_reports",
        """CREATE POLICY whistleblower_reports_update ON whistleblower_reports
FOR UPDATE
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
WITH CHECK (
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
        "DROP POLICY IF EXISTS whistleblower_reporter_profiles_identity_access "
        "ON whistleblower_reporter_profiles",
        """CREATE POLICY whistleblower_reporter_profiles_identity_access
ON whistleblower_reporter_profiles
FOR SELECT
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
        "DROP POLICY IF EXISTS whistleblower_reporter_profiles_insert "
        "ON whistleblower_reporter_profiles",
        """CREATE POLICY whistleblower_reporter_profiles_insert
ON whistleblower_reporter_profiles
FOR INSERT
WITH CHECK (
    current_setting('app.role', true) IN ('admin', 'auditor')
    OR EXISTS (
        SELECT 1 FROM whistleblower_reports r
        WHERE r.id = whistleblower_reporter_profiles.report_id
          AND r.created_by = NULLIF(current_setting('app.actor_id', true), '')::bigint
    )
)""",
        # 子テーブル・ACL テーブルは migration 024 と同一定義（N2: rls.py 未同期の解消）。
        # これらは常に既存 ACL（investigator 等）保有者のみが INSERT する経路しか
        # 無いため、FOR ALL のままでも「通報作成時に INSERT が拒否される」問題は
        # 発生しない。ただし ACL 保有者が誤って既存行を更新・削除できる余地は残る
        # ため、将来的な追加ハードニング対象として TODO 化する。
        "ALTER TABLE whistleblower_case_access ENABLE ROW LEVEL SECURITY",
        "DROP POLICY IF EXISTS whistleblower_case_access_self_or_admin "
        "ON whistleblower_case_access",
        """CREATE POLICY whistleblower_case_access_self_or_admin ON whistleblower_case_access
USING (
    current_setting('app.role', true) IN ('admin', 'auditor')
    OR user_id = NULLIF(current_setting('app.actor_id', true), '')::bigint
)""",
        "ALTER TABLE whistleblower_evidence ENABLE ROW LEVEL SECURITY",
        "DROP POLICY IF EXISTS whistleblower_evidence_case_access ON whistleblower_evidence",
        """CREATE POLICY whistleblower_evidence_case_access ON whistleblower_evidence
USING (
    current_setting('app.role', true) IN ('admin', 'auditor')
    OR EXISTS (
        SELECT 1 FROM whistleblower_case_access wca
        WHERE wca.report_id = whistleblower_evidence.report_id
          AND wca.user_id = NULLIF(current_setting('app.actor_id', true), '')::bigint
          AND wca.revoked_at IS NULL
          AND (wca.expires_at IS NULL OR wca.expires_at > now())
    )
)""",
        "ALTER TABLE whistleblower_interviews ENABLE ROW LEVEL SECURITY",
        "DROP POLICY IF EXISTS whistleblower_interviews_case_access ON whistleblower_interviews",
        """CREATE POLICY whistleblower_interviews_case_access ON whistleblower_interviews
USING (
    current_setting('app.role', true) IN ('admin', 'auditor')
    OR EXISTS (
        SELECT 1 FROM whistleblower_case_access wca
        WHERE wca.report_id = whistleblower_interviews.report_id
          AND wca.user_id = NULLIF(current_setting('app.actor_id', true), '')::bigint
          AND wca.revoked_at IS NULL
          AND (wca.expires_at IS NULL OR wca.expires_at > now())
    )
)""",
        "ALTER TABLE whistleblower_timeline_events ENABLE ROW LEVEL SECURITY",
        "DROP POLICY IF EXISTS whistleblower_timeline_events_case_access "
        "ON whistleblower_timeline_events",
        """CREATE POLICY whistleblower_timeline_events_case_access ON whistleblower_timeline_events
USING (
    current_setting('app.role', true) IN ('admin', 'auditor')
    OR EXISTS (
        SELECT 1 FROM whistleblower_case_access wca
        WHERE wca.report_id = whistleblower_timeline_events.report_id
          AND wca.user_id = NULLIF(current_setting('app.actor_id', true), '')::bigint
          AND wca.revoked_at IS NULL
          AND (wca.expires_at IS NULL OR wca.expires_at > now())
    )
)""",
        "ALTER TABLE whistleblower_actions ENABLE ROW LEVEL SECURITY",
        "DROP POLICY IF EXISTS whistleblower_actions_case_access ON whistleblower_actions",
        """CREATE POLICY whistleblower_actions_case_access ON whistleblower_actions
USING (
    current_setting('app.role', true) IN ('admin', 'auditor')
    OR EXISTS (
        SELECT 1 FROM whistleblower_case_access wca
        WHERE wca.report_id = whistleblower_actions.report_id
          AND wca.user_id = NULLIF(current_setting('app.actor_id', true), '')::bigint
          AND wca.revoked_at IS NULL
          AND (wca.expires_at IS NULL OR wca.expires_at > now())
    )
)""",
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
