#!/usr/bin/env python3
"""MVP デモデータ投入スクリプト。

使い方（backend コンテナ内で実行する前提）:
    docker cp scripts/seed_demo_data.py <backend-container>:/tmp/seed_demo_data.py
    docker exec -w /app <backend-container> python /tmp/seed_demo_data.py            # 投入
    docker exec -w /app <backend-container> python /tmp/seed_demo_data.py --dry-run  # 確認のみ
    docker exec -w /app <backend-container> python /tmp/seed_demo_data.py --delete   # デモデータ削除

方針:
  - 人物名・会社名・案件名はすべて「デモ」「見本」「サンプル」接頭辞付きの架空値のみ。
    実在企業・実在人物・実在案件は使用しない。
  - デモ行は識別子プレフィックス（CTR-2026- / DEMO- / DSP-2026- / PAY- / CHG-2026-）で
    判別でき、冪等（再実行しても重複しない）。
  - 監査ログ（append-only・削除不可）には demo フラグ付きで投入し、実監査と混同しない。
  - 主要画面（契約・レビュー・リスク・ワークフロー・協力会社・紛争・支払・変更契約・
    テンプレート・ナレッジ・通知）が空にならないよう主要テーブルを網羅する。
"""

from __future__ import annotations

import argparse
import asyncio
import os
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from app.db.session import AsyncSessionLocal
from app.models.app_settings import AiProviderSetting
from app.models.change_order import ChangeOrder
from app.models.clause import Clause
from app.models.contract import Contract
from app.models.contract_document import ContractDocument
from app.models.contract_template import ContractTemplate
from app.models.department import Department
from app.models.dispute import Dispute
from app.models.enums import UserRole
from app.models.ip_asset import IpAsset
from app.models.ip_document import IpDocument
from app.models.ip_watch import IpWatchEvent, IpWatchTarget
from app.models.knowledge_article import KnowledgeArticle
from app.models.labor_wage import LaborWageStandard
from app.models.legal_review import LegalReview
from app.models.matter import LegalMatter, MatterEvent, matter_contracts_table
from app.models.negotiation import ClauseNegotiationEvent
from app.models.notification import Notification
from app.models.obligation import ContractObligation
from app.models.outside_counsel import CounselLawyer, LawFirm, LegalEngagement
from app.models.partner import Partner
from app.models.partner_review import PartnerReview
from app.models.payment_record import PaymentRecord
from app.models.price_consultation import PriceConsultationLog
from app.models.joint_venture import JvAgreement, JvDispute, JvMember, JvSettlement, JointVenture
from app.models.public_works import ContractingAgency, OwnerNotification, PublicWorksConsultation
from app.models.risk_item import RiskItem
from app.models.signing import ESignatureEnvelope, ESignatureEvent
from app.models.standard_duration import StandardWorkDuration
from app.models.user import User
from app.models.workflow import Workflow, WorkflowStep
from app.services import audit_service, jv_service, partner_ext_service, price_consultation_service, public_works_service
from app.services.rls_context import set_rls_context
from sqlalchemy import delete, select, update

BASE_DATE = date(2026, 5, 16)

# 実在企業名を避けた明確な架空デモ会社（フロントエンド mock-data と同一表記）。
COMPANIES = [
    "みらい建設工業(株)",
    "さくら土木(株)",
    "(株)やまびこ設計事務所",
    "ひかり資材(株)",
    "(株)つばさ組",
    "あおぞらコンサルタント(株)",
    "北信電設(株)",
    "(株)はるか建材",
    "西陵工業(株)",
    "(株)きさらぎ設備",
    "みらいセメント商事(株)",
    "(株)ほしぞら工務店",
]

# 実在しない架空の案件名（実在地名・実在案件を含まない）。
PROJECTS = [
    "みらい北幹線道路補修工事",
    "ひかり町駅前再開発",
    "あおば港防波堤改修",
    "こまくさ川橋梁架替",
    "みらい都市トンネル補強",
    "つばさ市地下道整備",
]

# 定型的なプレースホルダー氏名（実在の特定個人ではない架空表記）。
PEOPLE = ["田中 太郎", "鈴木 花子", "佐藤 一郎", "山田 美咲", "高橋 健二", "伊藤 直美", "中村 裕子", "渡辺 誠"]

CONTRACT_TYPES = [
    "工事請負契約",
    "業務委託契約",
    "資材購入契約",
    "下請契約",
    "設計監理契約",
    "賃貸借契約",
    "秘密保持契約",
]
DEPARTMENTS = [
    ("LEGAL", "法務部"),
    ("CONSTRUCTION", "工事部"),
    ("ADMIN", "管理部"),
    ("SALES", "営業部"),
    ("DESIGN", "設計部"),
    ("GENERAL", "総務部"),
]
DEMO_USERS = [
    ("admin", "00000000-0000-0000-0000-000000000001", "田中 太郎"),
    ("viewer", "00000000-0000-0000-0000-000000000002", "鈴木 花子"),
    ("drafter", "00000000-0000-0000-0000-000000000003", "佐藤 一郎"),
    ("reviewer", "00000000-0000-0000-0000-000000000004", "山田 美咲"),
    ("approver", "00000000-0000-0000-0000-000000000005", "高橋 健二"),
    ("auditor", "00000000-0000-0000-0000-000000000006", "伊藤 直美"),
    ("guest", "00000000-0000-0000-0000-000000000007", "中村 裕子"),
]
AMOUNTS = [1200000, 3500000, 8900000, 15000000, 25000000, 48000000, 75000000, 120000000, 250000000, 500000000]

# mock の status を backend の CHECK 制約内へ写像
STATUS_MAP = {
    "draft": "draft",
    "in_review": "in_review",
    "approved": "approved",
    "pending_approval": "in_review",
    "expired": "archived",
    "archived": "archived",
}
REVIEW_STATUS_MAP = {
    "completed": "completed",
    "in_progress": "running",
    "pending_confirmation": "pending",
}
WF_STEP_STATUS_MAP = {
    "approved": "approved",
    "pending": "pending",
    "waiting": "pending",
    "rejected": "rejected",
}

REVIEW_ISSUES = [
    {
        "clause_seq": 3,
        "title": "契約金額・支払条件",
        "risk_level": "high",
        "comment": "支払期日が納品後60日を超えており、下請法第2条の4に違反する可能性があります。",
        "suggestion": "支払期日を受領日から60日以内に短縮する。",
        "citations": ["下請代金支払遅延等防止法 第2条の4"],
        "law_name": "下請代金支払遅延等防止法",
        "law_article": "第2条の4",
        "ai_confidence": 0.92,
        "verdict": "finding",
        "suggested_actions": [
            {
                "action": "replace",
                "target_clause_seq": 3,
                "description": "支払期日を60日以内へ変更する。",
                "replacement_text": "支払いは、納品確認後60日以内に行うものとする。",
            }
        ],
    },
    {
        "clause_seq": 7,
        "title": "解除条項",
        "risk_level": "critical",
        "comment": "発注者側からの一方的解除が不当に広く認められており、建設業法第19条の3に抵触する恐れがあります。",
        "suggestion": "解除事由を限定し、書面による催告手続を追加する。",
        "citations": ["建設業法 第19条の3"],
        "law_name": "建設業法",
        "law_article": "第19条の3",
        "ai_confidence": 0.88,
        "verdict": "finding",
        "suggested_actions": [
            {
                "action": "replace",
                "target_clause_seq": 7,
                "description": "催告後30日以内の是正を解除条件とする。",
                "replacement_text": "甲は、乙が重大な違反をし、書面による催告後30日以内に是正されない場合に限り解除できる。",
            }
        ],
    },
    {
        "clause_seq": 8,
        "title": "損害賠償",
        "risk_level": "medium",
        "comment": "損害賠償の上限条項がなく、過大なリスク負担となる可能性があります。",
        "suggestion": "契約金額を上限とする賠償上限条項を追加する。",
        "citations": [],
        "ai_confidence": 0.85,
        "verdict": "finding",
        "suggested_actions": [
            {
                "action": "add",
                "target_clause_seq": 8,
                "description": "賠償総額の上限を契約金額とする。",
                "replacement_text": "損害賠償の総額は、契約金額を上限とする。ただし故意または重過失による場合はこの限りでない。",
            }
        ],
    },
    {
        "clause_seq": 4,
        "title": "工期",
        "risk_level": "medium",
        "comment": "天候不順や不可抗力による工期延長の条件が具体的に定められていません。",
        "suggestion": "不可抗力による工期延長の要件と手続を明記する。",
        "citations": [],
        "ai_confidence": 0.78,
        "verdict": "needs_human_review",
        "suggested_actions": [],
    },
    {
        "clause_seq": 9,
        "title": "秘密保持",
        "risk_level": "low",
        "comment": "秘密情報の範囲が「一切の情報」と定義されており、実務上の運用が困難です。",
        "suggestion": "秘密情報の定義を具体的に列挙する。",
        "citations": [],
        "ai_confidence": 0.7,
        "verdict": "finding",
        "suggested_actions": [],
    },
    {
        "clause_seq": 5,
        "title": "検査・引渡し",
        "risk_level": "medium",
        "comment": "検査期間が7日と設定されていますが、工事の規模に対して不十分な可能性があります。",
        "suggestion": "検査期間を工事規模に応じて延長する。",
        "citations": [],
        "ai_confidence": 0.72,
        "verdict": "finding",
        "suggested_actions": [],
    },
]

SUGGESTED_ACTIONS = [
    {
        "action": "replace",
        "target_clause_seq": 3,
        "description": "支払期日を60日以内に短縮し、下請法の定めに従う旨を明記する。",
        "replacement_text": "支払いは、納品確認後60日以内に行うものとする。なお、下請法の適用がある場合は同法の定めに従う。",
    },
    {
        "action": "replace",
        "target_clause_seq": 7,
        "description": "解除事由の限定と書面催告手続を追加する。",
        "replacement_text": "甲は、乙が重大な違反をし、書面による催告後30日以内に是正されない場合に限り解除できる。",
    },
    {
        "action": "add",
        "target_clause_seq": 8,
        "description": "契約金額を上限とする賠償上限条項を追加する。",
        "replacement_text": "損害賠償の総額は、契約金額を上限とする。ただし故意または重過失による場合はこの限りでない。",
    },
]

