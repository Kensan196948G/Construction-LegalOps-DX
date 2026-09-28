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
  - Phase 3（内部通報 /whistleblower・証拠 /evidence・独禁法 /compliance/antitrust・
    紛争高度化 /disputes・条項ライブラリ /templates・IP ウォッチ検知 /ip-watch・
    Legal Hold・JV 詳細）も同様に網羅する。削除の判別は「タイトル等の末尾（デモ）」または
    「DEMO- 等のデモ識別子」で行う。
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.db.session import AsyncSessionLocal
from app.models.access_control import AccessControlEntry, LegalHold
from app.models.antitrust_compliance import (
    AntitrustCheck,
    AntitrustConsultation,
    AntitrustPriorApplication,
    ComplianceTraining,
)
from app.models.app_settings import AiProviderSetting
from app.models.attachment import Attachment
from app.models.change_order import ChangeOrder, ChangeOrderEvidence
from app.models.clause import Clause, ClauseLibrary
from app.models.contract import Contract
from app.models.contract_document import ContractDocument
from app.models.contract_template import ContractTemplate
from app.models.department import Department
from app.models.dispute import Dispute, DisputeEvidence, DisputeTimelineEvent
from app.models.dispute_ext import (
    DisputeArgumentPosition,
    DisputeDelayEvent,
    DisputeProceedingStage,
    DisputeSettlementOption,
)
from app.models.enums import UserRole
from app.models.evidence import Evidence, EvidenceCustodyEvent
from app.models.ip_asset import IpAsset
from app.models.ip_document import IpDocument
from app.models.ip_watch import IpWatchEvent, IpWatchTarget
from app.models.knowledge_article import KnowledgeArticle
from app.models.labor_commitment import LaborCommitment
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
from app.models.whistleblower import (
    WhistleblowerAction,
    WhistleblowerCaseAccess,
    WhistleblowerEvidence,
    WhistleblowerInterview,
    WhistleblowerReport,
    WhistleblowerReporterProfile,
    WhistleblowerTimelineEvent,
)
from app.services import (
    antitrust_service,
    audit_service,
    dispute_ext_service,
    evidence_service,
    jv_service,
    partner_ext_service,
    price_consultation_service,
    public_works_service,
    whistleblower_service,
)
from app.services.rls_context import set_rls_context
from sqlalchemy import bindparam, delete, func, select, text, update

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

# ===========================================================================
# Phase 3 デモデータ定義（whistleblower / evidence / antitrust / dispute 拡張 /
# clause_library / ip_watch_events / legal_hold / JV 詳細）
#
# すべて架空の値。実在企業・実在人物・実在案件・実在の係争は一切使用しない。
# 削除（--delete）は「タイトル等の末尾 DEMO_SUFFIX」または「デモ識別子
# プレフィックス（DEMO- / AG-DEMO- 等）」で判別する。
# ===========================================================================
DEMO_SUFFIX = "（デモ）"


def _demo_sha256(seed: str) -> str:
    """デモ証拠用の決定的な SHA-256（実ファイルのハッシュではない）."""
    return hashlib.sha256(f"legalops-demo-evidence::{seed}".encode()).hexdigest()


# 内部通報（/whistleblower）。report_no はサービス層が WB-YYYY-NNNNNN で採番する。
WB_REPORTS: list[dict[str, Any]] = [
    {
        "category": "harassment",
        "severity": "high",
        "title": f"【デモ】現場監督による継続的なパワーハラスメントの疑い{DEMO_SUFFIX}",
        "description": "架空のデモ通報です。実在の人物・事案とは一切関係ありません。",
        "is_anonymous": False,
        "reporter": {
            "name": "田中 太郎",
            "email": "demo-wb-reporter1@example.invalid",
            "phone": "000-0000-0001",
            "department": "工事部",
            "relationship": "同僚",
            "consent": True,
        },
        "status": "investigating",
        "access": [("investigator", False), ("observer", False)],
        "evidence": [
            ("document", "就業記録の写し（デモ・架空）", True),
            ("testimony", "同僚2名の証言メモ（デモ・架空）", False),
        ],
        "interviews": [
            ("witness", "鈴木 花子", "目撃状況のヒアリング（デモ・架空）。"),
            ("subject", "佐藤 一郎", "事実確認のヒアリング（デモ・架空）。"),
        ],
        "notes": ["初動ヒアリングを実施し、調査計画書を作成した（デモ）。"],
        "actions": [
            ("corrective", f"現場監督の担当業務を一時変更{DEMO_SUFFIX}", "in_progress"),
        ],
    },
    {
        "category": "safety",
        "severity": "critical",
        "title": f"【デモ】法面工事の安全措置不足に関する匿名通報{DEMO_SUFFIX}",
        "description": "架空のデモ通報です。匿名通報のため通報者識別情報は保存しません。",
        "is_anonymous": True,
        "reporter": None,
        "status": "triage",
        "access": [("investigator", False)],
        "evidence": [("photo", "法面の状況写真（デモ・架空）", True)],
        "interviews": [],
        "notes": ["匿名通報のため、通報者識別情報は記録しない（デモ）。"],
        "actions": [
            ("preventive", f"安全パトロールの頻度引上げ{DEMO_SUFFIX}", "open"),
        ],
    },
    {
        "category": "compliance",
        "severity": "medium",
        "title": f"【デモ】資材発注における便宜供与の疑い{DEMO_SUFFIX}",
        "description": "架空のデモ通報です。実在の取引先・担当者とは一切関係ありません。",
        "is_anonymous": False,
        "reporter": {
            "name": "高橋 健二",
            "email": "demo-wb-reporter3@example.invalid",
            "phone": "000-0000-0003",
            "department": "管理部",
            "relationship": "部下",
            "consent": False,
        },
        "status": "corrective_action",
        "access": [("lead_investigator", True), ("investigator", True)],
        "evidence": [("email", "発注経緯のメール写し（デモ・架空）", True)],
        "interviews": [
            ("reporter", "高橋 健二", "通報内容の詳細確認（デモ・架空）。"),
        ],
        "notes": ["調査の結果、手続漏れが認められたため再発防止策を起案した（デモ）。"],
        "actions": [
            ("corrective", f"発注承認フローの見直し{DEMO_SUFFIX}", "completed"),
            ("preventive", f"コンプライアンス研修の追加実施{DEMO_SUFFIX}", "open"),
        ],
    },
]

# 証拠・eDiscovery（/evidence）。title 末尾 DEMO_SUFFIX で判別する。
# (キー, タイトル, 説明, 入手経路, MIME, ファイル名, 重複用シード or None)
EVIDENCES: list[tuple[str, str, str, str, str, str, str | None]] = [
    (
        "evd-01",
        f"【デモ】工事請負契約書 最終版スキャン{DEMO_SUFFIX}",
        "架空の契約書スキャンです。実在の契約ではありません。",
        "scan",
        "application/pdf",
        "demo-contract-scan.pdf",
        None,
    ),
    (
        "evd-02",
        f"【デモ】現場写真（法面崩れ・第3工区）{DEMO_SUFFIX}",
        "架空の現場写真メタデータです。EXIF は保持しません。",
        "photo",
        "image/jpeg",
        "demo-site-photo.jpg",
        None,
    ),
    (
        "evd-03",
        f"【デモ】遅延に関する打合せメール{DEMO_SUFFIX}",
        "架空のメール証拠です。実在の送受信者はいません。",
        "email",
        "message/rfc822",
        "demo-delay-mail.eml",
        None,
    ),
    (
        "evd-04",
        f"【デモ】工事請負契約書 最終版スキャン（重複取込）{DEMO_SUFFIX}",
        "evd-01 と同一ハッシュの重複取込を再現する架空データです。",
        "upload",
        "application/pdf",
        "demo-contract-scan-copy.pdf",
        "evd-01",
    ),
]

