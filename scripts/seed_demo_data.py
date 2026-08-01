#!/usr/bin/env python3
"""Standalone WebUI 相当のデモデータを backend DB へ投入するスクリプト。

使い方（backend コンテナ内で実行する前提）:
    docker cp scripts/seed_demo_data.py <backend-container>:/tmp/seed_demo_data.py
    docker exec -w /app <backend-container> python /tmp/seed_demo_data.py            # 投入
    docker exec -w /app <backend-container> python /tmp/seed_demo_data.py --dry-run  # 確認のみ
    docker exec -w /app <backend-container> python /tmp/seed_demo_data.py --delete   # デモデータ削除

デモ行は識別子プレフィックス（CTR-2026- / DEMO- 等）で判別でき、冪等です。
監査ログ（append-only・削除不可）には投入しません。
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from app.db.session import AsyncSessionLocal
from app.models.contract import Contract
from app.models.department import Department
from app.models.knowledge_article import KnowledgeArticle
from app.models.legal_review import LegalReview
from app.models.notification import Notification
from app.models.risk_item import RiskItem
from app.models.user import User
from app.models.workflow import Workflow, WorkflowStep
from sqlalchemy import delete, select

BASE_DATE = date(2026, 5, 16)

CONTRACT_TYPES = [
    "工事請負契約",
    "業務委託契約",
    "資材購入契約",
    "下請契約",
    "設計監理契約",
    "賃貸借契約",
    "秘密保持契約",
]
COMPANIES = [
    "大成建設工業(株)",
    "鈴木土木(株)",
    "(株)山田設計事務所",
    "東日本資材(株)",
    "(株)佐藤組",
    "中央コンサルタント(株)",
    "北関東電設(株)",
    "(株)高橋建材",
    "西部工業(株)",
    "(株)渡辺設備",
    "太平洋セメント(株)",
    "(株)田中工務店",
    "関東リース(株)",
    "(株)伊藤測量",
    "(株)小林重機",
    "東京法律事務所",
    "横浜建設(株)",
    "(株)中村組",
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
        "target": "第3条 契約金額",
        "summary": "契約金額の支払条件が下請法に抵触する可能性",
        "severity": "high",
        "detail": "支払期日が納品後60日を超えており、下請法第2条の4に違反する可能性があります。",
    },
    {
        "target": "第7条 解除条項",
        "summary": "一方的解除条項に建設業法上のリスク",
        "severity": "critical",
        "detail": "発注者側からの一方的解除が不当に広く認められており、建設業法第19条の3に抵触する恐れがあります。",
    },
    {
        "target": "第12条 損害賠償",
        "summary": "賠償上限が設定されていない",
        "severity": "medium",
        "detail": "損害賠償の上限条項がなく、過大なリスク負担となる可能性があります。",
    },
    {
        "target": "第5条 工期",
        "summary": "工期延長条件が不明確",
        "severity": "medium",
        "detail": "天候不順や不可抗力による工期延長の条件が具体的に定められていません。",
    },
    {
        "target": "第15条 秘密保持",
        "summary": "秘密情報の定義が広すぎる",
        "severity": "low",
        "detail": "秘密情報の範囲が「一切の情報」と定義されており、実務上の運用が困難です。",
    },
    {
        "target": "第9条 検査・引渡し",
        "summary": "検査期間が短すぎる可能性",
        "severity": "medium",
        "detail": "検査期間が7日と設定されていますが、工事の規模に対して不十分な可能性があります。",
    },
]

REVIEW_SUGGESTIONS = [
    {
        "target": "第3条 契約金額",
        "summary": "支払期日を60日以内に短縮",
        "original": "支払いは、納品確認後90日以内に行うものとする。",
        "proposed": "支払いは、納品確認後60日以内に行うものとする。なお、下請法の適用がある場合は同法の定めに従う。",
        "rationale": "下請法第2条の4により、下請代金の支払期日は物品等の受領日から60日以内と定められています。",
        "confidence": 92,
    },
    {
        "target": "第7条 解除条項",
        "summary": "解除事由の限定と催告手続の追加",
        "original": "甲は、いつでも本契約を解除することができる。",
        "proposed": "甲は、乙が本契約に重大な違反をし、書面による催告後30日以内に是正されない場合に限り、本契約を解除することができる。",
        "rationale": "建設業法第19条の3の趣旨に照らし、一方的な解除権は制限すべきです。",
        "confidence": 88,
    },
    {
        "target": "第12条 損害賠償",
        "summary": "賠償上限条項の追加",
        "original": "（上限条項なし）",
        "proposed": "本契約に基づく損害賠償の総額は、契約金額を上限とする。ただし、故意または重過失による場合はこの限りでない。",
        "rationale": "無制限の賠償責任は過大なリスクとなるため、契約金額を上限とする条項の追加を推奨します。",
        "confidence": 85,
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


def contract_title(i: int) -> str:
    return f"{CONTRACT_TYPES[i % len(CONTRACT_TYPES)]}（{COMPANIES[i % len(COMPANIES)]}）"


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


async def seed(session, *, dry_run: bool) -> dict[str, int]:
    counts: dict[str, int] = {}
    user = (await session.execute(select(User).order_by(User.id).limit(1))).scalar_one_or_none()
    if user is None:
        raise RuntimeError("users テーブルにユーザーがいません（先に JIT ログインが必要）")

    departments = await ensure_departments(session)
    legal_dept = departments["法務部"]

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
        suggestions = REVIEW_SUGGESTIONS[: (idx % 2) + 1]
        review = LegalReview(
            contract_id=contract.id,
            review_type="hybrid",
            status=REVIEW_STATUS_MAP[mock_status],
            ai_model="claude-opus-4-7",
            summary="本契約について、下請法・建設業法の観点から指摘事項が検出されました。",
            overall_risk=risk_level,
            risk_score=risk_score,
            result={"issues": issues, "suggestions": suggestions},
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
                    severity=issue["severity"],
                    probability="medium",
                    impact="medium",
                    description=issue["detail"],
                    mitigation="",
                    recommendation=issue["summary"],
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
            description="Standalone デモ相当の承認ワークフロー定義。",
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
    return counts


async def delete_demo(session) -> dict[str, int]:
    counts: dict[str, int] = {}
    demo_contract_ids = list(
        (await session.execute(select(Contract.id).where(Contract.contract_no.like("CTR-2026-%")))).scalars()
    )
    counts["notifications"] = (
        await session.execute(
            delete(Notification).where(Notification.payload["demo"].astext == "true")
        )
    ).rowcount
    counts["knowledge_articles"] = (
        await session.execute(delete(KnowledgeArticle).where(KnowledgeArticle.tags.contains(["デモ"])))
    ).rowcount
    if demo_contract_ids:
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