KNOWLEDGE_ITEMS = [
    ("建設業法 第19条の解説と実務上の留意点", "建設業法", "契約書面の交付義務と実務上の留意点について解説します。"),
    ("下請法における支払期日の遵守について", "下請法", "下請代金の支払期日（60日ルール）と書面交付の要点をまとめます。"),
    ("電子帳簿保存法 — 契約書の電子保存要件", "電子帳簿保存法", "電子取引データの保存要件と検索要件を整理します。"),
    ("工事請負契約のリスクチェックリスト", "社内規程", "工事請負契約のレビュー時に確認すべき項目のチェックリストです。"),
    ("反社会的勢力排除条項の標準文言", "コンプライアンス", "反社会的勢力排除条項の標準的な文言と導入時の注意点です。"),
    ("【相談事例】下請契約の検収時期と支払期日の起算", "下請法", "下請契約における検収の実施時期と、60日ルール上の支払期日の起算点に関する相談事例です。"),
    ("【相談事例】一括下請負の禁止と例外の判断", "建設業法", "一括下請負の禁止規定と、例外的に認められるケースの判断基準を整理した相談事例です。"),
    ("【相談事例】契約不適合責任の期間制限", "民法", "契約不適合責任を追及できる期間と、契約書の特約による伸長の可否に関する相談事例です。"),
    ("【相談事例】主任技術者の専任要件と兼務の可否", "建設業法", "現場ごとの主任技術者専任要件と、兼務が認められる範囲に関する相談事例です。"),
]

NOTIFICATIONS = [
    ("契約 CTR-2026-0003 の承認期限が3日後です", "contract", "warning"),
    ("AIレビュー REV-0005 が完了しました", "review", "info"),
    ("ワークフロー WF-DEMO-0002 が承認されました", "workflow", "success"),
    ("契約 CTR-2026-0008 の期限が30日後に迫っています", "contract", "warning"),
    ("新しい法令改正情報が追加されました", "knowledge", "info"),
]

PARTNERS = [
    ("みらい建設工業(株)", "元請", "デモ大臣許可（般-2026）第000001号", "confirmed", True, True, "low"),
    ("さくら土木(株)", "元請", "デモ大臣許可（般-2026）第000002号", "confirmed", True, True, "low"),
    ("(株)やまびこ設計事務所", "元請", "デモ大臣許可（般-2026）第000003号", "confirmed", True, False, "low"),
    ("ひかり資材(株)", "材料", "デモ大臣許可（般-2026）第000004号", "confirmed", True, True, "medium"),
    ("(株)つばさ組", "下請", "デモ都知事許可（般-2026）第000005号", "confirmed", True, True, "low"),
    ("あおぞらコンサルタント(株)", "専門工事", "デモ県知事許可（般-2026）第000006号", "pending", True, False, "medium"),
    ("北信電設(株)", "専門工事", "デモ県知事許可（般-2026）第000007号", "confirmed", True, True, "medium"),
    ("(株)はるか建材", "材料", "デモ県知事許可（般-2026）第000008号", "confirmed", True, True, "low"),
    ("(株)きさらぎ設備", "専門工事", "デモ県知事許可（般-2026）第000009号", "unconfirmed", False, False, "high"),
    ("西陵工業(株)", "輸送", "デモ大臣許可（般-2026）第000010号", "confirmed", True, True, "low"),
    ("みらいセメント商事(株)", "その他", "デモ都知事許可（般-2026）第000011号", "pending", True, False, "medium"),
    ("(株)ほしぞら工務店", "材料", "デモ大臣許可（般-2026）第000012号", "confirmed", True, True, "low"),
]

DISPUTES = [
    ("DSP-2026-0001", "delay", "みらい北幹線道路補修工事の工期延長費用", "open", "高", 15000000, "みらい建設工業(株)"),
    ("DSP-2026-0002", "defect", "ひかり町駅前再開発の施工品質是正要求", "investigating", "高", 8000000, "さくら土木(株)"),
    ("DSP-2026-0003", "claim", "あおば港防波堤改修の追加費用請求", "escalated", "中", 2500000, "(株)やまびこ設計事務所"),
    ("DSP-2026-0004", "payment", "こまくさ川橋梁架替の下請代金支払条件", "open", "中", None, "ひかり資材(株)"),
    ("DSP-2026-0005", "accident", "みらい都市トンネル補強の安全対策協議", "resolved", "中", 5000000, "(株)つばさ組"),
    ("DSP-2026-0006", "labor", "つばさ市地下道整備の労務環境相談", "closed", "低", 1200000, "あおぞらコンサルタント(株)"),
]

CHANGE_ORDERS = [
    ("CHG-2026-0001", "additional_work", "みらい北幹線道路補修工事 追加工事", "approved", 12000000, 14, "notice_sent"),
    ("CHG-2026-0002", "design_change", "ひかり町駅前再開発 設計変更", "in_consultation", 6500000, 21, "notice_sent"),
    ("CHG-2026-0003", "schedule_extension", "あおば港防波堤改修 工期延長", "approved", None, 30, "approved"),
    ("CHG-2026-0004", "price_slide", "こまくさ川橋梁架替 スライド請求", "registered", 9800000, 0, "registered"),
    ("CHG-2026-0005", "claim", "みらい都市トンネル補強 クレーム", "in_consultation", 4200000, 7, "notice_sent"),
    ("CHG-2026-0006", "additional_work", "つばさ市地下道整備 追加工事", "registered", 15000000, 10, "registered"),
]

TEMPLATES = [
    ("DEMO-UC-001", "工事請負契約ひな形（デモ）", "工事請負契約", "工事請負契約の標準ひな形（デモ用）。契約金額・工期・支払条件・解除条項を含む。"),
    ("DEMO-NDA-001", "秘密保持契約ひな形（デモ）", "秘密保持契約", "秘密保持契約の標準ひな形（デモ用）。秘密情報の定義と開示範囲を含む。"),
    ("DEMO-BP-001", "業務委託契約ひな形（デモ）", "業務委託契約", "業務委託契約の標準ひな形（デモ用）。委託範囲と再委託条件を含む。"),
    ("DEMO-SC-001", "下請契約ひな形（デモ）", "下請契約", "下請契約の標準ひな形（デモ用）。60日ルール対応の支払条項を含む。"),
    ("DEMO-SD-001", "設計監理契約ひな形（デモ）", "設計監理契約", "設計監理契約の標準ひな形（デモ用）。業務範囲と報酬条件を含む。"),
]

# 契約ごとに展開する標準条項（架空文言）。
CLAUSE_TEMPLATES = [
    ("第1条（目的）", "本契約は、発注者と受注者との間で、対象工事の施工に関し必要な事項を定めることを目的とする（デモ）。", None),
    ("第2条（工事内容）", "工事内容は別紙「工事内訳明細書」のとおりとする（デモ）。", "low"),
    ("第3条（契約金額）", "契約金額は別紙のとおりとし、支払いは納品確認後60日以内に行う（デモ）。", "medium"),
    ("第4条（工期）", "工期は契約締結日から180日間とする。天候不順等による延長は協議により定める（デモ）。", "medium"),
    ("第5条（検査・引渡し）", "工事完成後、発注者は14日以内に完成検査を行う（デモ）。", "low"),
    ("第6条（契約不適合責任）", "契約不適合が判明したときは、受注者は速やかに補修または代替を行う（デモ）。", "high"),
    ("第7条（解除）", "当事者は、相手方が本契約に重大な違反をした場合、書面による催告後30日以内に是正されないときに限り本契約を解除できる（デモ）。", "critical"),
    ("第8条（損害賠償）", "本契約に基づく損害賠償の総額は、契約金額を上限とする。ただし故意または重過失による場合はこの限りでない（デモ）。", "medium"),
    ("第9条（秘密保持）", "当事者は、本契約に関して知り得た相手方の秘密情報を第三者に開示してはならない（デモ）。", "low"),
]

# 契約パッケージ文書（添付ファイル不要のメタデータ型文書）。
DOCUMENT_TEMPLATES = [
    ("contract", "工事請負契約書（デモ）", 1),
    ("spec", "工事内訳明細書（デモ）", 2),
    ("site_rule", "現場施工要領書（デモ）", 3),
]


def contract_title(i: int) -> str:
    return f"{CONTRACT_TYPES[i % len(CONTRACT_TYPES)]}（{COMPANIES[i % len(COMPANIES)]}・{PROJECTS[i % len(PROJECTS)]}）"


def _demo_payload(**extra: object) -> dict[str, object]:
    return {"demo": True, **extra}


async def _ensure_demo_user(session, departments) -> User:
    """MVP 用デモ管理者を JIT 解決ロジックと同一の oid で作成する。

    backend の dev bypass（APP_ENV=staging + AUTH_DEV_BYPASS=true）が
    DEV_USER_ID を subject として解決するユーザーと同一行を指すように、
    entra_oid = UUID(DEV_USER_ID) で作成する。
    """
    raw_id = (os.getenv("DEV_USER_ID", "") or "00000000-0000-0000-0000-000000000001").strip()
    email = (os.getenv("DEV_USER_EMAIL", "") or "demo@legalops-mvp.example.com").strip().lower()
    role = (os.getenv("DEV_USER_ROLE", "") or "admin").strip().lower()
    allowed_roles = {r.value for r in UserRole}
    if role not in allowed_roles:
        role = "admin"
    oid = uuid.UUID(raw_id)

    existing = (
        await session.execute(select(User).where(User.entra_oid == oid))
    ).scalar_one_or_none()
    if existing is not None:
        if existing.department_id is None:
            existing.department_id = departments["法務部"].id
        return existing

    user = User(
        entra_oid=oid,
        email=email,
        display_name="デモ管理者（田中 太郎）",
        department_id=departments["法務部"].id,
        role=role,
        is_active=True,
        attributes={"demo": True},
    )
    session.add(user)
    await session.flush()
    return user


async def _repair_invalid_demo_emails(session) -> int:
    """Fix JIT/dev-bypass rows whose reserved-domain email fails EmailStr.

    The original dev bypass default ``*.example.invalid`` is a reserved domain
    rejected by pydantic ``EmailStr``, which made ``GET /users`` 500 on the MVP.
    Rewrite legacy rows to a valid, clearly fictional domain.
    """
    rows = (
        await session.execute(select(User).where(User.email.like("%.invalid")))
    ).scalars().all()
    for row in rows:
        local = (row.role or "user").lower()
        row.email = f"{local}@legalops-mvp.example.com"
    return len(rows)