# 独禁法チェック（/compliance/antitrust）。subject 末尾 DEMO_SUFFIX で判別する。
ANTITRUST_CHECKS: list[tuple[str, str, dict[str, object]]] = [
    (
        "general",
        f"【デモ】下請契約書の独禁法一般スクリーニング{DEMO_SUFFIX}",
        {"text": "価格を合わせる旨を記載した架空の条項（デモ）"},
    ),
    (
        "bid_rigging",
        f"【デモ】公共工事の入札前情報共有チェック{DEMO_SUFFIX}",
        {
            "pre_bid_price_shared": True,
            "procuring_agency_involvement": True,
            "contacted_competitors": 3,
            "exchanged_topics": ["price", "schedule"],
        },
    ),
    (
        "price_exchange",
        f"【デモ】競合他社との価格情報交換チェック{DEMO_SUFFIX}",
        {
            "with_competitor": True,
            "exchanged_topics": ["price"],
            "scope_covers_pricing": True,
        },
    ),
    (
        "jv_formation",
        f"【デモ】JV 形成時の競争法チェック{DEMO_SUFFIX}",
        {
            "is_competitor_jv": True,
            "combined_market_share_pct": 45,
            "has_legitimate_business_reason": True,
        },
    ),
    (
        "joint_research",
        f"【デモ】競合との共同研究チェック{DEMO_SUFFIX}",
        {
            "with_competitor": True,
            "covers_pricing_or_output": False,
            "covers_customer_allocation": False,
        },
    ),
]

# 事前申請（/compliance/antitrust）。title 末尾 DEMO_SUFFIX で判別する。
ANTITRUST_APPLICATIONS: list[tuple[str, str, str, int | None, str]] = [
    (
        "competitor_contact",
        f"【デモ】競合他社との業界団体接触記録{DEMO_SUFFIX}",
        "ひかり資材(株)",
        None,
        "submitted",
    ),
    (
        "meeting_social",
        f"【デモ】業界懇親会への参加事前申請{DEMO_SUFFIX}",
        "あおぞらコンサルタント(株)",
        None,
        "approved",
    ),
    (
        "entertainment_gift",
        f"【デモ】取引先との会食（接待）事前申請{DEMO_SUFFIX}",
        "北信電設(株)",
        12000,
        "completed",
    ),
    (
        "public_official_contact",
        f"【デモ】発注者担当者との意見交換の事前申請{DEMO_SUFFIX}",
        "架空公共発注者（デモ）",
        None,
        "approved",
    ),
    (
        "donation_sponsorship",
        f"【デモ】業界団体への協賛金審査{DEMO_SUFFIX}",
        "架空業界団体（デモ）",
        50000,
        "rejected",
    ),
]

# 競争法相談（/compliance/antitrust）。query_text 先頭 【デモ】で判別する。
ANTITRUST_CONSULTATIONS: list[tuple[str, str]] = [
    (
        "【デモ】JV 組成時に競合他社と共有してよい情報の範囲を教えてください。",
        (
            "架空のデモ回答です。一次情報の引用は行わず、一般的な整理のみを示します。"
            "市場・顧客・価格に関する情報共有は競争法上のリスクが高いため、"
            "個別案件は法務担当者・顧問弁護士の確認が必要です（デモ）。"
        ),
    ),
    (
        "【デモ】入札前に下請業者へ概算価格を伝える場合の留意点は？",
        (
            "架空のデモ回答です。入札前の価格情報共有は談合リスクを高めます。"
            "必要な範囲に限定し、記録を残す運用としてください（デモ）。"
        ),
    ),
]

# コンプライアンス研修（/compliance/antitrust）。training_title 末尾 DEMO_SUFFIX で判別する。
COMPLIANCE_TRAININGS: list[tuple[str, str, int]] = [
    (f"【デモ】独占禁止法基礎研修（全社員）{DEMO_SUFFIX}", "antitrust", 88),
    (f"【デモ】入札談合防止研修（工事部門）{DEMO_SUFFIX}", "antitrust", 92),
    (f"【デモ】贈収賄・接待管理研修（管理部門）{DEMO_SUFFIX}", "anti_bribery", 79),
    (f"【デモ】下請法遵守研修（購買部門）{DEMO_SUFFIX}", "subcontract", 85),
]

# 遅延事象（/disputes 詳細）。cause_category は DisputeDelayCauseCategory の値。
DISPUTE_DELAY_EVENTS: list[dict[str, Any]] = [
    {
        "cause_category": "design_change",
        "title": f"【デモ】設計変更に伴う追加施工{DEMO_SUFFIX}",
        "description": "架空の遅延事象です。実在の工事・発注者は登場しません。",
        "occurred_from_offset": 10,
        "occurred_to_offset": 25,
        "delay_days": 15,
        "responsible_party": "発注者（デモ）",
        "additional_cost_jpy": 4200000,
        "eot_days_requested": 15,
        "eot_days_granted": 10,
        "eot_status": "partial",
    },
    {
        "cause_category": "weather",
        "title": f"【デモ】長雨による土工事の中止{DEMO_SUFFIX}",
        "description": "架空の気象遅延です（デモ）。",
        "occurred_from_offset": 40,
        "occurred_to_offset": 47,
        "delay_days": 7,
        "responsible_party": "不可抗力（デモ）",
        "additional_cost_jpy": 850000,
        "eot_days_requested": 7,
        "eot_days_granted": None,
        "eot_status": "pending",
    },
    {
        "cause_category": "owner_caused",
        "title": f"【デモ】資材支給の遅延{DEMO_SUFFIX}",
        "description": "架空の支給遅延です（デモ）。",
        "occurred_from_offset": 60,
        "occurred_to_offset": 66,
        "delay_days": 6,
        "responsible_party": "発注者（デモ）",
        "additional_cost_jpy": 1200000,
        "eot_days_requested": 6,
        "eot_days_granted": 6,
        "eot_status": "approved",
    },
]

# 主張・反論マトリクス（/disputes 詳細）
DISPUTE_ARGUMENTS: list[dict[str, Any]] = [
    {
        "issue_no": 1,
        "issue_title": f"【デモ】追加費用の負担範囲{DEMO_SUFFIX}",
        "party": "ours",
        "stance": "claim",
        "content": "設計変更に起因する追加費用は発注者負担と解すべき旨の架空の主張（デモ）。",
    },
    {
        "issue_no": 1,
        "issue_title": f"【デモ】追加費用の負担範囲{DEMO_SUFFIX}",
        "party": "counterparty",
        "stance": "rebuttal",
        "content": "契約単価に含まれる旨の架空の反論（デモ）。",
    },
    {
        "issue_no": 2,
        "issue_title": f"【デモ】工期延長日数{DEMO_SUFFIX}",
        "party": "ours",
        "stance": "claim",
        "content": "15 日の工期延長が必要である旨の架空の主張（デモ）。",
    },
]

# 和解案比較（/disputes 詳細）
DISPUTE_SETTLEMENT_OPTIONS: list[dict[str, Any]] = [
    {
        "option_no": 1,
        "title": f"【デモ】追加費用の半額を和解金として受領{DEMO_SUFFIX}",
        "settlement_amount_jpy": 2100000,
        "payment_terms": "一括・合意後30日以内（デモ）",
        "pros": "早期解決により工事再開が可能（デモ）。",
        "cons": "請求額の半額を放棄することになる（デモ）。",
        "probability_score": 60,
        "status": "proposed",
    },
    {
        "option_no": 2,
        "title": f"【デモ】工期延長のみ合意し費用は別途協議{DEMO_SUFFIX}",
        "settlement_amount_jpy": 0,
        "payment_terms": "別途協議（デモ）",
        "pros": "費用請求権を留保できる（デモ）。",
        "cons": "解決まで長期化する見込み（デモ）。",
        "probability_score": 35,
        "status": "draft",
    },
]

# 訴訟・ADR ステージ（/disputes 詳細）
DISPUTE_STAGES: list[dict[str, Any]] = [
    {
        "stage": "negotiation",
        "started_offset": 5,
        "ended_offset": 45,
        "forum": "当事者間協議（デモ）",
    },
    {
        "stage": "mediation",
        "started_offset": 45,
        "ended_offset": None,
        "forum": "架空建設紛争調停センター（デモ）",
    },
]

