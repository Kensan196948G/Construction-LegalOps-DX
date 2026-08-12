"""契約種別マスタ統合（表記揺れ・旧名称の正準値への正規化）.

Revision ID: 008_contract_type_master
Revises: 007_business_domain
Create Date: 2026-08-12

2026-08-12 まで ``contracts.contract_type`` 等に 3 系統の値が混在していた。
- backend テスト等: ``ukeoi`` / ``itaku``（romanized）
- 旧 enum: ``請負`` / ``委託`` / ``賃借`` / ``秘密保持``
- UI・シード: ``工事請負契約`` / ``業務委託契約`` / ``賃貸借契約`` / ``秘密保持契約``

本マイグレーションで正準値（UI 表示名）へ正規化する。正準値は
``app.models.enums.ContractType`` および ``app.services.contract_type`` を正とする。
DB カラムはカスタム種別許容のため CHECK 制約は追加しない。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "008_contract_type_master"
down_revision: str | Sequence[str] | None = "007_business_domain"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_NORMALIZE_CASE = sa.text(
    """
    CASE contract_type
        WHEN 'ukeoi' THEN '工事請負契約'
        WHEN 'itaku' THEN '業務委託契約'
        WHEN '請負' THEN '工事請負契約'
        WHEN '委託' THEN '業務委託契約'
        WHEN '賃借' THEN '賃貸借契約'
        WHEN '秘密保持' THEN '秘密保持契約'
        WHEN '工事請負' THEN '工事請負契約'
        WHEN '業務委託' THEN '業務委託契約'
        WHEN '資材購入' THEN '資材購入契約'
        WHEN '設計監理' THEN '設計監理契約'
        ELSE contract_type
    END
    """
)

_REVERSE_CASE = sa.text(
    """
    CASE contract_type
        WHEN '工事請負契約' THEN '請負'
        WHEN '業務委託契約' THEN '委託'
        WHEN '賃貸借契約' THEN '賃借'
        WHEN '秘密保持契約' THEN '秘密保持'
        ELSE contract_type
    END
    """
)


def upgrade() -> None:
    for table in ("contracts", "workflows", "contract_templates", "knowledge_articles"):
        columns = sa.inspect(op.get_bind()).get_columns(table)
        if any(c["name"] == "contract_type" for c in columns):
            op.execute(
                sa.text(f"UPDATE {table} SET contract_type = {_NORMALIZE_CASE.text} ")
            )


def downgrade() -> None:
    for table in ("contracts", "workflows", "contract_templates", "knowledge_articles"):
        columns = sa.inspect(op.get_bind()).get_columns(table)
        if any(c["name"] == "contract_type" for c in columns):
            op.execute(
                sa.text(f"UPDATE {table} SET contract_type = {_REVERSE_CASE.text} ")
            )
