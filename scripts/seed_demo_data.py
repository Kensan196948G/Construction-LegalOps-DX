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

from sqlalchemy import delete, select

from app.db.session import AsyncSessionLocal
from app.models.change_order import ChangeOrder
from app.models.clause import Clause
from app.models.contract import Contract
from app.models.contract_document import ContractDocument
from app.models.contract_template import ContractTemplate
from app.models.department import Department
from app.models.dispute import Dispute
from app.models.enums import UserRole
from app.models.knowledge_article import KnowledgeArticle
from app.models.legal_review import LegalReview
from app.models.notification import Notification
from app.models.partner import Partner
from app.models.payment_record import PaymentRecord
from app.models.risk_item import RiskItem
from app.models.user import User
from app.models.workflow import Workflow, WorkflowStep
from app.services import audit_service
from app.services.rls_context import set_rls_context

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
    email = (os.getenv("DEV_USER_EMAIL", "") or "dev-user@example.invalid").strip().lower()
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
            ai_model="demo-ai-model",
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

    await session.flush()

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
        counts["contracts"] = (
            await session.execute(delete(Contract).where(Contract.contract_no.like("CTR-2026-%")))
        ).rowcount
    counts["workflow_definitions"] = (
        await session.execute(delete(Workflow).where(Workflow.code == "DEMO-LEGAL-001"))
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