# 紛争の証拠・タイムライン（/disputes 詳細）
DISPUTE_EVIDENCE_ITEMS: list[tuple[str, str]] = [
    ("contract", f"【デモ】工事請負契約書（該当条項抜粋）{DEMO_SUFFIX}"),
    ("daily_report", f"【デモ】作業日報（遅延期間）{DEMO_SUFFIX}"),
    ("email", f"【デモ】設計変更指示メール{DEMO_SUFFIX}"),
]
DISPUTE_TIMELINE_ITEMS: list[tuple[str, str]] = [
    ("fact", f"【デモ】設計変更指示を受領{DEMO_SUFFIX}"),
    ("notice", f"【デモ】追加費用の請求書を送付{DEMO_SUFFIX}"),
    ("hearing", f"【デモ】第1回調停期日{DEMO_SUFFIX}"),
]

# 条項ライブラリ（/templates の「条項ライブラリ」タブ）。code は DEMO- で判別。
# (code, category, title, body, recommendation, tags)
CLAUSE_LIBRARY: list[tuple[str, str, str, str, str, list[str]]] = [
    (
        "DEMO-CLB-001",
        "支払条件",
        f"出来高部分払いの支払条件{DEMO_SUFFIX}",
        "出来高部分払いは、出来高の 3 分の 1 を超えない範囲で行うものとする。",
        "recommended",
        ["支払", "出来高"],
    ),
    (
        "DEMO-CLB-002",
        "変更",
        f"設計変更時の協議義務{DEMO_SUFFIX}",
        "設計図書の変更が必要となった場合、甲は速やかに乙と協議するものとする。",
        "required",
        ["変更", "協議"],
    ),
    (
        "DEMO-CLB-003",
        "遅延",
        f"工期延長の請求手続{DEMO_SUFFIX}",
        (
            "天候その他やむを得ない事由により工期の延長が必要な場合、"
            "乙は遅滞なく書面で申し出るものとする。"
        ),
        "recommended",
        ["工期", "遅延"],
    ),
    (
        "DEMO-CLB-004",
        "解除",
        f"一方的解除の制限{DEMO_SUFFIX}",
        "甲は、乙に責めに帰すべき事由がない限り、本契約を一方的に解除することができない。",
        "prohibited",
        ["解除"],
    ),
    (
        "DEMO-CLB-005",
        "紛争",
        f"紛争解決の段階的条項{DEMO_SUFFIX}",
        "紛争が生じた場合、当事者はまず誠実に協議し、次いで調停、仲裁の順に解決を図るものとする。",
        "recommended",
        ["紛争", "仲裁"],
    ),
    (
        "DEMO-CLB-006",
        "秘密保持",
        f"秘密保持義務の存続期間{DEMO_SUFFIX}",
        "秘密保持義務は、本契約の終了後 3 年間存続するものとする。",
        "optional",
        ["秘密保持"],
    ),
]

# IP ウォッチ検知イベント（/ip-watch）。デモ対象（notes に [DEMO]）に紐づける。
IP_WATCH_EVENTS: list[tuple[str, str, str]] = [
    ("new_application", "JP2026-000001", f"【デモ】競合他社の新規出願を検知{DEMO_SUFFIX}"),
    ("status_change", "JP2025-000123", f"【デモ】審査状況の変化を検知{DEMO_SUFFIX}"),
    ("registration", "JP2024-000456", f"【デモ】登録査定を検知{DEMO_SUFFIX}"),
    ("publication", "JP2026-000789", f"【デモ】公開公報の発行を検知{DEMO_SUFFIX}"),
]

# ===========================================================================
# ここまで Phase 3 デモデータ定義
# ===========================================================================

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


async def repair_legacy_review_issues(session) -> int:
    """Rewrite legacy ``legal_reviews.result.issues`` into the current shape.

    The rows created by the 2026-08-01 bootstrap store each issue as
    ``{"detail", "target", "summary", "severity"}``. The response model
    ``ReviewIssue`` (``app/schemas/legal_review.py``) requires
    ``clause_seq`` / ``risk_level`` / ``comment``, and ``review_service``
    forwards ``result["issues"]`` verbatim, so any of those rows makes
    ``GET /api/v1/reviews`` fail response validation with 500
    (measured 2026-09-28: 15 such rows in both ``legalops_mvp`` and
    ``legalops_prod``; the current seed shape is written correctly but
    pre-existing rows were never migrated).

    Only rows that still carry the legacy marker **and** whose contract is a demo
    contract (``CTR-2026-%``, the same convention the rest of this script uses to
    find and delete demo rows) are touched. The contract check matters: the
    legacy rows carry no ``demo`` flag in ``result`` and use ``claude-opus-4-7``
    as ``ai_model``, so the marker alone would also match a review a real user
    had created against a real contract, and rewriting that with fictional
    findings would be data corruption.

    The replacement content is the canonical ``REVIEW_ISSUES`` data, keeping the
    original issue count. Idempotent: re-running finds nothing to repair.

    Note: the API read path is separately hardened (api-fixer, task-5 #6) so a
    future shape drift degrades instead of returning 500; this function
    converges the stored data itself.
    """
    demo_contract_ids = set(
        (
            await session.execute(
                select(Contract.id).where(Contract.contract_no.like("CTR-2026-%"))
            )
        ).scalars()
    )
    rows = (await session.execute(select(LegalReview))).scalars().all()
    repaired = 0
    for review in rows:
        if review.contract_id not in demo_contract_ids:
            continue  # never rewrite a review attached to a non-demo contract
        result = review.result or {}
        issues = result.get("issues")
        if not isinstance(issues, list) or not issues:
            continue
        legacy = [
            i for i in issues if isinstance(i, dict) and "severity" in i and "risk_level" not in i
        ]
        if not legacy:
            continue  # already the current shape
        canonical = [dict(i) for i in REVIEW_ISSUES[: max(1, len(issues))]]
        # Reassign (do not mutate in place) so SQLAlchemy flags the JSON column dirty.
        review.result = {**result, "issues": canonical}
        repaired += 1
    return repaired


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


