"""``evidence_hold_release_approvals`` に ``deleted_at`` を追加（モデル定義との整合）.

Revision ID: 027_hold_release_deleted_at
Revises: 026_rls_restrictive_scope
Create Date: 2026-09-28

``app.models.evidence.EvidenceHoldReleaseApproval`` は ``IntPKMixin`` と
``TimestampMixin`` を継承しているため、モデル側には ``created_at`` /
``updated_at`` / ``deleted_at`` の 3 列が定義されている。しかし
``025_evidence`` の ``create_table`` は ``created_at`` / ``updated_at`` しか
作っておらず、``deleted_at`` が欠落していた。

``GET /api/v1/evidence/hold-release-requests`` は
``EvidenceHoldReleaseApproval`` を SELECT するため、PostgreSQL では

    asyncpg.exceptions.UndefinedColumnError:
        column evidence_hold_release_approvals.deleted_at does not exist

で 500 を返していた（MVP backend / 2026-09-28 実測）。

モデル定義（79 テーブル）と実 DB の全列照合で唯一の不一致が本列である。

既存行が存在するため ``nullable=True`` で追加する。``deleted_at`` の意味論は
他テーブルの ``TimestampMixin`` と同一（NULL = 有効、非 NULL = 論理削除）で
あり、``server_default`` は不要（既存行は NULL のまま = 有効）。

注意: 適用は所有者ロール ``legalops_mvp`` として行うこと。所有者が変わると
RLS の適用主体が変わり（所有者は RLS をバイパスする）アプリの可視データが
黙って変わる。``backend/alembic/env.py`` の ``ALEMBIC_DB_ROLE`` を参照。

Revision ID を 32 文字以内に抑えている理由: ``alembic_version.version_num`` は
``character varying(32)`` であり、超えると ``upgrade`` の最終ステップ
（``UPDATE alembic_version``）で ``StringDataRightTruncationError`` になる
（DDL は同一トランザクションでロールバックされる）。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "027_hold_release_deleted_at"
down_revision: str | Sequence[str] | None = "026_rls_restrictive_scope"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "evidence_hold_release_approvals"


def upgrade() -> None:
    op.add_column(
        _TABLE,
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column(_TABLE, "deleted_at")
