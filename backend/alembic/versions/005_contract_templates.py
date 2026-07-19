"""Add persistent contract_templates table.

Revision ID: 005_contract_templates
Revises: 004_ai_provider_settings
Create Date: 2026-07-19

The `/templates` API previously served read-only seed data and returned 501
for template creation. This migration adds the persistent table and seeds the
five approved construction/legal templates so existing GET behavior remains
stable while POST can create durable records.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "005_contract_templates"
down_revision: str | Sequence[str] | None = "004_ai_provider_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_SEED_ROWS = [
    {
        "id": 1,
        "code": "TMPL-UKEOI-001",
        "name": "工事請負契約書（標準）",
        "contract_type": "請負",
        "description": "建設業法第18条に基づく工事請負契約の標準ひな形。",
        "body": (
            "工事請負契約書\n\n"
            "発注者（以下「甲」）と受注者（以下「乙」）は、以下のとおり工事請負契約を締結する。\n\n"
            "第1条（目的）\n甲は乙に対し、別紙仕様書に記載の工事（以下「本工事」）を請け負わせ、"
            "乙はこれを受注する。\n\n"
            "第2条（工期）\n本工事の工期は別紙に定めるとおりとする。\n\n"
            "第3条（請負代金）\n本工事の請負代金は別紙に定めるとおりとする。"
        ),
    },
    {
        "id": 2,
        "code": "TMPL-SHITAUKE-001",
        "name": "下請契約書（専門工事）",
        "contract_type": "請負",
        "description": "専門工事業者との下請契約ひな形。建設業法第24条の2以下の規定を考慮済み。",
        "body": (
            "下請契約書\n\n"
            "元請負人（以下「甲」）と下請負人（以下「乙」）は、下記のとおり下請契約を締結する。\n\n"
            "第1条（下請工事の内容）\n甲が請け負った工事のうち、別紙記載の工事を乙に下請負させる。\n\n"
            "第2条（下請代金）\n下請代金額は別紙に定めるとおりとし、"
            "甲は乙に対し完成検査合格後30日以内に支払う。\n\n"
            "第3条（工期）\n本工事の工期は別紙に定めるとおりとする。"
        ),
    },
    {
        "id": 3,
        "code": "TMPL-ITAKU-001",
        "name": "業務委託契約書（設計業務）",
        "contract_type": "委託",
        "description": "建築設計・監理業務を委託するためのひな形。",
        "body": (
            "業務委託契約書\n\n"
            "委託者（以下「甲」）と受託者（以下「乙」）は、以下のとおり業務委託契約を締結する。\n\n"
            "第1条（委託業務）\n甲は乙に対し、別紙仕様書記載の業務（以下「本業務」）を委託する。\n\n"
            "第2条（委託料）\n委託料は別紙に定めるとおりとし、業務完了後30日以内に支払う。\n\n"
            "第3条（再委託の禁止）\n乙は甲の書面による事前承諾なく本業務を第三者に再委託してはならない。"
        ),
    },
    {
        "id": 4,
        "code": "TMPL-NDA-001",
        "name": "秘密保持契約書",
        "contract_type": "秘密保持",
        "description": "入札前・設計前の機密情報開示に際して締結する NDA ひな形。",
        "body": (
            "秘密保持契約書\n\n"
            "開示者（以下「甲」）と受領者（以下「乙」）は、以下のとおり秘密保持契約を締結する。\n\n"
            "第1条（定義）\n「秘密情報」とは、甲が乙に開示する技術上・営業上の情報であって、"
            "開示の際に秘密である旨を明示したものをいう。\n\n"
            "第2条（秘密保持義務）\n乙は秘密情報を厳重に管理し、甲の事前承諾なく第三者に開示してはならない。\n\n"
            "第3条（有効期間）\n本契約の有効期間は締結日から3年間とする。"
        ),
    },
    {
        "id": 5,
        "code": "TMPL-JV-001",
        "name": "建設工事共同企業体（JV）協定書",
        "contract_type": "JV",
        "description": "特定建設工事共同企業体（特定 JV）の協定書ひな形。",
        "body": (
            "建設工事共同企業体協定書\n\n"
            "本協定書は、下記工事を共同で請け負うことを目的に組成する"
            "建設工事共同企業体（以下「本JV」）に関して、構成員間の権利義務を定める。\n\n"
            "第1条（目的）\n本JVは、別紙記載の工事を共同で請け負い遂行することを目的とする。\n\n"
            "第2条（出資比率・構成員）\n各構成員の出資比率は別紙に定めるとおりとする。\n\n"
            "第3条（代表者）\n本JVを代表するスポンサーを別紙に定める。"
        ),
    },
]


def upgrade() -> None:
    op.create_table(
        "contract_templates",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("contract_type", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT", use_alter=True),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT", use_alter=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_contract_templates_code"),
    )
    op.create_index(
        "ix_contract_templates_contract_type",
        "contract_templates",
        ["contract_type"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_contract_templates_active",
        "contract_templates",
        ["is_active"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    table = sa.table(
        "contract_templates",
        sa.column("id", sa.BigInteger()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("contract_type", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("body", sa.Text()),
        sa.column("is_active", sa.Boolean()),
        sa.column("version", sa.Integer()),
    )
    op.bulk_insert(
        table,
        [{**row, "is_active": True, "version": 1} for row in _SEED_ROWS],
    )
    op.execute(
        "SELECT setval(pg_get_serial_sequence('contract_templates', 'id'), "
        "(SELECT max(id) FROM contract_templates))"
    )


def downgrade() -> None:
    op.drop_index("ix_contract_templates_active", table_name="contract_templates")
    op.drop_index("ix_contract_templates_contract_type", table_name="contract_templates")
    op.drop_table("contract_templates")