async def seed_phase3(
    session: Any,
    *,
    user: User,
    demo_contracts: list[Contract],
    counts: dict[str, int],
) -> None:
    """Phase 3 のデモデータを投入する（画面 35 項目が空にならないようにする）。

    ``seed()`` のローカル変数と衝突しないよう独立した関数スコープに分離している
    （同一関数内で ``row`` / ``spec`` 等を再代入すると mypy が型を混同するため）。
    冪等: 各ブロックはデモ判別子で既存を確認してから追加する。
    """

    # =====================================================================
    # Phase 3 デモデータ（画面 /whistleblower・/evidence・/compliance/antitrust・
    # /disputes 詳細・/templates（条項ライブラリ）・/ip-watch・/settings・
    # /joint-ventures 詳細・/change-orders 詳細 が空にならないよう投入する）
    #
    # 冪等性: 各ブロックはデモ判別子（DEMO_SUFFIX を含むタイトル／DEMO- プレフィックス
    # ／デモ契約・紛争の ID）で既存を確認してから追加する。再実行しても重複しない。
    # 実データの削除・改変は行わない（追加のみ）。
    # =====================================================================
    actor_role = str(user.role)

    # ---- 条項ライブラリ（画面 /templates・code=DEMO-%）----
    existing_clause_codes = set((await session.execute(select(ClauseLibrary.code))).scalars())
    clause_library_count = 0
    for code, category, title, body, recommendation, tags in CLAUSE_LIBRARY:
        if code in existing_clause_codes:
            continue
        session.add(
            ClauseLibrary(
                code=code,
                category=category,
                title=title,
                body=body,
                recommendation=recommendation,
                tags=tags,
                version=1,
                effective_from=BASE_DATE - timedelta(days=365),
                created_by=user.id,
                updated_by=user.id,
            )
        )
        clause_library_count += 1
        existing_clause_codes.add(code)
    await session.flush()
    counts["clause_library"] = clause_library_count

    # ---- IP ウォッチ検知イベント（画面 /ip-watch・デモ対象に紐づける）----
    demo_target_ids = list(
        (
            await session.execute(
                select(IpWatchTarget.id).where(IpWatchTarget.notes.like("%[DEMO]%"))
            )
        ).scalars()
    )
    existing_event_codes = set((await session.execute(select(IpWatchEvent.event_code))).scalars())
    ip_event_count = 0
    if demo_target_ids:
        for idx, (event_type, app_no, description) in enumerate(IP_WATCH_EVENTS):
            event_code = f"DEMO-IPW-{idx + 1:02d}"
            if event_code in existing_event_codes:
                continue
            session.add(
                IpWatchEvent(
                    watch_target_id=demo_target_ids[idx % len(demo_target_ids)],
                    ip_asset_id=None,
                    application_number=app_no,
                    event_type=event_type,
                    event_code=event_code,
                    description=description,
                    event_data={"demo": True},
                    is_read=False,
                    detected_at=datetime.now(UTC) - timedelta(days=idx * 3 + 1),
                )
            )
            ip_event_count += 1
            existing_event_codes.add(event_code)
        await session.flush()
    counts["ip_watch_events"] = ip_event_count

    # ---- 契約添付ファイル（/contracts 詳細・証拠の紐付け先）----
    existing_attachment_refs = set(
        (await session.execute(select(Attachment.sharepoint_item_id))).scalars()
    )
    attachment_count = 0
    demo_attachments: list[Attachment] = []
    for idx, contract in enumerate(demo_contracts[:4]):
        ref = f"DEMO-SP-{idx + 1:04d}"
        if ref in existing_attachment_refs:
            continue
        attachment = Attachment(
            contract_id=contract.id,
            filename=f"demo-contract-{idx + 1:02d}.pdf",
            mime_type="application/pdf",
            size_bytes=120_000 + idx * 4_096,
            sharepoint_item_id=ref,
            storage="sharepoint",
            checksum_sha256=_demo_sha256(ref),
            version=1,
            is_primary=(idx == 0),
            uploaded_by=user.id,
        )
        session.add(attachment)
        demo_attachments.append(attachment)
        attachment_count += 1
        existing_attachment_refs.add(ref)
    await session.flush()
    counts["attachments"] = attachment_count

    # ---- 契約単位 ACL（/contracts 詳細のアクセス権タブ・UI から到達する）----
    legal_dept_id = (
        await session.execute(select(Department.id).where(Department.name == "法務部"))
    ).scalar_one_or_none()
    acl_contract_ids = [c.id for c in demo_contracts[:3]]
    if acl_contract_ids:
        existing_acl_contracts = set(
            (
                await session.execute(
                    select(AccessControlEntry.contract_id).where(
                        AccessControlEntry.contract_id.in_(acl_contract_ids)
                    )
                )
            ).scalars()
        )
    else:
        existing_acl_contracts = set()
    acl_count = 0
    acl_specs: list[tuple[str, str, str]] = [
        ("user", str(user.id), "admin"),
        ("role", "reviewer", "read"),
        ("role", "auditor", "read"),
        ("external_counsel", "demo-counsel@example.invalid", "read"),
    ]
    if legal_dept_id is not None:
        acl_specs.append(("department", str(legal_dept_id), "write"))
    for contract in demo_contracts[:3]:
        if contract.id in existing_acl_contracts:
            continue
        for principal_type, principal_id, access_level in acl_specs:
            session.add(
                AccessControlEntry(
                    contract_id=contract.id,
                    principal_type=principal_type,
                    principal_id=principal_id,
                    access_level=access_level,
                    granted_by=user.id,
                    expires_at=None,
                )
            )
            acl_count += 1
    await session.flush()
    counts["access_control_entries"] = acl_count

    # ---- 変更契約の証拠（画面 /change-orders 詳細）----
    demo_change_ids = [
        row.id
        for row in (
            await session.execute(
                select(ChangeOrder.id, ChangeOrder.change_no).where(
                    ChangeOrder.change_no.like("CHG-2026-%")
                )
            )
        ).all()
    ]
    if demo_change_ids:
        existing_coe = set(
            (
                await session.execute(
                    select(ChangeOrderEvidence.change_order_id).where(
                        ChangeOrderEvidence.change_order_id.in_(demo_change_ids)
                    )
                )
            ).scalars()
        )
    else:
        existing_coe = set()
    change_order_evidence_count = 0
    for idx, change_id in enumerate(demo_change_ids):
        if change_id in existing_coe:
            continue
        session.add(
            ChangeOrderEvidence(
                change_order_id=change_id,
                evidence_type=["daily_report", "photo", "email", "minutes", "instruction", "other"][
                    idx % 6
                ],
                description=f"【デモ】変更契約の根拠資料{DEMO_SUFFIX}",
                occurred_at=BASE_DATE + timedelta(days=idx * 5),
                attachment_id=demo_attachments[idx % len(demo_attachments)].id
                if demo_attachments
                else None,
                created_by=user.id,
                updated_by=user.id,
            )
        )
        change_order_evidence_count += 1
    await session.flush()
    counts["change_order_evidence"] = change_order_evidence_count

    # ---- Legal Hold（画面 /evidence・/settings の保全状況）----
    existing_hold_reasons = set((await session.execute(select(LegalHold.reason))).scalars())
    hold_count = 0
    demo_holds: list[LegalHold] = []
    for idx, contract in enumerate(demo_contracts[:2]):
        reason = f"【デモ】{contract.contract_no} に係る証拠保全{DEMO_SUFFIX}"
        if reason in existing_hold_reasons:
            continue
        hold = LegalHold(
            target_type="contract",
            target_id=contract.id,
            reason=reason,
            status="active",
            started_by=user.id,
            started_at=datetime.now(UTC) - timedelta(days=30 + idx * 10),
            evidence_ids=[],
            ethical_wall=(idx == 1),
        )
        session.add(hold)
        demo_holds.append(hold)
        hold_count += 1
        existing_hold_reasons.add(reason)
    await session.flush()
    counts["legal_holds"] = hold_count

    # ---- 証拠・eDiscovery（画面 /evidence・title 末尾 DEMO_SUFFIX で判別）----
    existing_evidence_titles = set(
        (
            await session.execute(
                select(Evidence.title).where(Evidence.title.like(f"%{DEMO_SUFFIX}"))
            )
        ).scalars()
    )
    new_evidence: list[Evidence] = []
    evidence_count = 0
    for key, title, description, source_type, mime, filename, duplicate_of in EVIDENCES:
        if title in existing_evidence_titles:
            continue
        checksum_seed = duplicate_of or key
        row = await evidence_service.create_evidence(
            session,
            actor_id=user.id,
            title=title,
            description=description,
            source_type=source_type,
            contract_id=demo_contracts[0].id if demo_contracts else None,
            filename=filename,
            mime_type=mime,
            storage="sharepoint",
            storage_ref=f"DEMO-EVD/{filename}",
            checksum_sha256=_demo_sha256(checksum_seed),
            collected_by=user.id,
            collected_by_name="伊藤 直美",
            collected_at=datetime.now(UTC) - timedelta(days=20),
        )
        new_evidence.append(row)
        evidence_count += 1
        existing_evidence_titles.add(title)
    await session.flush()
    counts["evidences"] = evidence_count

    # Chain of Custody（追記専用）。新規証拠にのみ付与する（冪等）。
    custody_count = 0
    for row in new_evidence:
        for step, custody_action in enumerate(["collected", "received", "analyzed"]):
            await evidence_service.add_custody_event(
                session,
                evidence_id=row.id,
                actor_id=user.id,
                action=custody_action,
                actor_name="伊藤 直美",
                from_custodian="デモ現場事務所" if step == 0 else "デモ法務部",
                to_custodian="デモ法務部",
                notes=f"【デモ】Chain of Custody 記録（{custody_action}）{DEMO_SUFFIX}",
            )
            custody_count += 1
    await session.flush()
    counts["evidence_custody_events"] = custody_count

    # 保全対象の証拠に Legal Hold を紐付ける（デモ行のみ）。
    if demo_holds:
        held = list(
            (
                await session.execute(
                    select(Evidence)
                    .where(Evidence.title.like(f"%{DEMO_SUFFIX}"))
                    .order_by(Evidence.id)
                )
            )
            .scalars()
            .all()
        )
        for idx, row in enumerate(held[:2]):
            row.legal_hold_id = demo_holds[idx % len(demo_holds)].id
            row.is_under_hold = True
        await session.flush()

    # Legal Hold 解除承認。ORM モデル（TimestampMixin）は migration 025 に存在しない
    # ``deleted_at`` を参照するため INSERT/SELECT できず、生 SQL で投入する
    # （既知のスキーマ不整合。詳細は削除ブロックとタスク報告を参照）。
    hold_release_count = 0
    if demo_holds:
        existing_hr = (
            await session.execute(
                text(
                    "SELECT count(*) FROM evidence_hold_release_approvals "
                    "WHERE reason LIKE :pat"
                ),
                {"pat": f"%{DEMO_SUFFIX}"},
            )
        ).scalar_one()
        pending_evidence = list(
            (
                await session.execute(
                    select(Evidence.id)
                    .where(Evidence.title.like(f"%{DEMO_SUFFIX}"))
                    .order_by(Evidence.id)
                )
            ).scalars()
        )
        if not existing_hr:
            for idx, hold in enumerate(demo_holds):
                await session.execute(
                    text(
                        "INSERT INTO evidence_hold_release_approvals "
                        "(legal_hold_id, evidence_id, requested_by, requested_at, reason, status) "
                        "VALUES (:hold_id, :evidence_id, :requested_by, "
                        ":requested_at, :reason, :status)"
                    ),
                    {
                        "hold_id": hold.id,
                        "evidence_id": (
                            pending_evidence[idx] if idx < len(pending_evidence) else None
                        ),
                        "requested_by": user.id,
                        "requested_at": datetime.now(UTC) - timedelta(days=3 + idx),
                        "reason": f"【デモ】保全目的の消滅に伴う解除申請{DEMO_SUFFIX}",
                        "status": "pending" if idx == 0 else "rejected",
                    },
                )
                hold_release_count += 1
            await session.flush()
    counts["evidence_hold_release_approvals"] = hold_release_count

    # ---- 内部通報・調査（画面 /whistleblower）----
    # report_no はサービス層が WB-YYYY-NNNNNN で採番するため、削除の判別は
    # タイトル末尾の DEMO_SUFFIX で行う。
    existing_wb_titles = set(
        (
            await session.execute(
                select(WhistleblowerReport.title).where(
                    WhistleblowerReport.title.like(f"%{DEMO_SUFFIX}")
                )
            )
        ).scalars()
    )
    investigator_user_id = user.id
    # 調査担当者 ACL は (report_id, user_id) が UNIQUE のため、案件ごとに
    # 別ユーザーを割り当てて複数担当の状態を再現する。
    grant_pool = list(
        (
            await session.execute(
                select(User)
                .where(User.email.like("%@legalops-mvp.example.com"))
                .order_by(User.id)
            )
        ).scalars()
    )
    if user.id not in [u.id for u in grant_pool]:
        grant_pool.insert(0, user)
    wb_counts = {
        "whistleblower_reports": 0,
        "whistleblower_reporter_profiles": 0,
        "whistleblower_case_access": 0,
        "whistleblower_evidence": 0,
        "whistleblower_interviews": 0,
        "whistleblower_timeline_events": 0,
        "whistleblower_actions": 0,
    }
    for spec in WB_REPORTS:
        title = str(spec["title"])
        if title in existing_wb_titles:
            continue
        reporter = spec.get("reporter")
        report = await whistleblower_service.create_report(
            session,
            actor_id=user.id,
            category=str(spec["category"]),
            title=title,
            description=str(spec["description"]),
            severity=str(spec["severity"]),
            is_anonymous=bool(spec["is_anonymous"]),
            occurred_at=BASE_DATE - timedelta(days=45),
            reporter_name=str(reporter["name"]) if isinstance(reporter, dict) else None,
            contact_email=str(reporter["email"]) if isinstance(reporter, dict) else None,
            contact_phone=str(reporter["phone"]) if isinstance(reporter, dict) else None,
            department=str(reporter["department"]) if isinstance(reporter, dict) else None,
            relationship_to_subject=str(reporter["relationship"])
            if isinstance(reporter, dict)
            else None,
            consent_identity_disclosure=bool(reporter["consent"])
            if isinstance(reporter, dict)
            else False,
            lead_investigator_id=investigator_user_id,
        )
        wb_counts["whistleblower_reports"] += 1
        if isinstance(reporter, dict):
            wb_counts["whistleblower_reporter_profiles"] += 1
        # 調査ステータス（受付 → 調査中など）。create_report 直後は received。
        report.status = str(spec["status"])
        if report.status == "closed":
            report.closed_at = datetime.now(UTC)
            report.substantiated = True

        for grant_idx, (role_in_case, can_view_identity) in enumerate(spec["access"]):
            grantee = grant_pool[grant_idx % len(grant_pool)]
            await whistleblower_service.grant_case_access(
                session,
                report_id=report.id,
                actor_id=user.id,
                user_id=grantee.id,
                role_in_case=str(role_in_case),
                can_view_reporter_identity=bool(can_view_identity),
                expires_at=datetime.now(UTC) + timedelta(days=180),
            )
            wb_counts["whistleblower_case_access"] += 1
        for evidence_type, description, preserved in spec["evidence"]:
            await whistleblower_service.add_evidence(
                session,
                report_id=report.id,
                role=actor_role,
                user_id=user.id,
                evidence_type=str(evidence_type),
                description=str(description),
                occurred_at=BASE_DATE - timedelta(days=40),
                preserved=bool(preserved),
                chain_of_custody=f"【デモ】保全手続の記録{DEMO_SUFFIX}",
            )
            wb_counts["whistleblower_evidence"] += 1
        for interviewee_type, name, summary in spec["interviews"]:
            await whistleblower_service.add_interview(
                session,
                report_id=report.id,
                role=actor_role,
                user_id=user.id,
                interviewee_type=str(interviewee_type),
                conducted_at=datetime.now(UTC) - timedelta(days=15),
                interviewee_name=str(name),
                summary=str(summary),
            )
            wb_counts["whistleblower_interviews"] += 1
        for note in spec["notes"]:
            await whistleblower_service.add_note(
                session,
                report_id=report.id,
                role=actor_role,
                user_id=user.id,
                note=str(note),
            )
        for category, action_title, action_status in spec["actions"]:
            action = await whistleblower_service.add_action(
                session,
                report_id=report.id,
                role=actor_role,
                user_id=user.id,
                action_category=str(category),
                title=str(action_title),
                description=f"【デモ】是正・再発防止措置{DEMO_SUFFIX}",
                owner_id=user.id,
                due_date=BASE_DATE + timedelta(days=60),
            )
            action.status = str(action_status)
            if action.status in {"completed", "verified"}:
                action.completed_at = datetime.now(UTC) - timedelta(days=2)
            wb_counts["whistleblower_actions"] += 1
        existing_wb_titles.add(title)
    await session.flush()
    # タイムラインはサービス層が各操作で追記するため実測値を数える。
    wb_timeline_total = 0
    if wb_counts["whistleblower_reports"]:
        new_report_ids = list(
            (
                await session.execute(
                    select(WhistleblowerReport.id).where(
                        WhistleblowerReport.title.like(f"%{DEMO_SUFFIX}")
                    )
                )
            ).scalars()
        )
        wb_timeline_total = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(WhistleblowerTimelineEvent)
                    .where(WhistleblowerTimelineEvent.report_id.in_(new_report_ids))
                )
            ).scalar_one()
        )
    wb_counts["whistleblower_timeline_events"] = wb_timeline_total
    counts.update(wb_counts)

    # ---- 独禁法・入札談合コンプライアンス（画面 /compliance/antitrust）----
    existing_atc_subjects = set(
        (
            await session.execute(
                select(AntitrustCheck.subject).where(AntitrustCheck.subject.like(f"%{DEMO_SUFFIX}"))
            )
        ).scalars()
    )
    antitrust_check_count = 0
    for check_type, subject, context in ANTITRUST_CHECKS:
        if subject in existing_atc_subjects:
            continue
        await antitrust_service.create_check(
            session,
            actor_id=user.id,
            check_type=check_type,
            subject=subject,
            context=context,
            contract_id=demo_contracts[0].id if demo_contracts else None,
            notes=f"【デモ】決定論的ルールベース判定{DEMO_SUFFIX}",
        )
        antitrust_check_count += 1
        existing_atc_subjects.add(subject)
    await session.flush()
    counts["antitrust_checks"] = antitrust_check_count

    existing_apa_titles = set(
        (
            await session.execute(
                select(AntitrustPriorApplication.title).where(
                    AntitrustPriorApplication.title.like(f"%{DEMO_SUFFIX}")
                )
            )
        ).scalars()
    )
    antitrust_app_count = 0
    for idx, (app_type, app_title, counterparty, amount, app_status) in enumerate(
        ANTITRUST_APPLICATIONS
    ):
        if app_title in existing_apa_titles:
            continue
        application = await antitrust_service.create_application(
            session,
            actor_id=user.id,
            application_type=app_type,
            title=app_title,
            counterparty_name="田中 太郎",
            counterparty_organization=counterparty,
            purpose=f"【デモ】事前申請の目的（架空）{DEMO_SUFFIX}",
            scheduled_at=datetime.now(UTC) + timedelta(days=7 + idx * 3),
            location="架空本社会議室（デモ）",
            amount_jpy=amount,
            attendees=["田中 太郎", "鈴木 花子"],
            contract_id=demo_contracts[0].id if demo_contracts else None,
        )
        application.status = app_status
        if app_status in {"approved", "completed"}:
            application.approved_by = user.id
            application.approved_at = datetime.now(UTC) - timedelta(days=5)
            application.decision_note = f"【デモ】承認（架空の決裁記録）{DEMO_SUFFIX}"
        if app_status == "completed":
            application.occurred_at = datetime.now(UTC) - timedelta(days=2)
            application.outcome_note = f"【デモ】実施記録（架空）{DEMO_SUFFIX}"
            application.reported_at = datetime.now(UTC) - timedelta(days=1)
        if app_status == "rejected":
            application.decision_note = f"【デモ】金額上限を超えるため却下{DEMO_SUFFIX}"
        antitrust_app_count += 1
        existing_apa_titles.add(app_title)
    await session.flush()
    counts["antitrust_prior_applications"] = antitrust_app_count

    existing_consult_queries = set(
        (
            await session.execute(
                select(AntitrustConsultation.query_text).where(
                    AntitrustConsultation.query_text.like("%【デモ】%")
                )
            )
        ).scalars()
    )
    antitrust_consult_count = 0
    for query_text, answer_text in ANTITRUST_CONSULTATIONS:
        if query_text in existing_consult_queries:
            continue
        await antitrust_service.create_consultation(
            session,
            actor_id=user.id,
            query_text=query_text,
            contract_id=demo_contracts[0].id if demo_contracts else None,
        )
        # create_consultation は引用付き回答を生成する。デモ回答で上書きする。
        row = (
            await session.execute(
                select(AntitrustConsultation)
                .where(AntitrustConsultation.query_text == query_text)
                .order_by(AntitrustConsultation.id.desc())
                .limit(1)
            )
        ).scalar_one()
        row.answer_text = answer_text
        antitrust_consult_count += 1
        existing_consult_queries.add(query_text)
    await session.flush()
    counts["antitrust_consultations"] = antitrust_consult_count

    existing_training_titles = set(
        (
            await session.execute(
                select(ComplianceTraining.training_title).where(
                    ComplianceTraining.training_title.like(f"%{DEMO_SUFFIX}")
                )
            )
        ).scalars()
    )
    training_count = 0
    for idx, (training_title, category, score) in enumerate(COMPLIANCE_TRAININGS):
        if training_title in existing_training_titles:
            continue
        await antitrust_service.create_training(
            session,
            actor_id=user.id,
            training_title=training_title,
            completed_at=BASE_DATE - timedelta(days=20 + idx * 15),
            user_id=user.id if idx % 2 == 0 else None,
            attendee_name="伊藤 直美" if idx % 2 else None,
            category=category,
            score=score,
            notes=f"【デモ】研修履歴（架空）{DEMO_SUFFIX}",
        )
        training_count += 1
        existing_training_titles.add(training_title)
    await session.flush()
    counts["compliance_trainings"] = training_count

    # ---- 紛争管理の高度化（画面 /disputes 詳細）----
    # 対象はデモ紛争（DSP-2026-%）のみ。既存データには触れない。
    demo_disputes = list(
        (
            await session.execute(
                select(Dispute)
                .where(Dispute.dispute_no.like("DSP-2026-%"))
                .order_by(Dispute.dispute_no)
            )
        )
        .scalars()
        .all()
    )
    dispute_ext_counts = {
        "dispute_delay_events": 0,
        "dispute_argument_positions": 0,
        "dispute_settlement_options": 0,
        "dispute_proceeding_stages": 0,
        "dispute_evidence": 0,
        "dispute_timeline_events": 0,
    }
    for dispute in demo_disputes:
        # 既に遅延事象があるデモ紛争はスキップ（冪等）。
        has_ext = (
            await session.execute(
                select(DisputeDelayEvent.id)
                .where(DisputeDelayEvent.dispute_id == dispute.id)
                .limit(1)
            )
        ).scalar_one_or_none()
        if has_ext is not None:
            continue

        for spec in DISPUTE_DELAY_EVENTS:
            occurred_from = BASE_DATE + timedelta(days=int(spec["occurred_from_offset"]))
            occurred_to = BASE_DATE + timedelta(days=int(spec["occurred_to_offset"]))
            delay_row = await dispute_ext_service.add_delay_event(
                session,
                dispute_id=dispute.id,
                actor_id=user.id,
                data={
                    "cause_category": spec["cause_category"],
                    "title": spec["title"],
                    "description": spec["description"],
                    "occurred_from": occurred_from,
                    "occurred_to": occurred_to,
                    "delay_days": spec["delay_days"],
                    "responsible_party": spec["responsible_party"],
                    "additional_cost_jpy": spec["additional_cost_jpy"],
                    "eot_days_requested": spec["eot_days_requested"],
                },
            )
            delay_row.eot_status = str(spec["eot_status"])
            granted = spec["eot_days_granted"]
            if granted is not None:
                delay_row.eot_days_granted = int(granted)
                delay_row.eot_decided_at = datetime.now(UTC) - timedelta(days=5)
                delay_row.eot_decided_by = user.id
                delay_row.eot_note = f"【デモ】工期延長の判定記録{DEMO_SUFFIX}"
            dispute_ext_counts["dispute_delay_events"] += 1

        for spec in DISPUTE_ARGUMENTS:
            await dispute_ext_service.add_argument_position(
                session,
                dispute_id=dispute.id,
                actor_id=user.id,
                data={**spec, "evidence_refs": []},
            )
            dispute_ext_counts["dispute_argument_positions"] += 1

        for spec in DISPUTE_SETTLEMENT_OPTIONS:
            await dispute_ext_service.add_settlement_option(
                session,
                dispute_id=dispute.id,
                actor_id=user.id,
                data=dict(spec),
            )
            dispute_ext_counts["dispute_settlement_options"] += 1

        for spec in DISPUTE_STAGES:
            started = BASE_DATE + timedelta(days=int(spec["started_offset"]))
            ended_offset = spec["ended_offset"]
            ended_at = (
                BASE_DATE + timedelta(days=int(ended_offset))
                if ended_offset is not None
                else None
            )
            await dispute_ext_service.add_proceeding_stage(
                session,
                dispute_id=dispute.id,
                actor_id=user.id,
                data={
                    "stage": spec["stage"],
                    "started_at": started,
                    "ended_at": ended_at,
                    "forum": spec["forum"],
                    "notes": f"【デモ】進行ステージの記録{DEMO_SUFFIX}",
                },
            )
            dispute_ext_counts["dispute_proceeding_stages"] += 1

        for ev_type, description in DISPUTE_EVIDENCE_ITEMS:
            session.add(
                DisputeEvidence(
                    dispute_id=dispute.id,
                    evidence_type=ev_type,
                    description=description,
                    occurred_at=BASE_DATE + timedelta(days=12),
                    preserved=True,
                    created_by=user.id,
                    updated_by=user.id,
                )
            )
            dispute_ext_counts["dispute_evidence"] += 1

        for ev_type, description in DISPUTE_TIMELINE_ITEMS:
            session.add(
                DisputeTimelineEvent(
                    dispute_id=dispute.id,
                    occurred_at=datetime.now(UTC) - timedelta(days=10),
                    event_type=ev_type,
                    description=description,
                    created_by=user.id,
                    updated_by=user.id,
                )
            )
            dispute_ext_counts["dispute_timeline_events"] += 1
    await session.flush()
    counts.update(dispute_ext_counts)

    # ---- JV 詳細（画面 /joint-ventures 詳細・デモ JV のみ）----
    demo_jv_ids = list(
        (
            await session.execute(
                select(JointVenture.id).where(JointVenture.jv_no.like("JV-DEMO-%"))
            )
        ).scalars()
    )
    jv_detail_counts = {"jv_agreements": 0, "jv_disputes": 0, "jv_settlements": 0}
    if demo_jv_ids:
        existing_jv_agreement_nos = set(
            (await session.execute(select(JvAgreement.agreement_no))).scalars()
        )
        existing_jv_dispute_nos = set(
            (await session.execute(select(JvDispute.dispute_no))).scalars()
        )
        existing_jv_settlement_nos = set(
            (await session.execute(select(JvSettlement.settlement_no))).scalars()
        )
        for idx, jv_id in enumerate(demo_jv_ids):
            agreement_no = f"JVA-DEMO-{idx + 1:03d}"
            if agreement_no not in existing_jv_agreement_nos:
                session.add(
                    JvAgreement(
                        jv_id=jv_id,
                        agreement_no=agreement_no,
                        status="signed",  # JvAgreementStatus.SIGNED
                        title=f"【デモ】共同企業体協定書{DEMO_SUFFIX}",
                        summary="架空の JV 協定です（デモ）。",
                        signed_at=BASE_DATE - timedelta(days=120),
                        created_by=user.id,
                        updated_by=user.id,
                    )
                )
                jv_detail_counts["jv_agreements"] += 1
            dispute_no = f"JVD-DEMO-{idx + 1:03d}"
            if dispute_no not in existing_jv_dispute_nos:
                session.add(
                    JvDispute(
                        jv_id=jv_id,
                        dispute_no=dispute_no,
                        status="open",
                        title=f"【デモ】出来高配分に関する意見相違{DEMO_SUFFIX}",
                        claimant_name="デモ構成員A（架空）",
                        respondent_name="デモ構成員B（架空）",
                        amount_claimed_jpy=3_000_000 + idx * 500_000,
                        detail="架空の JV 内部紛争です（デモ）。",
                        raised_at=BASE_DATE - timedelta(days=30),
                        created_by=user.id,
                        updated_by=user.id,
                    )
                )
                jv_detail_counts["jv_disputes"] += 1
            settlement_no = f"JVS-DEMO-{idx + 1:03d}"
            if settlement_no not in existing_jv_settlement_nos:
                session.add(
                    JvSettlement(
                        jv_id=jv_id,
                        settlement_no=settlement_no,
                        status="settled",  # JvSettlementStatus.SETTLED
                        title=f"【デモ】精算合意書{DEMO_SUFFIX}",
                        settled_at=BASE_DATE - timedelta(days=10),
                        settlement_amount_jpy=1_500_000 + idx * 250_000,
                        detail="架空の JV 精算合意です（デモ）。",
                        recorded_by=user.id,
                        created_by=user.id,
                        updated_by=user.id,
                    )
                )
                jv_detail_counts["jv_settlements"] += 1
        await session.flush()
    counts.update(jv_detail_counts)