async def ensure_demo_users(session, departments) -> dict[str, User]:
    """Seed one fictional user per RBAC role so the settings/users tab is operable."""
    by_oid: dict[str, User] = {}
    for idx, (role, raw_oid, name) in enumerate(DEMO_USERS):
        oid = uuid.UUID(raw_oid)
        existing = (
            await session.execute(select(User).where(User.entra_oid == oid))
        ).scalar_one_or_none()
        if existing is None:
            dept = departments[DEPARTMENTS[idx % len(DEPARTMENTS)][1]]
            existing = User(
                entra_oid=oid,
                email=f"{role}@legalops-mvp.example.com",
                display_name=name,
                department_id=dept.id,
                role=role,
                is_active=True,
                attributes={"demo": True},
            )
            session.add(existing)
            await session.flush()
        elif existing.email and existing.email.endswith(".invalid"):
            existing.email = f"{role}@legalops-mvp.example.com"
        by_oid[raw_oid] = existing
    return by_oid


async def ensure_departments(session) -> dict[str, Department]:
    existing = (await session.execute(select(Department))).scalars().all()
    by_name = {d.name: d for d in existing}
    by_code = {d.code: d for d in existing}
    for code, name in DEPARTMENTS:
        if code in by_code:
            by_name[name] = by_code[code]
            continue
        if name not in by_name:
            dept = Department(code=code, name=name)
            session.add(dept)
            await session.flush()
            by_name[name] = dept
    return by_name


async def _log(session, user: User, action: str, target_type: str, target_id: int, **payload: object) -> None:
    """デモフラグ付き監査ログ。実監査と混同しないよう demo=True を必ず載せる。"""
    await audit_service.log(
        session,
        actor_id=user.id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        payload=_demo_payload(**payload),
    )