async def delete_phase3_demo(session: Any, counts: dict[str, int]) -> None:
    """Phase 3 のデモデータを削除する（契約・紛争削除より先に呼ぶこと）。

    これらは契約・紛争・保全へ FK を持つため、先に消さないと SET NULL /
    CASCADE で件数を正しく数えられない。
    """

    demo_contract_ids_for_phase3 = list(
        (
            await session.execute(
                select(Contract.id).where(Contract.contract_no.like("CTR-2026-%"))
            )
        ).scalars()
    )

    # ------------------------------------------------------------------
    # Phase 3 デモデータの削除（契約・紛争・JV の削除より先に処理する）
    #
    # これらは契約/紛争/保全へ FK を持つため、先に消さないと
    # SET NULL や CASCADE で件数を正しく数えられない。
    # ------------------------------------------------------------------

    # 条項ライブラリ（code=DEMO-%）
    counts["clause_library"] = (
        await session.execute(delete(ClauseLibrary).where(ClauseLibrary.code.like("DEMO-%")))
    ).rowcount

    # IP ウォッチ検知イベント（event_code=DEMO-IPW-%）
    counts["ip_watch_events"] = (
        await session.execute(
            delete(IpWatchEvent).where(IpWatchEvent.event_code.like("DEMO-IPW-%"))
        )
    ).rowcount

    # 変更契約の証拠（デモ変更契約 CHG-2026-% 配下）
    demo_change_ids = list(
        (
            await session.execute(
                select(ChangeOrder.id).where(ChangeOrder.change_no.like("CHG-2026-%"))
            )
        ).scalars()
    )
    if demo_change_ids:
        counts["change_order_evidence"] = (
            await session.execute(
                delete(ChangeOrderEvidence).where(
                    ChangeOrderEvidence.change_order_id.in_(demo_change_ids)
                )
            )
        ).rowcount
    else:
        counts["change_order_evidence"] = 0

    # 証拠・eDiscovery（title 末尾 DEMO_SUFFIX で判別）
    demo_evidence_ids = list(
        (
            await session.execute(
                select(Evidence.id).where(Evidence.title.like(f"%{DEMO_SUFFIX}"))
            )
        ).scalars()
    )
    # evidence_hold_release_approvals は ORM モデルが migration に存在しない
    # ``deleted_at`` を参照するため ORM では削除できない（生 SQL で削除）。
    if demo_evidence_ids:
        counts["evidence_hold_release_approvals"] = (
            await session.execute(
                text(
                    "DELETE FROM evidence_hold_release_approvals "
                    "WHERE reason LIKE :pat OR evidence_id IN :evidence_ids"
                ).bindparams(bindparam("evidence_ids", expanding=True)),
                {"pat": f"%{DEMO_SUFFIX}", "evidence_ids": demo_evidence_ids},
            )
        ).rowcount
        counts["evidence_custody_events"] = (
            await session.execute(
                delete(EvidenceCustodyEvent).where(
                    EvidenceCustodyEvent.evidence_id.in_(demo_evidence_ids)
                )
            )
        ).rowcount
        counts["evidences"] = (
            await session.execute(delete(Evidence).where(Evidence.id.in_(demo_evidence_ids)))
        ).rowcount
    else:
        counts["evidence_hold_release_approvals"] = (
            await session.execute(
                text(
                    "DELETE FROM evidence_hold_release_approvals WHERE reason LIKE :pat"
                ),
                {"pat": f"%{DEMO_SUFFIX}"},
            )
        ).rowcount
        counts["evidence_custody_events"] = 0
        counts["evidences"] = 0

    # Legal Hold（reason 末尾 DEMO_SUFFIX で判別）
    counts["legal_holds"] = (
        await session.execute(delete(LegalHold).where(LegalHold.reason.like(f"%{DEMO_SUFFIX}")))
    ).rowcount

    # 内部通報（title 末尾 DEMO_SUFFIX で判別・子 → 親の順）
    demo_wb_ids = list(
        (
            await session.execute(
                select(WhistleblowerReport.id).where(
                    WhistleblowerReport.title.like(f"%{DEMO_SUFFIX}")
                )
            )
        ).scalars()
    )
    if demo_wb_ids:
        for wb_model in (
            WhistleblowerAction,
            WhistleblowerTimelineEvent,
            WhistleblowerInterview,
            WhistleblowerEvidence,
            WhistleblowerCaseAccess,
            WhistleblowerReporterProfile,
        ):
            report_filter = wb_model.report_id.in_(demo_wb_ids)  # type: ignore[attr-defined]
            counts[wb_model.__tablename__] = (
                await session.execute(delete(wb_model).where(report_filter))
            ).rowcount
        counts["whistleblower_reports"] = (
            await session.execute(
                delete(WhistleblowerReport).where(WhistleblowerReport.id.in_(demo_wb_ids))
            )
        ).rowcount
    else:
        counts["whistleblower_actions"] = 0
        counts["whistleblower_timeline_events"] = 0
        counts["whistleblower_interviews"] = 0
        counts["whistleblower_evidence"] = 0
        counts["whistleblower_case_access"] = 0
        counts["whistleblower_reporter_profiles"] = 0
        counts["whistleblower_reports"] = 0

    # 独禁法・入場談合コンプライアンス（デモ判別子で削除）
    counts["antitrust_checks"] = (
        await session.execute(
            delete(AntitrustCheck).where(AntitrustCheck.subject.like(f"%{DEMO_SUFFIX}"))
        )
    ).rowcount
    counts["antitrust_prior_applications"] = (
        await session.execute(
            delete(AntitrustPriorApplication).where(
                AntitrustPriorApplication.title.like(f"%{DEMO_SUFFIX}")
            )
        )
    ).rowcount
    counts["antitrust_consultations"] = (
        await session.execute(
            delete(AntitrustConsultation).where(
                AntitrustConsultation.query_text.like("%【デモ】%")
            )
        )
    ).rowcount
    counts["compliance_trainings"] = (
        await session.execute(
            delete(ComplianceTraining).where(
                ComplianceTraining.training_title.like(f"%{DEMO_SUFFIX}")
            )
        )
    ).rowcount

    # 紛争管理の高度化（デモ紛争 DSP-2026-% 配下）
    demo_dispute_ids = list(
        (
            await session.execute(
                select(Dispute.id).where(Dispute.dispute_no.like("DSP-2026-%"))
            )
        ).scalars()
    )
    for disp_model in (
        DisputeDelayEvent,
        DisputeArgumentPosition,
        DisputeSettlementOption,
        DisputeProceedingStage,
        DisputeEvidence,
        DisputeTimelineEvent,
    ):
        if demo_dispute_ids:
            dispute_filter = disp_model.dispute_id.in_(  # type: ignore[attr-defined]
                demo_dispute_ids
            )
            counts[disp_model.__tablename__] = (
                await session.execute(delete(disp_model).where(dispute_filter))
            ).rowcount
        else:
            counts[disp_model.__tablename__] = 0

    # 契約単位 ACL（デモ契約 CTR-2026-% 配下・contracts の CASCADE 前に消す）
    if demo_contract_ids_for_phase3:
        counts["access_control_entries"] = (
            await session.execute(
                delete(AccessControlEntry).where(
                    AccessControlEntry.contract_id.in_(demo_contract_ids_for_phase3)
                )
            )
        ).rowcount
    else:
        counts["access_control_entries"] = 0

    # 添付（sharepoint_item_id=DEMO-SP-%・change_order_evidence 削除後に消す）
    counts["attachments"] = (
        await session.execute(
            delete(Attachment).where(Attachment.sharepoint_item_id.like("DEMO-SP-%"))
        )
    ).rowcount



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
    counts["reviews_repaired"] = await repair_legacy_review_issues(session)

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
        # 冪等: 同一協力会社・同一タイトルの再審査が既にあれば再投入しない。
        # 旧実装は無条件に create_review していたため、再実行のたびに
        # partner_reviews が 3 件ずつ増えていた（2026-09-28 実測: 2 回目で +3）。
        review_title = f"定期再審査（デモ）— {partner_row.name}"
        already_seeded = (
            await session.execute(
                select(PartnerReview.id).where(
                    PartnerReview.partner_id == partner_row.id,
                    PartnerReview.title == review_title,
                )
            )
        ).first()
        if already_seeded is not None:
            # Risk Score は毎回再計算しても同値（決定論的）なので冪等に再実行する。
            await partner_ext_service.refresh_risk_score(session, partner_id=partner_row.id)
            continue
        review = await partner_ext_service.create_review(
            session,
            actor_id=user.id,
            partner_id=partner_row.id,
            review_type="periodic",
            title=review_title,
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

    # ---- 労務費コミットメント（#28 / 画面 /labor-wage）----
    # デモ契約 2 件に表明を登録（冪等: タイトルで判別）。
    existing_commitments = set(
        (await session.execute(select(LaborCommitment.title))).scalars()
    )
    commitment_count = 0
    created_commitments: list[LaborCommitment] = []
    if demo_contracts:
        for contract, ctype, title, statement in [
            (
                demo_contracts[0],
                "wage_payment",
                "賃金支払確約（デモ）",
                "下請労働者への賃金を適時に、適正な額で支払うことを表明します（架空）。",
            ),
            (
                demo_contracts[0],
                "proper_allocation",
                "労務費の適正配分（デモ）",
                "労務費を適正に配分し、改善に努めることを表明します（架空）。",
            ),
            (
                demo_contracts[1] if len(demo_contracts) > 1 else demo_contracts[0],
                "no_lump_subcontract",
                "一括下請負の禁止遵守（デモ）",
                "一括して下請負をしないことを遵守します（架空）。",
            ),
        ]:
            if title in existing_commitments:
                continue
            row = LaborCommitment(
                contract_id=contract.id,
                commitment_type=ctype,
                title=title,
                statement=statement,
                status="active",
                confirmed_at=date.today(),
                created_by=user.id,
            )
            session.add(row)
            created_commitments.append(row)
            existing_commitments.add(title)
            commitment_count += 1
    await session.flush()
    counts["labor_commitments"] = commitment_count

    # Phase 3 デモデータ（whistleblower / evidence / antitrust / dispute 拡張 /
    # 条項ライブラリ / IP ウォッチ検知 / Legal Hold / JV 詳細）は seed_phase3() に集約。
    await seed_phase3(session, user=user, demo_contracts=demo_contracts, counts=counts)
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
    for commitment in created_commitments:
        await _log(
            session,
            user,
            "labor_commitment.create",
            "labor_commitments",
            commitment.id,
            title=commitment.title,
        )
        audit_count += 1
    counts["audit_logs"] = audit_count

    return counts


async def delete_demo(session) -> dict[str, int]:
    counts: dict[str, int] = {}

    await delete_phase3_demo(session, counts)
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
        counts["ip_watch_events"] = counts.get("ip_watch_events", 0) + (
            await session.execute(delete(IpWatchEvent).where(IpWatchEvent.ip_asset_id.in_(demo_asset_ids)))
        ).rowcount
        counts["ip_assets"] = (
            await session.execute(delete(IpAsset).where(IpAsset.id.in_(demo_asset_ids)))
        ).rowcount
    else:
        counts["ip_documents"] = 0
        counts["ip_watch_events"] = counts.get("ip_watch_events", 0)
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
    # 労務費コミットメント（デモタイトルで判別）
    counts["labor_commitments"] = (
        await session.execute(
            delete(LaborCommitment).where(LaborCommitment.title.like("%（デモ）%"))
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