async def seed(session, *, dry_run: bool) -> dict[str, int]:
    counts: dict[str, int] = {}
    departments = await ensure_departments(session)
    legal_dept = departments["法務部"]
    user = await _ensure_demo_user(session, departments)
    await _repair_invalid_demo_emails(session)
    await ensure_demo_users(session, departments)

    existing_providers = set(
        (await session.execute(select(AiProviderSetting.provider))).scalars()
    )
    provider_count = 0
    for provider, model in (("perplexity", "sonar"), ("deepseek", "deepseek-chat")):
        if provider in existing_providers:
            continue
        session.add(
            AiProviderSetting(
                provider=provider,
                model=model,
                is_active=True,
            )
        )
        provider_count += 1
    counts["ai_provider_settings"] = provider_count

    # PG 16 の RLS を管理者権限で適用（SQLite では no-op）。
    try:
        await set_rls_context(session, actor_id=user.id, role=user.role, email=user.email)
    except Exception:  # pragma: no cover - SQLite 等のフォールバック
        pass

    existing_nos = set((await session.execute(select(Contract.contract_no))).scalars())
    contracts: list[Contract] = []
    for i in range(22):
        no = f"CTR-2026-{i + 1:04d}"
        if no in existing_nos:
            continue
        risk_level = ["low", "medium", "high", "critical"][i % 4]
        risk_score = {"low": 20, "medium": 50, "high": 70, "critical": 88}[risk_level]
        contract = Contract(
            contract_no=no,
            title=contract_title(i),
            counterparty=COMPANIES[i % len(COMPANIES)],
            contract_type=CONTRACT_TYPES[i % len(CONTRACT_TYPES)],
            amount=Decimal(AMOUNTS[i % len(AMOUNTS)]),
            start_date=BASE_DATE - timedelta(days=90 + i),
            end_date=BASE_DATE + timedelta(days=180 + i * 7),
            department_id=legal_dept.id,
            drafter_id=user.id,
            confidentiality="normal",
            status=STATUS_MAP[["draft", "in_review", "approved", "pending_approval", "expired", "archived"][i % 6]],
            extra_metadata={
                "demo": True,
                "project": PROJECTS[i % len(PROJECTS)],
                "risk_level": risk_level,
                "risk_score": risk_score,
                "has_review": i < 15,
                "review_count": (i % 3) + 1 if i < 15 else 0,
            },
        )
        session.add(contract)
        contracts.append(contract)
        existing_nos.add(no)
    await session.flush()
    counts["contracts"] = len(contracts)

    demo_contracts = (
        await session.execute(select(Contract).where(Contract.contract_no.like("CTR-2026-%")).order_by(Contract.contract_no))
    ).scalars().all()

    # --- 契約条項スナップショット ---
    existing_clause_contracts = set(
        (await session.execute(select(Clause.contract_id).distinct())).scalars()
    )
    clause_count = 0
    for contract in contracts[:12]:
        if contract.id in existing_clause_contracts:
            continue
        for seq, (title, body, risk_level) in enumerate(CLAUSE_TEMPLATES, start=1):
            session.add(
                Clause(
                    contract_id=contract.id,
                    seq=seq,
                    title=title,
                    body=body,
                    risk_level=risk_level,
                    ai_findings={"demo": True, "issues": 1 if risk_level in {"high", "critical"} else 0},
                )
            )
            clause_count += 1
        existing_clause_contracts.add(contract.id)
    await session.flush()
    counts["clauses"] = clause_count

    # --- 契約パッケージ文書 ---
    existing_doc_contracts = set(
        (await session.execute(select(ContractDocument.contract_id).distinct())).scalars()
    )
    doc_count = 0
    for contract in contracts[:10]:
        if contract.id in existing_doc_contracts:
            continue
        for doc_type, title, priority in DOCUMENT_TEMPLATES:
            session.add(
                ContractDocument(
                    contract_id=contract.id,
                    doc_type=doc_type,
                    title=title,
                    priority=priority,
                    doc_date=contract.start_date,
                    amount_jpy=int(contract.amount) if priority == 2 and contract.amount else None,
                    start_date=contract.start_date,
                    end_date=contract.end_date,
                    content=f"{title}の内容（デモ用・架空文言）。",
                    version=1,
                )
            )
            doc_count += 1
        existing_doc_contracts.add(contract.id)
    await session.flush()
    counts["contract_documents"] = doc_count

    review_contracts = demo_contracts[:15]

    existing_reviews = set(
        (await session.execute(select(LegalReview.contract_id).where(LegalReview.contract_id.in_([c.id for c in review_contracts])))).scalars()
    )
    reviews: list[LegalReview] = []
    for idx, contract in enumerate(review_contracts):
        if contract.id in existing_reviews:
            continue
        mock_status = ["completed", "in_progress", "pending_confirmation"][idx % 3]
        risk_level = ["low", "medium", "high", "critical"][idx % 4]
        risk_score = {"low": 20, "medium": 50, "high": 70, "critical": 88}[risk_level]
        issues = REVIEW_ISSUES[: (idx % 4) + 2]
        suggested_actions = SUGGESTED_ACTIONS[: (idx % 2) + 1]
        review = LegalReview(
            contract_id=contract.id,
            review_type="hybrid",
            status=REVIEW_STATUS_MAP[mock_status],
            ai_model="deepseek-chat",
            summary="本契約について、下請法・建設業法の観点から指摘事項が検出されました。",
            overall_risk=risk_level,
            risk_score=risk_score,
            result={"issues": issues, "suggested_actions": suggested_actions, "demo": True},
            started_at=datetime(2026, 5, 1, 9, 0, tzinfo=UTC) + timedelta(days=idx),
            finished_at=(
                datetime(2026, 5, 4, 17, 0, tzinfo=UTC) + timedelta(days=idx)
                if mock_status == "completed"
                else None
            ),
            reviewer_id=user.id,
        )
        session.add(review)
        reviews.append(review)
    await session.flush()
    counts["reviews"] = len(reviews)
    # 旧シード行（demo-ai-model）を DeepSeek 表記へ更新（冪等 fix-up）。
    await session.execute(
        update(LegalReview)
        .where(LegalReview.ai_model == "demo-ai-model")
        .values(ai_model="deepseek-chat")
    )

    risk_count = 0
    for idx, review in enumerate(reviews):
        contract = review_contracts[idx]
        issues = (review.result or {}).get("issues", [])
        for issue in issues[:3]:
            session.add(
                RiskItem(
                    contract_id=contract.id,
                    legal_review_id=review.id,
                    category="契約条項",
                    severity=issue.get("risk_level", "medium"),
                    probability="medium",
                    impact="medium",
                    description=issue.get("comment", ""),
                    mitigation="",
                    recommendation=issue.get("title") or issue.get("suggestion") or "",
                    status="open",
                    owner_id=user.id,
                    due_date=BASE_DATE + timedelta(days=14),
                )
            )
            risk_count += 1
    counts["risk_items"] = risk_count

    workflow = (
        await session.execute(select(Workflow).where(Workflow.code == "DEMO-LEGAL-001"))
    ).scalar_one_or_none()
    if workflow is None:
        workflow = Workflow(
            code="DEMO-LEGAL-001",
            name="法務レビュー → 部門長承認（デモ）",
            description="MVP デモ相当の承認ワークフロー定義。",
            definition={
                "steps": [
                    {"seq": 1, "name": "法務担当レビュー", "step_type": "legal_review"},
                    {"seq": 2, "name": "法務リード承認", "step_type": "legal_review"},
                    {"seq": 3, "name": "部門長承認", "step_type": "manager_approval"},
                ]
            },
        )
        session.add(workflow)
        await session.flush()
        counts["workflow_definitions"] = 1
    else:
        counts["workflow_definitions"] = 0

    wf_contracts = demo_contracts[:10]
    existing_steps = set(
        (await session.execute(select(WorkflowStep.contract_id).where(WorkflowStep.contract_id.in_([c.id for c in wf_contracts])))).scalars()
    )
    step_count = 0
    step_defs = [
        ("法務担当レビュー", "legal_review", "approved", -3),
        ("法務リード承認", "legal_review", "approved", -1),
        ("部門長承認", "manager_approval", "pending", 3),
    ]
    for idx, contract in enumerate(wf_contracts):
        if contract.id in existing_steps:
            continue
        for seq, (name, step_type, status, day_offset) in enumerate(step_defs, start=1):
            mock_status = "approved" if idx >= 3 or seq < 3 else ("pending" if seq == 3 else "approved")
            decided = datetime(2026, 5, 12, 15, 0, tzinfo=UTC) + timedelta(days=seq) if mock_status == "approved" else None
            session.add(
                WorkflowStep(
                    workflow_id=workflow.id,
                    contract_id=contract.id,
                    seq=seq,
                    name=name,
                    step_type=step_type,
                    assignee_id=user.id,
                    status=WF_STEP_STATUS_MAP[mock_status],
                    due_at=datetime(2026, 5, 20, 18, 0, tzinfo=UTC) + timedelta(days=day_offset),
                    decided_at=decided,
                    decision_note="（デモデータ）" if mock_status == "approved" else None,
                )
            )
            step_count += 1
    counts["workflow_steps"] = step_count

    # --- 協力会社台帳 ---
    existing_partner_names = set((await session.execute(select(Partner.name))).scalars())
    partners: list[Partner] = []
    for idx, (name, ptype, permit_no, anti_social, social, ccus, risk) in enumerate(PARTNERS):
        if name in existing_partner_names:
            continue
        partner = Partner(
            name=name,
            partner_type=ptype,
            permit_number=permit_no,
            permit_types=["特定建設業"] if idx % 3 == 0 else ["一般建設業"],
            permit_specific=(idx % 2 == 0),
            permit_expiry=BASE_DATE + timedelta(days=90 + idx * 15),
            social_insurance_joined=social,
            ccus_registered=ccus,
            ccus_expiry=BASE_DATE + timedelta(days=300 + idx * 10),
            supervisor_qualifications=["1級施工管理技士"] if idx % 2 == 0 else [],
            business_evaluation={"score": 60 + idx, "grade": "A" if idx % 3 == 0 else "B"},
            anti_social_check=anti_social,
            anti_social_checked_at=BASE_DATE - timedelta(days=30 + idx),
            bankruptcy_risk="low" if idx % 4 else "medium",
            insurance_joined=social,
            re_subcontract=(idx >= 4),
            last_transaction=BASE_DATE - timedelta(days=idx * 4),
            risk_level=risk,
            notes="（デモデータ）架空の協力会社です。" if idx == 0 else None,
        )
        session.add(partner)
        partners.append(partner)
        existing_partner_names.add(name)
    await session.flush()
    counts["partners"] = len(partners)

    # --- 紛争台帳 ---
    existing_dispute_nos = set((await session.execute(select(Dispute.dispute_no))).scalars())
    disputes: list[Dispute] = []
    for idx, (no, dtype, title, status, priority, amount, counterparty) in enumerate(DISPUTES):
        if no in existing_dispute_nos:
            continue
        dispute = Dispute(
            dispute_no=no,
            contract_id=demo_contracts[idx % len(demo_contracts)].id if demo_contracts else None,
            dispute_type=dtype,
            title=f"{title}（デモ）",
            description="MVP デモ用の架空紛争案件です。実在の紛争・当事者とは一切関係ありません。",
            status=status,
            priority=priority,
            counterparty=counterparty,
            amount_claimed_jpy=amount,
            reserve_amount_jpy=(amount // 2) if amount else None,
            assignee_id=user.id,
            statute_limitations_date=BASE_DATE + timedelta(days=365 + idx * 30),
            notice_deadline=BASE_DATE + timedelta(days=7 + idx * 5),
            resolution_method="negotiation",
            exposure={"demo": True, "estimated": amount},
        )
        session.add(dispute)
        disputes.append(dispute)
        existing_dispute_nos.add(no)
    await session.flush()
    counts["disputes"] = len(disputes)

    # --- 支払イベント正本（60日ルール判定用）---
    existing_payment_nos = set((await session.execute(select(PaymentRecord.record_no))).scalars())
    payment_count = 0
    for idx, contract in enumerate(demo_contracts[:8]):
        events = [
            ("order", "scheduled", contract.start_date - timedelta(days=5), contract.amount),
            ("receipt", "checked", contract.start_date + timedelta(days=20), contract.amount),
            ("inspection", "checked", contract.start_date + timedelta(days=45), contract.amount),
            ("payment", "paid" if idx % 2 == 0 else "late", contract.start_date + timedelta(days=55 if idx % 2 == 0 else 75), contract.amount),
        ]
        for seq, (rtype, status, event_date, amount) in enumerate(events, start=1):
            no = f"PAY-{contract.contract_no}-{seq:02d}"
            if no in existing_payment_nos:
                continue
            session.add(
                PaymentRecord(
                    contract_id=contract.id,
                    record_no=no,
                    record_type=rtype,
                    event_date=event_date,
                    amount_jpy=int(amount) if amount else None,
                    related_to="デモ支払イベント",
                    payment_due_date=(event_date + timedelta(days=60)) if rtype == "receipt" else None,
                    payment_method="bank_transfer" if rtype == "payment" else None,
                    status=status,
                    note="（デモデータ）架空の支払イベントです。",
                )
            )
            payment_count += 1
            existing_payment_nos.add(no)
    await session.flush()
    counts["payment_records"] = payment_count

    # --- 変更契約 ---
    existing_change_nos = set((await session.execute(select(ChangeOrder.change_no))).scalars())
    change_orders: list[ChangeOrder] = []
    for idx, (no, ctype, title, status, amount, schedule_days, _deadline_status) in enumerate(CHANGE_ORDERS):
        if no in existing_change_nos:
            continue
        contract = demo_contracts[idx % len(demo_contracts)] if demo_contracts else None
        change_order = ChangeOrder(
            contract_id=contract.id if contract else None,
            change_no=no,
            change_type=ctype,
            title=f"{title}（デモ）",
            description="MVP デモ用の架空変更契約です。実在の工事・発注とは一切関係ありません。",
            requested_by=PEOPLE[idx % len(PEOPLE)],
            requested_at=BASE_DATE - timedelta(days=20 - idx * 2),
            response_deadline=BASE_DATE + timedelta(days=10 + idx),
            status=status,
            amount_jpy=amount,
            schedule_impact_days=schedule_days,
            forfeiture_warning=None,
            evidence_summary={"demo": True, "count": idx % 3},
            original_amount_jpy=int(contract.amount) if contract else None,
            cumulative_after_jpy=(int(contract.amount) + amount) if contract and amount else None,
        )
        session.add(change_order)
        change_orders.append(change_order)
        existing_change_nos.add(no)
    await session.flush()
    counts["change_orders"] = len(change_orders)

    # --- 契約テンプレート ---
    existing_template_codes = set((await session.execute(select(ContractTemplate.code))).scalars())
    template_count = 0
    for code, name, ctype, description in TEMPLATES:
        if code in existing_template_codes:
            continue
        session.add(
            ContractTemplate(
                code=code,
                name=name,
                contract_type=ctype,
                description=description,
                body=(
                    f"第1条（目的）\n本契約は、{name}に基づき、当事者間の合意事項を定める（デモ用）。\n"
                    "第2条（契約金額）\n契約金額は別紙のとおり。\n"
                    "第3条（支払条件）\n納品確認後60日以内に支払う。\n"
                ),
                is_active=True,
                version=1,
            )
        )
        template_count += 1
    counts["contract_templates"] = template_count

    # --- ナレッジ ---
    existing_knowledge = set((await session.execute(select(KnowledgeArticle.title))).scalars())
    knowledge_count = 0
    for title, category, body in KNOWLEDGE_ITEMS:
        if title in existing_knowledge:
            continue
        session.add(
            KnowledgeArticle(
                title=title,
                body=body,
                contract_type=None,
                tags=["デモ", category],
                citations=[],
                author_id=user.id,
            )
        )
        knowledge_count += 1
    counts["knowledge_articles"] = knowledge_count

    # --- 通知 ---
    existing_notif = set((await session.execute(select(Notification.subject))).scalars())
    notif_count = 0
    for subject, category, level in NOTIFICATIONS:
        if subject in existing_notif:
            continue
        session.add(
            Notification(
                recipient_id=user.id,
                contract_id=demo_contracts[0].id if demo_contracts else None,
                channel="in_app",
                category=category,
                subject=subject,
                body=f"[DEMO] {subject}",
                payload={"demo": True, "level": level},
                status="sent",
                sent_at=datetime.now(UTC),
            )
        )
        notif_count += 1
    counts["notifications"] = notif_count

    # --- 知財管理（JPO 特許情報取得 API 連携のデモデータ）---
    existing_apps = set(
        (await session.execute(select(IpAsset.application_number))).scalars()
    )
    ip_assets: list[IpAsset] = []
    demo_ip_data = [
        {
            "application_number": "2026000001",
            "ip_type": "patent",
            "invention_title": "建設現場の安全管理システム（デモ）",
            "filing_date": date(2026, 1, 15),
            "publication_number": "2026000001",
            "registration_number": "7000001",
            "status": "登録",
            "applicants": [
                {
                    "applicantAttorneyCd": "000000001",
                    "name": "みらい建設工業(株)",
                    "applicantAttorneyClass": "1",
                }
            ],
            "jplatpat_url": "https://www.j-platpat.inpit.go.jp/c1800/PU/JP-2026-000001/15/ja",
            "progress_data": {
                "applicationNumber": "2026000001",
                "inventionTitle": "建設現場の安全管理システム（デモ）",
                "progress": [
                    {"progressCode": "110", "progressDate": "20260115", "progressDetail": "出願"},
                    {"progressCode": "160", "progressDate": "20260701", "progressDetail": "公開"},
                    {"progressCode": "210", "progressDate": "20260720", "progressDetail": "審査請求"},
                    {"progressCode": "400", "progressDate": "20260930", "progressDetail": "登録"},
                ],
            },
            "registration_data": {
                "applicationNumber": "2026000001",
                "registrationNumber": "7000001",
                "registrationDate": "20260930",
            },
        },
        {
            "application_number": "2026000002",
            "ip_type": "patent",
            "invention_title": "建設機械の遠隔監視装置（デモ）",
            "filing_date": date(2026, 2, 10),
            "status": "審査請求",
            "applicants": [
                {
                    "applicantAttorneyCd": "000000001",
                    "name": "みらい建設工業(株)",
                    "applicantAttorneyClass": "1",
                }
            ],
            "progress_data": {
                "applicationNumber": "2026000002",
                "progress": [
                    {"progressCode": "110", "progressDate": "20260210", "progressDetail": "出願"},
                    {"progressCode": "210", "progressDate": "20260301", "progressDetail": "審査請求"},
                ],
            },
        },
    ]
    for item in demo_ip_data:
        if item["application_number"] in existing_apps:
            continue
        asset = IpAsset(
            application_number=item["application_number"],
            ip_type=item["ip_type"],
            invention_title=item["invention_title"],
            filing_date=item["filing_date"],
            applicants=item["applicants"],
            publication_number=item.get("publication_number"),
            registration_number=item.get("registration_number"),
            status=item["status"],
            progress_data=item["progress_data"],
            registration_data=item.get("registration_data", {}),
            jplatpat_url=item.get("jplatpat_url"),
            last_synced_at=datetime.now(UTC),
            notes="[DEMO] 架空のデモ出願",
            created_by=user.id,
            updated_by=user.id,
        )
        session.add(asset)
        ip_assets.append(asset)
        existing_apps.add(item["application_number"])
    await session.flush()
    counts["ip_assets"] = len(ip_assets)

    ip_docs = 0
    if ip_assets:
        target = ip_assets[1] if len(ip_assets) > 1 else ip_assets[0]
        existing_docs = (
            await session.execute(
                select(IpDocument.id).where(IpDocument.ip_asset_id == target.id)
            )
        ).scalars().all()
        if not existing_docs:
            session.add(
                IpDocument(
                    ip_asset_id=target.id,
                    doc_type="refusal_reason",
                    doc_name="拒絶理由通知書（デモ）",
                    fetched_at=datetime.now(UTC),
                    content_text=(
                        "拒絶理由通知書（デモ）\n【通知日】2026年9月1日\n"
                        "【出願番号】2026000002\n"
                        "特許法第29条第1項第3号（新規性）の拒絶理由が通知された。\n"
                        "【指定期間】この通知の発送の日から3月以内に意見書又は補正書を提出すること。"
                    ),
                    ai_summary="拒絶理由通知書の要点を抽出しました。 期限: 2026-12-01。",
                    ai_findings={
                        "issues": [
                            {
                                "severity": "high",
                                "title": "拒絶理由への対応が必要です",
                                "description": "意見書または補正書の提出を検討してください。",
                                "law": "特許法第29条",
                            }
                        ],
                        "suggested_actions": ["担当弁理士と対応方針を協議する", "期限をカレンダーに登録する"],
                        "deadline": "2026-12-01",
                        "disclaimer": "本 AI 解析結果は参考情報であり、最終判断は法務担当者および顧問弁護士が行ってください。",
                    },
                    ai_model="demo-local",
                    analyzed_at=datetime.now(UTC),
                )
            )
            ip_docs += 1
    counts["ip_documents"] = ip_docs

    existing_targets = set(
        (await session.execute(select(IpWatchTarget.name))).scalars()
    )
    ip_targets: list[IpWatchTarget] = []
    for name, code in [
        ("デモ競合建設工業(株)", "000000009"),
        ("デモ重機メーカー(株)", "000000010"),
    ]:
        if name in existing_targets:
            continue
        target = IpWatchTarget(
            name=name,
            applicant_code=code,
            ip_types=["patent"],
            status="active",
            notes="[DEMO] 架空の競合ウォッチ対象",
            created_by=user.id,
            updated_by=user.id,
        )
        session.add(target)
        ip_targets.append(target)
        existing_targets.add(name)
    await session.flush()
    counts["ip_watch_targets"] = len(ip_targets)

    # =====================================================================
    # Phase 1-2 新機能デモデータ（signing / obligations / negotiation /
    # matters / outside_counsel / labor_wage）— 画面 F1-F7 が空にならないよう投入
    # =====================================================================

    # ---- 電子契約・電子署名（#1-4 / 画面 /signing）----
    existing_envelope_nos = set(
        (await session.execute(select(ESignatureEnvelope.envelope_no))).scalars()
    )
    new_envelopes: list[ESignatureEnvelope] = []
    for idx, (status, counterparty, method) in enumerate(
        [
            ("completed", "みらい建設工業(株)", "electronic"),
            ("sent", "さくら土木(株)", "electronic"),
            ("draft", "あおぞらコンサルタント(株)", "paper"),
        ]
    ):
        no = f"ES-DEMO-2026-{idx + 1:04d}"
        if no in existing_envelope_nos or not demo_contracts:
            continue
        contract = demo_contracts[idx % len(demo_contracts)]
        env_kwargs: dict[str, object] = {
            "contract_id": contract.id,
            "envelope_no": no,
            "status": status,
            "method": method,
            "provider": "demo",
            "counterparty_name": counterparty,
            "note": "[DEMO] 架空の電子署名デモ",
            "created_by": user.id,
        }
        if status in ("sent", "completed"):
            env_kwargs["sent_at"] = datetime.now(UTC) - timedelta(days=6 - idx)
            env_kwargs["signer_name"] = PEOPLE[idx % len(PEOPLE)]
            env_kwargs["signer_email"] = f"demo{idx + 1}@example.com"
        if status == "completed":
            env_kwargs["consent_confirmed_at"] = datetime.now(UTC) - timedelta(days=8 - idx)
            env_kwargs["consentor_name"] = counterparty
            env_kwargs["consentor_email"] = "legal@example.com"
            env_kwargs["consent_note"] = "[DEMO] 電磁的方法による交付の承諾（建設業法19条）"
            env_kwargs["viewed_at"] = datetime.now(UTC) - timedelta(days=5 - idx)
            env_kwargs["signed_at"] = datetime.now(UTC) - timedelta(days=4 - idx)
            env_kwargs["completed_at"] = datetime.now(UTC) - timedelta(days=3 - idx)
        envelope = ESignatureEnvelope(**env_kwargs)  # type: ignore[arg-type]
        session.add(envelope)
        new_envelopes.append(envelope)
        existing_envelope_nos.add(no)
    await session.flush()
    # 証跡イベント（追記専用・INSERT のみ・status に応じた現実的な遷移）
    signing_event_count = 0
    _event_sets = {
        "draft": ["created"],
        "sent": ["created", "sent"],
        "completed": [
            "created",
            "sent",
            "consent_received",
            "viewed",
            "signed",
            "completed",
        ],
    }
    for envelope in new_envelopes:
        existing_ev = (
            await session.execute(
                select(ESignatureEvent.id).where(ESignatureEvent.envelope_id == envelope.id)
            )
        ).scalars().first()
        if existing_ev is not None:
            continue
        for event_type in _event_sets.get(envelope.status or "draft", ["created"]):
            session.add(
                ESignatureEvent(
                    envelope_id=envelope.id,
                    event_type=event_type,
                    actor_id=user.id,
                    payload={"demo": True, "event_type": event_type},
                )
            )
            signing_event_count += 1
    counts["signing_envelopes"] = len(new_envelopes)
    counts["signing_events"] = signing_event_count

    # ---- 契約義務（#9-13 / 画面 /obligations）----
    # 期限バケット（overdue / within_30 / within_60 / future）が実行日基準で
    # 正しく見えるよう、実行日の相対日付で投入する（タイトルで冪等化）。
    existing_obligations = set(
        (await session.execute(select(ContractObligation.title))).scalars()
    )
    obligations: list[ContractObligation] = []
    demo_obligations = [
        ("notice", "工事着手届の提出（デモ）", datetime.now(UTC).date() - timedelta(days=3), "open"),
        ("report", "月次工程報告書の提出（デモ）", datetime.now(UTC).date() + timedelta(days=12), "open"),
        ("insurance", "保険証券の写し提出（デモ）", datetime.now(UTC).date() + timedelta(days=45), "in_progress"),
        ("submit", "設計図書の提出（デモ）", datetime.now(UTC).date() + timedelta(days=90), "open"),
        ("renewal", "自動更新の確認（デモ）", datetime.now(UTC).date() + timedelta(days=200), "open"),
        ("closing", "完了検査・引渡し（デモ）", datetime.now(UTC).date() + timedelta(days=300), "open"),
    ]
    for idx, (otype, title, due, status) in enumerate(demo_obligations):
        if title in existing_obligations or not demo_contracts:
            continue
        contract = demo_contracts[idx % len(demo_contracts)]
        obligation = ContractObligation(
            contract_id=contract.id,
            obligation_type=otype,
            title=title,
            description="[DEMO] 架空の契約義務（画面確認用）",
            due_date=due,
            status=status,
            assignee_id=user.id,
            created_by=user.id,
        )
        session.add(obligation)
        obligations.append(obligation)
        existing_obligations.add(title)
    counts["obligations"] = len(obligations)

    # ---- 条項交渉・Redline（#5-8 / 画面 /negotiations・既存条項に付与）----
    demo_clauses = (
        await session.execute(
            select(Clause)
            .where(Clause.contract_id.in_([c.id for c in demo_contracts[:12]]))
            .order_by(Clause.contract_id, Clause.seq)
        )
    ).scalars().all()
    negotiation_event_count = 0
    for clause in demo_clauses[:3]:
        if clause.negotiation_status is not None:
            continue
        clause.negotiation_status = "negotiating"
        clause.clause_owner = "法務"
        clause.negotiated_text = clause.body.replace("60日以内", "45日以内") if "60日" in clause.body else None
        session.add(
            ClauseNegotiationEvent(
                contract_id=clause.contract_id,
                clause_id=clause.id,
                round_no=1,
                action="redline",
                status_to="negotiating",
                owner_to="法務",
                note="[DEMO] 支払条件の修正提案（架空の交渉）",
                proposed_text=clause.negotiated_text,
                actor_id=user.id,
            )
        )
        negotiation_event_count += 1
    counts["negotiation_events"] = negotiation_event_count

    # ---- Legal Matter（#71-84 / 画面 /matters）----
    existing_matter_nos = set((await session.execute(select(LegalMatter.matter_no))).scalars())
    matters: list[LegalMatter] = []
    _matter_contract_links: list[tuple[int, int]] = []
    for idx, (mtype, status, priority, title) in enumerate(
        [
            ("dispute", "in_progress", "high", "◯◯工事の追加工事費支払請求への対応（デモ）"),
            ("compliance", "open", "medium", "下請法 60 日ルールの社内点検（デモ）"),
            ("labor", "open", "medium", "労務費基準の乖離是正対応（デモ）"),
        ]
    ):
        no = f"MT-DEMO-2026-{idx + 1:03d}"
        if no in existing_matter_nos or not demo_contracts:
            continue
        contract = demo_contracts[idx % len(demo_contracts)]
        matter = LegalMatter(
            matter_no=no,
            title=title,
            description="[DEMO] 架空の法務案件（画面確認用）",
            matter_type=mtype,
            status=status,
            priority=priority,
            assignee_id=user.id,
            opened_at=datetime.now(UTC) - timedelta(days=10 + idx),
            created_by=user.id,
        )
        session.add(matter)
        matters.append(matter)
        existing_matter_nos.add(no)
        _matter_contract_links.append((matter, contract.id))
    await session.flush()
    # 関係契約リンク（#79）— flush 後に matter.id が確定してから紐付ける
    for matter, contract_id in _matter_contract_links:
        await session.execute(
            matter_contracts_table.insert().values(
                matter_id=matter.id, contract_id=contract_id
            )
        )
    await session.flush()
    matter_event_count = 0
    for matter in matters:
        for event_type, note in [
            ("created", "案件を登録しました"),
            ("status_changed", "対応中に変更しました（デモ）"),
        ]:
            session.add(
                MatterEvent(
                    matter_id=matter.id,
                    event_type=event_type,
                    note=note,
                    actor_id=user.id,
                    payload={"demo": True},
                )
            )
            matter_event_count += 1
    counts["matters"] = len(matters)
    counts["matter_events"] = matter_event_count

    # ---- 顧問弁護士・外部法律事務所（#85-96 / 画面 /outside-counsel）----
    existing_firms = set((await session.execute(select(LawFirm.firm_name))).scalars())
    firms: list[LawFirm] = []
    lawyers: list[CounselLawyer] = []
    engagements: list[LegalEngagement] = []
    firm = None
    if "デモみらい法律事務所" not in existing_firms:
        firm = LawFirm(
            firm_name="デモみらい法律事務所",
            contact_email="demo@example.com",
            phone="03-0000-0000",
            address="東京都千代田区（架空）",
            notes="[DEMO] 架空の法律事務所",
            created_by=user.id,
        )
        session.add(firm)
        firms.append(firm)
        existing_firms.add(firm.firm_name)
    await session.flush()
    if firm is not None:
        existing_lawyer_names = set(
            (await session.execute(select(CounselLawyer.lawyer_name))).scalars()
        )
        for lname, spec in [
            ("デモ 法務太郎", "建設紛争・契約"),
            ("デモ 契約花子", "労働・下請法"),
        ]:
            if lname in existing_lawyer_names:
                continue
            lawyer = CounselLawyer(
                firm_id=firm.id,
                lawyer_name=lname,
                email="demo.lawyer@example.com",
                bar_number="000000",
                specialties=spec,
                created_by=user.id,
            )
            session.add(lawyer)
            lawyers.append(lawyer)
            existing_lawyer_names.add(lname)
        await session.flush()
        existing_eng_no = set(
            (await session.execute(select(LegalEngagement.engagement_no))).scalars()
        )
        for idx, (status, title, question) in enumerate(
            [
                ("confirmed", "追加工事費の請求可否について（デモ）", "◯◯工事の追加工事について、発注者への請求可否と法的論点をご教示ください。（架空）"),
                ("answered", "労働者派遣と下請負の区分について（デモ）", "本件作業が労働者派遣に該当するか、下請負かについてご教示ください。（架空）"),
                ("open", "一括下請負の該当性について（デモ）", "契約構成が一括下請負に該当しないか確認したい。（架空）"),
            ]
        ):
            no = f"LEG-DEMO-2026-{idx + 1:03d}"
            if no in existing_eng_no:
                continue
            engagement = LegalEngagement(
                engagement_no=no,
                firm_id=firm.id,
                lawyer_id=lawyers[idx % len(lawyers)].id if lawyers else None,
                matter_id=matters[idx % len(matters)].id if matters else None,
                title=title,
                question=question,
                notes="[DEMO] 架空の弁護士依頼",
                status=status,
                due_date=BASE_DATE + timedelta(days=14 + idx * 7),
                conflict_of_interest=False,
                confidential=idx == 0,
                fee_estimate_jpy=100_000 + idx * 50_000,
                created_by=user.id,
            )
            if status in ("answered", "confirmed"):
                engagement.answer = (
                    "ご質問の件につき、法令に基づき以下のとおり回答します（デモ回答）。"
                    "本回答は一般論であり、最終判断は社内でご確認ください。（架空）"
                )
                engagement.answered_at = datetime.now(UTC) - timedelta(days=2 - idx)
                engagement.answered_by = user.id
            session.add(engagement)
            engagements.append(engagement)
            existing_eng_no.add(no)
        await session.flush()
    counts["law_firms"] = len(firms)
    counts["counsel_lawyers"] = len(lawyers)
    counts["engagements"] = len(engagements)

    # ---- 労務費基準マスタ（#16-20 / 画面 /labor-wage・source_ref で冪等化）----
    # デモ正本は全 8 件（既存 5 件 + 追加 3 件）。delete → seed で必ず全件復元される。
    existing_wage = set(
        (
            await session.execute(
                select(LaborWageStandard.work_type, LaborWageStandard.prefecture)
            )
        ).all()
    )
    wage_count = 0
    for wtype, pref, amount in [
        ("土木", "東京都", 20400),
        ("土木", "大阪府", 19800),
        ("とび・土工", None, 21800),
        ("舗装", None, 19300),
        ("解体", None, 20100),
        ("鉄筋", "東京都", 20500),
        ("コンクリート", "大阪府", 19900),
        ("とび・土工", "愛知県", 21600),
    ]:
        key = (wtype, pref)
        if key in existing_wage:
            continue
        session.add(
            LaborWageStandard(
                work_type=wtype,
                prefecture=pref,
                amount_jpy=amount,
                effective_from=date(2026, 1, 1),
                amount_unit="日",
                source_ref="demo-2026-01",
                created_by=user.id,
            )
        )
        existing_wage.add(key)
        wage_count += 1
    counts["labor_wage_standards"] = wage_count

    # ---- 標準工期マスタ（#22 短工期判定 / 画面 /labor-wage）----
    # 工種 × 請負金額帯 × 標準工期。source_ref=demo-2026-01 で冪等化・削除対象に含める。
    existing_durations = set(
        (
            await session.execute(
                select(
                    StandardWorkDuration.work_type,
                    StandardWorkDuration.prefecture,
                    StandardWorkDuration.amount_min_jpy,
                    StandardWorkDuration.amount_max_jpy,
                )
            )
        ).all()
    )
    duration_count = 0
    for wtype, pref, amin, amax, days in [
        ("土木", None, 0, 50_000_000, 120),
        ("土木", None, 50_000_000, None, 240),
        ("とび・土工", None, 0, 20_000_000, 60),
        ("とび・土工", None, 20_000_000, None, 150),
        ("舗装", None, 0, 30_000_000, 45),
        ("解体", None, 0, 30_000_000, 30),
        ("鉄筋", None, 0, None, 90),
        ("コンクリート", None, 0, None, 90),
    ]:
        key = (wtype, pref, amin, amax)
        if key in existing_durations:
            continue
        session.add(
            StandardWorkDuration(
                work_type=wtype,
                prefecture=pref,
                amount_min_jpy=amin,
                amount_max_jpy=amax,
                standard_days=days,
                effective_from=date(2026, 1, 1),
                source_ref="demo-2026-01",
                created_by=user.id,
            )
        )
        existing_durations.add(key)
        duration_count += 1
    counts["standard_durations"] = duration_count

    # ---- 労務費価格協議（#24 / ダンピング警告 #21 / 見積変更監視 #23）----
    # サービス層の乖離スナップショット付きで投入する（log_no は自動採番）。
    # 冪等化: summary（協議内容）の重複を確認してスキップする。
    existing_consultation_summaries = set(
        (await session.execute(select(PriceConsultationLog.summary))).scalars()
    )
    consultation_count = 0
    created_consultations: list[PriceConsultationLog] = []
    demo_consultations = [
        {
            "direction": "from_subcontractor",
            "work_type": "土木",
            "prefecture": "東京都",
            "quote_day_jpy": 17_500,
            "summary": "労務費上昇に伴う単価引上げ協議（デモ）",
            "request_detail": "2026年基準改定に伴う労務単価の上昇を踏まえた引上げの申出（架空）。",
            "requested_at": date.today() - timedelta(days=6),
        },
        {
            "direction": "from_subcontractor",
            "work_type": "解体",
            "quote_day_jpy": 14_000,
            "summary": "解体工事の単価見直し協議（デモ）",
            "request_detail": "現場条件の変化に伴う単価見直しの申出（架空）。基準を大きく下回る要確認例。",
            "requested_at": date.today() - timedelta(days=3),
        },
        {
            "direction": "to_subcontractor",
            "work_type": "鉄筋",
            "prefecture": "東京都",
            "quote_day_jpy": 21_000,
            "summary": "見積単価の確認依頼（デモ）",
            "request_detail": "下請から提出された見積の妥当性確認（架空）。",
            "requested_at": date.today() - timedelta(days=1),
        },
    ]
    for item in demo_consultations:
        if item["summary"] in existing_consultation_summaries:
            continue
        try:
            row = await price_consultation_service.create_log(
                session,
                actor_id=user.id,
                direction=item["direction"],
                work_type=item["work_type"],
                prefecture=item.get("prefecture"),
                quote_day_jpy=item.get("quote_day_jpy"),
                summary=item["summary"],
                request_detail=item.get("request_detail"),
                requested_at=item.get("requested_at"),
            )
        except Exception:  # 基準未登録等で失敗してもデモ全体を止めない
            continue
        consultation_count += 1
        created_consultations.append(row)
        existing_consultation_summaries.add(item["summary"])
    counts["price_consultations"] = consultation_count

    # ---- 公共工事（#41-#43・#54-#57 / 画面 /public-works）----
    # 発注機関マスタ 3 件・通知 3 件・協議 3 件（冪等: コード/タイトルで判別）。
    existing_agencies = set((await session.execute(select(ContractingAgency.code))).scalars())
    created_agencies: list[ContractingAgency] = []
    demo_agencies = [
        ("AG-DEMO-0001", "デモ国交省出張所", "national", None, 50, 0.4),
        ("AG-DEMO-0002", "デモ県土木事務所", "prefectural", "東京都", 50, 0.3),
        ("AG-DEMO-0003", "デモ市役所建設課", "municipal", "東京都", 60, 0.0),
    ]
    for code, name, atype, pref, pay_days, adv in demo_agencies:
        if code in existing_agencies:
            continue
        agency = await public_works_service.create_agency(
            session,
            actor_id=user.id,
            code=code,
            name=name,
            agency_type=atype,
            prefecture=pref,
            payment_deadline_days=pay_days,
            advance_payment_ratio=adv,
            requires_slide_clause=atype in ("national", "prefectural"),
            notes="[DEMO] 架空の発注機関",
        )
        created_agencies.append(agency)
        existing_agencies.add(code)
    counts["contracting_agencies"] = len(created_agencies)
    await session.flush()

    existing_notif_titles = set(
        (await session.execute(select(OwnerNotification.title))).scalars()
    )
    created_notifications: list[OwnerNotification] = []
    demo_notifications = [
        ("delay", "工期遅延に伴う通知（デモ）", date.today() - timedelta(days=2)),
        ("design_change", "設計変更の通知（デモ）", date.today() + timedelta(days=14)),
        ("completion", "部分使用承認申請の通知（デモ）", date.today() + timedelta(days=45)),
    ]
    for ntype, title, due in demo_notifications:
        if title in existing_notif_titles:
            continue
        row = await public_works_service.create_notification(
            session,
            actor_id=user.id,
            notification_type=ntype,
            title=title,
            agency_id=created_agencies[0].id if created_agencies else None,
            detail="[DEMO] 架空の発注者通知",
            due_date=due,
        )
        created_notifications.append(row)
        existing_notif_titles.add(title)
    counts["owner_notifications"] = len(created_notifications)
    await session.flush()

    existing_consult_titles = set(
        (await session.execute(select(PublicWorksConsultation.title))).scalars()
    )
    created_consults: list[PublicWorksConsultation] = []
    demo_consults = [
        ("extension_of_time", "工期延伸協議（デモ）", 30, None),
        ("design_change", "設計変更協議（デモ）", None, 8_000_000),
        ("price_slide", "材料価格スライド請求協議（デモ）", None, 1_200_000),
    ]
    for ctype, title, cdays, camount in demo_consults:
        if title in existing_consult_titles:
            continue
        row = await public_works_service.create_consultation(
            session,
            actor_id=user.id,
            consultation_type=ctype,
            title=title,
            agency_id=created_agencies[1].id if len(created_agencies) > 1 else (created_agencies[0].id if created_agencies else None),
            detail="[DEMO] 架空の発注者との協議",
            claimed_days=cdays,
            claimed_amount_jpy=camount,
            due_date=date.today() + timedelta(days=20),
        )
        created_consults.append(row)
        existing_consult_titles.add(title)
    counts["public_works_consultations"] = len(created_consults)
    await session.flush()

    # ---- JV（共同企業体）（#61-#65 / #69 / #70 / 画面 /joint-ventures）----
    existing_jv_nos = set((await session.execute(select(JointVenture.jv_no))).scalars())
    created_jvs: list[JointVenture] = []
    for idx, (name, rep, status) in enumerate(
        [
            ("デモ◯◯工事共同企業体", "みらい建設工業(株)", "active"),
            ("デモ駅前再開発 JV", "さくら土木(株)", "active"),
        ]
    ):
        no = f"JV-DEMO-2026-{idx + 1:03d}"
        if no in existing_jv_nos:
            continue
        jv = JointVenture(
            jv_no=no,
            name=name,
            status=status,
            representative_name=rep,
            works_title=PROJECTS[idx % len(PROJECTS)],
            start_date=BASE_DATE,
            end_date=BASE_DATE + timedelta(days=365),
            notes="[DEMO] 架空の JV",
            created_by=user.id,
        )
        session.add(jv)
        created_jvs.append(jv)
        existing_jv_nos.add(no)
    await session.flush()
    jv_member_count = 0
    for jv in created_jvs:
        existing_members = set(
            (
                await session.execute(
                    select(JvMember.company_name).where(JvMember.jv_id == jv.id)
                )
            ).scalars()
        )
        for mname, role, equity in [
            (jv.representative_name or "代表（デモ）", "representative", 60.0),
            ("(株)つばさ組", "member", 40.0),
        ]:
            if mname in existing_members:
                continue
            session.add(
                JvMember(
                    jv_id=jv.id,
                    role=role,
                    company_name=mname,
                    equity_ratio=equity,
                    profit_share_ratio=equity,
                    notes="[DEMO] 架空の構成員",
                    created_by=user.id,
                )
            )
            jv_member_count += 1
    counts["joint_ventures"] = len(created_jvs)
    counts["jv_members"] = jv_member_count

    # ---- 協力会社拡張（#146/#150/#151 / 画面 /partner-risk・/partners）----
    # 既存 Partner（partners テーブル）へ保険証券期限・Risk Score を設定し、
    # 定期再審査を起票・完了させる（冪等: review_no は自動採番、タイトルで判別）。
    partners_rows = (
        await session.execute(select(Partner).order_by(Partner.id).limit(3))
    ).scalars().all()
    created_reviews: list[PartnerReview] = []
    for idx, partner_row in enumerate(partners_rows):
        if partner_row.insurance_expiry is None:
            partner_row.insurance_expiry = date.today() + timedelta(days=120 + idx * 30)
        if idx == 0:
            # 期限切れ例（アラート表示用）
            partner_row.permit_expiry = date.today() - timedelta(days=10)
        review = await partner_ext_service.create_review(
            session,
            actor_id=user.id,
            partner_id=partner_row.id,
            review_type="periodic",
            title=f"定期再審査（デモ）— {partner_row.name}",
        )
        await partner_ext_service.complete_review(
            session,
            review_id=review.id,
            actor_id=user.id,
            safety_score=[88, 75, 92][idx % 3],
            findings="[DEMO] 架空の再審査結果",
        )
        created_reviews.append(review)
        await partner_ext_service.refresh_risk_score(session, partner_id=partner_row.id)
    counts["partner_reviews"] = len(created_reviews)

    # --- 監査ログ（デモフラグ付き・append-only）---
    # 新規投入した行についてのみ記録する（冪等性維持）。
    audit_count = 0
    for contract in contracts:
        await _log(
            session,
            user,
            "contract.create",
            "contracts",
            contract.id,
            contract_no=contract.contract_no,
            title=contract.title,
        )
        audit_count += 1
    for review in reviews:
        await _log(session, user, "review.complete", "reviews", review.id, contract_id=review.contract_id)
        audit_count += 1
    for partner in partners:
        await _log(session, user, "partner.create", "partners", partner.id, name=partner.name)
        audit_count += 1
    for dispute in disputes:
        await _log(session, user, "dispute.create", "disputes", dispute.id, dispute_no=dispute.dispute_no)
        audit_count += 1
    for change_order in change_orders:
        await _log(session, user, "change_order.create", "change_orders", change_order.id, change_no=change_order.change_no)
        audit_count += 1
    for asset in ip_assets:
        await _log(session, user, "ip_asset.create", "ip_assets", asset.id, application_number=asset.application_number)
        audit_count += 1
    for target in ip_targets:
        await _log(session, user, "ip_watch_target.create", "ip_watch_targets", target.id, name=target.name)
        audit_count += 1
    for idx, contract in enumerate(wf_contracts[:7]):
        if contract.id not in existing_steps:
            await _log(
                session,
                user,
                "workflow_step.approve",
                "workflow_definitions",
                workflow.id,
                contract_no=contract.contract_no,
                step=idx + 1,
            )
            audit_count += 1
    for envelope in new_envelopes:
        await _log(
            session,
            user,
            "esignature.create",
            "esignature_envelopes",
            envelope.id,
            envelope_no=envelope.envelope_no,
        )
        audit_count += 1
    for obligation in obligations:
        await _log(
            session,
            user,
            "obligation.create",
            "contract_obligations",
            obligation.id,
            title=obligation.title,
        )
        audit_count += 1
    for matter in matters:
        await _log(session, user, "matter.create", "legal_matters", matter.id, matter_no=matter.matter_no)
        audit_count += 1
    for firm_obj in firms:
        await _log(session, user, "law_firm.create", "law_firms", firm_obj.id, firm_name=firm_obj.firm_name)
        audit_count += 1
    for lawyer in lawyers:
        await _log(session, user, "counsel_lawyer.create", "counsel_lawyers", lawyer.id, lawyer_name=lawyer.lawyer_name)
        audit_count += 1
    for engagement in engagements:
        await _log(
            session,
            user,
            "engagement.create",
            "legal_engagements",
            engagement.id,
            engagement_no=engagement.engagement_no,
        )
        audit_count += 1
    for consultation in created_consultations:
        await _log(
            session,
            user,
            "price_consultation.create",
            "price_consultation_logs",
            consultation.id,
            log_no=consultation.log_no,
            severity=consultation.severity,
        )
        audit_count += 1
    for agency in created_agencies:
        await _log(
            session,
            user,
            "contracting_agency.create",
            "contracting_agencies",
            agency.id,
            code=agency.code,
        )
        audit_count += 1
    for notification in created_notifications:
        await _log(
            session,
            user,
            "owner_notification.create",
            "owner_notifications",
            notification.id,
            notification_no=notification.notification_no,
        )
        audit_count += 1
    for consult in created_consults:
        await _log(
            session,
            user,
            "public_works_consultation.create",
            "public_works_consultations",
            consult.id,
            consultation_no=consult.consultation_no,
        )
        audit_count += 1
    for jv in created_jvs:
        await _log(session, user, "jv.create", "joint_ventures", jv.id, jv_no=jv.jv_no)
        audit_count += 1
    for review in created_reviews:
        await _log(
            session,
            user,
            "partner_review.create",
            "partner_reviews",
            review.id,
            review_no=review.review_no,
        )
        audit_count += 1
    counts["audit_logs"] = audit_count

    return counts


async def delete_demo(session) -> dict[str, int]:
    counts: dict[str, int] = {}
    demo_contract_ids = list(
        (await session.execute(select(Contract.id).where(Contract.contract_no.like("CTR-2026-%")))).scalars()
    )
    for table, where in [
        (PaymentRecord, PaymentRecord.contract_id.in_(demo_contract_ids)) if demo_contract_ids else None,
        (ChangeOrder, ChangeOrder.contract_id.in_(demo_contract_ids)) if demo_contract_ids else None,
    ]:
        if table is not None:
            counts[table.__tablename__] = (await session.execute(delete(table).where(where))).rowcount
    counts["disputes"] = (
        await session.execute(delete(Dispute).where(Dispute.dispute_no.like("DSP-2026-%")))
    ).rowcount
    counts["partners"] = (
        await session.execute(delete(Partner).where(Partner.permit_number.like("デモ大臣許可%") | Partner.permit_number.like("デモ都知事許可%") | Partner.permit_number.like("デモ県知事許可%")))
    ).rowcount
    counts["contract_templates"] = (
        await session.execute(delete(ContractTemplate).where(ContractTemplate.code.like("DEMO-%")))
    ).rowcount
    counts["notifications"] = (
        await session.execute(delete(Notification).where(Notification.payload["demo"].as_string() == "true"))
    ).rowcount
    demo_knowledge_ids = [
        row.id
        for row in (await session.execute(select(KnowledgeArticle.id, KnowledgeArticle.tags))).all()
        if "デモ" in (row.tags or [])
    ]
    counts["knowledge_articles"] = (
        await session.execute(delete(KnowledgeArticle).where(KnowledgeArticle.id.in_(demo_knowledge_ids)))
    ).rowcount if demo_knowledge_ids else 0
    if demo_contract_ids:
        counts["clauses"] = (
            await session.execute(delete(Clause).where(Clause.contract_id.in_(demo_contract_ids)))
        ).rowcount
        counts["contract_documents"] = (
            await session.execute(delete(ContractDocument).where(ContractDocument.contract_id.in_(demo_contract_ids)))
        ).rowcount
        counts["workflow_steps"] = (
            await session.execute(delete(WorkflowStep).where(WorkflowStep.contract_id.in_(demo_contract_ids)))
        ).rowcount
        counts["risk_items"] = (
            await session.execute(delete(RiskItem).where(RiskItem.contract_id.in_(demo_contract_ids)))
        ).rowcount
        counts["legal_reviews"] = (
            await session.execute(delete(LegalReview).where(LegalReview.contract_id.in_(demo_contract_ids)))
        ).rowcount
        # Phase 1-2: 契約に FK で紐づく新機能テーブルは契約削除より先に消す
        # （esignature_envelopes / clause_negotiation_events は ondelete=RESTRICT）
        counts["contract_obligations"] = (
            await session.execute(
                delete(ContractObligation).where(ContractObligation.contract_id.in_(demo_contract_ids))
            )
        ).rowcount
        counts["negotiation_events"] = (
            await session.execute(
                delete(ClauseNegotiationEvent).where(ClauseNegotiationEvent.contract_id.in_(demo_contract_ids))
            )
        ).rowcount
        demo_envelope_ids = list(
            (
                await session.execute(
                    select(ESignatureEnvelope.id).where(
                        ESignatureEnvelope.contract_id.in_(demo_contract_ids)
                    )
                )
            ).scalars()
        )
        if demo_envelope_ids:
            counts["signing_events"] = (
                await session.execute(
                    delete(ESignatureEvent).where(ESignatureEvent.envelope_id.in_(demo_envelope_ids))
                )
            ).rowcount
            counts["signing_envelopes"] = (
                await session.execute(
                    delete(ESignatureEnvelope).where(ESignatureEnvelope.id.in_(demo_envelope_ids))
                )
            ).rowcount
        else:
            counts["signing_events"] = 0
            counts["signing_envelopes"] = 0
        counts["contracts"] = (
            await session.execute(delete(Contract).where(Contract.contract_no.like("CTR-2026-%")))
        ).rowcount
    else:
        counts["contract_obligations"] = 0
        counts["negotiation_events"] = 0
        counts["signing_events"] = 0
        counts["signing_envelopes"] = 0
    counts["workflow_definitions"] = (
        await session.execute(delete(Workflow).where(Workflow.code == "DEMO-LEGAL-001"))
    ).rowcount
    demo_asset_ids = [
        row.id
        for row in (await session.execute(select(IpAsset.id, IpAsset.notes))).all()
        if row.notes and "[DEMO]" in row.notes
    ]
    if demo_asset_ids:
        counts["ip_documents"] = (
            await session.execute(delete(IpDocument).where(IpDocument.ip_asset_id.in_(demo_asset_ids)))
        ).rowcount
        counts["ip_watch_events"] = (
            await session.execute(delete(IpWatchEvent).where(IpWatchEvent.ip_asset_id.in_(demo_asset_ids)))
        ).rowcount
        counts["ip_assets"] = (
            await session.execute(delete(IpAsset).where(IpAsset.id.in_(demo_asset_ids)))
        ).rowcount
    else:
        counts["ip_documents"] = 0
        counts["ip_watch_events"] = 0
        counts["ip_assets"] = 0
    counts["ip_watch_targets"] = (
        await session.execute(
            delete(IpWatchTarget).where(IpWatchTarget.notes.like("%[DEMO]%"))
        )
    ).rowcount

    # ---- Phase 1-2 新機能デモ（DEMO 識別子・[DEMO] メモで冪等に削除）----
    # 契約配下（obligations / negotiation_events / envelopes）は上記の
    # demo_contract_ids ブロック内（契約削除直前）で削除済み。
    # 独立系: Matter（イベント → リンク → 本体）
    demo_matter_ids = list(
        (
            await session.execute(
                select(LegalMatter.id).where(LegalMatter.matter_no.like("MT-DEMO-%"))
            )
        ).scalars()
    )
    if demo_matter_ids:
        counts["matter_events"] = (
            await session.execute(
                delete(MatterEvent).where(MatterEvent.matter_id.in_(demo_matter_ids))
            )
        ).rowcount
        counts["matter_contracts"] = (
            await session.execute(
                delete(matter_contracts_table).where(
                    matter_contracts_table.c.matter_id.in_(demo_matter_ids)
                )
            )
        ).rowcount
        counts["matters"] = (
            await session.execute(
                delete(LegalMatter).where(LegalMatter.id.in_(demo_matter_ids))
            )
        ).rowcount
    else:
        counts["matter_events"] = 0
        counts["matter_contracts"] = 0
        counts["matters"] = 0
    # 顧問弁護士（依頼 → 弁護士 → 事務所）
    demo_firm_ids = list(
        (
            await session.execute(
                select(LawFirm.id).where(LawFirm.firm_name == "デモみらい法律事務所")
            )
        ).scalars()
    )
    if demo_firm_ids:
        demo_lawyer_ids = list(
            (
                await session.execute(
                    select(CounselLawyer.id).where(CounselLawyer.firm_id.in_(demo_firm_ids))
                )
            ).scalars()
        )
        counts["engagements"] = (
            await session.execute(
                delete(LegalEngagement).where(LegalEngagement.firm_id.in_(demo_firm_ids))
            )
        ).rowcount
        counts["counsel_lawyers"] = (
            await session.execute(
                delete(CounselLawyer).where(CounselLawyer.firm_id.in_(demo_firm_ids))
            )
        ).rowcount if demo_lawyer_ids else 0
        counts["law_firms"] = (
            await session.execute(delete(LawFirm).where(LawFirm.id.in_(demo_firm_ids)))
        ).rowcount
    else:
        counts["engagements"] = 0
        counts["counsel_lawyers"] = 0
        counts["law_firms"] = 0
    # 労務費基準（source_ref=demo-2026-01 のデモ行のみ・既存実データは残す）
    counts["labor_wage_demo"] = (
        await session.execute(
            delete(LaborWageStandard).where(LaborWageStandard.source_ref == "demo-2026-01")
        )
    ).rowcount
    # 標準工期マスタ（同様に source_ref=demo-2026-01 のデモ行のみ）
    counts["standard_durations"] = (
        await session.execute(
            delete(StandardWorkDuration).where(StandardWorkDuration.source_ref == "demo-2026-01")
        )
    ).rowcount
    # 労務費価格協議（デモ summary で判別）
    counts["price_consultations"] = (
        await session.execute(
            delete(PriceConsultationLog).where(
                PriceConsultationLog.summary.like("%（デモ）%")
            )
        )
    ).rowcount
    # 公共工事（デモ識別子 AG-DEMO-%・タイトル（デモ）で判別）
    demo_agency_ids = list(
        (
            await session.execute(
                select(ContractingAgency.id).where(
                    ContractingAgency.code.like("AG-DEMO-%")
                )
            )
        ).scalars()
    )
    if demo_agency_ids:
        counts["public_works_consultations"] = (
            await session.execute(
                delete(PublicWorksConsultation).where(
                    PublicWorksConsultation.agency_id.in_(demo_agency_ids)
                )
            )
        ).rowcount
        counts["owner_notifications"] = (
            await session.execute(
                delete(OwnerNotification).where(
                    OwnerNotification.agency_id.in_(demo_agency_ids)
                )
            )
        ).rowcount
        counts["contracting_agencies"] = (
            await session.execute(
                delete(ContractingAgency).where(ContractingAgency.id.in_(demo_agency_ids))
            )
        ).rowcount
    else:
        counts["public_works_consultations"] = (
            await session.execute(
                delete(PublicWorksConsultation).where(
                    PublicWorksConsultation.title.like("%（デモ）%")
                )
            )
        ).rowcount
        counts["owner_notifications"] = (
            await session.execute(
                delete(OwnerNotification).where(OwnerNotification.title.like("%（デモ）%"))
            )
        ).rowcount
        counts["contracting_agencies"] = 0
    # JV（デモ識別子 JV-DEMO-% で判別）
    demo_jv_ids = list(
        (
            await session.execute(
                select(JointVenture.id).where(JointVenture.jv_no.like("JV-DEMO-%"))
            )
        ).scalars()
    )
    if demo_jv_ids:
        counts["jv_members"] = (
            await session.execute(
                delete(JvMember).where(JvMember.jv_id.in_(demo_jv_ids))
            )
        ).rowcount
        counts["jv_settlements"] = (
            await session.execute(
                delete(JvSettlement).where(JvSettlement.jv_id.in_(demo_jv_ids))
            )
        ).rowcount
        counts["jv_disputes"] = (
            await session.execute(
                delete(JvDispute).where(JvDispute.jv_id.in_(demo_jv_ids))
            )
        ).rowcount
        counts["jv_agreements"] = (
            await session.execute(
                delete(JvAgreement).where(JvAgreement.jv_id.in_(demo_jv_ids))
            )
        ).rowcount
        counts["joint_ventures"] = (
            await session.execute(
                delete(JointVenture).where(JointVenture.id.in_(demo_jv_ids))
            )
        ).rowcount
    else:
        counts["jv_members"] = 0
        counts["jv_settlements"] = 0
        counts["jv_disputes"] = 0
        counts["jv_agreements"] = 0
        counts["joint_ventures"] = 0
    # 協力会社再審査（デモタイトルで判別）
    counts["partner_reviews"] = (
        await session.execute(
            delete(PartnerReview).where(PartnerReview.title.like("%（デモ）%"))
        )
    ).rowcount
    return counts


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="トランザクションをロールバックして確認のみ")
    parser.add_argument("--delete", action="store_true", help="デモデータを削除")
    args = parser.parse_args()

    async with AsyncSessionLocal() as session, session.begin():
        if args.delete:
            counts = await delete_demo(session)
        else:
            counts = await seed(session, dry_run=args.dry_run)
        if args.dry_run:
            await session.rollback()
            print("[dry-run] 投入予定:", counts)
        else:
            print(("削除" if args.delete else "投入") + "完了:", counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
