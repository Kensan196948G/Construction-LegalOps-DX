"""Compliance checker.

Pattern-based compliance scanner that turns the long-form checklist in
``docs/construction_law_checklist.md`` into a list of automated rules.
For Loop 2 we cover the most frequently-failing items: 建設業法 19 条
書面要件, 反社条項, 下請法 3 条書面, 電子帳簿保存法, 個人情報保護法,
偽装請負, JV / 公共工事ベースルール.

Each rule produces a :class:`ComplianceFinding` describing the rule
that fired, severity, and the citation pointing back to the law/policy.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable

import structlog

from app.models.enums import ContractType

logger = structlog.get_logger(__name__)


class ComplianceSeverity(str, Enum):
    """Severity of a compliance finding."""

    INFO = "info"
    WARN = "warn"
    BLOCK = "block"  # MUST-fix before signing


@dataclass(slots=True)
class ComplianceFinding:
    """A single rule result."""

    code: str
    title: str
    severity: ComplianceSeverity
    description: str
    citation: str
    suggestion: str | None = None
    matched_keywords: list[str] = field(default_factory=list)


@runtime_checkable
class _HasText(Protocol):
    """Anything that exposes ``.text`` (and optionally typed metadata)."""

    text: str


@dataclass(slots=True)
class ContractSnapshot:
    """Lightweight view of a contract used for compliance scanning.

    The full SQLAlchemy ``Contract`` model is owned by another team; we
    accept either it (duck-typed) or a manually-constructed snapshot.
    """

    text: str
    contract_type: ContractType | str = ContractType.OTHER
    amount_jpy: int | None = None
    is_public_work: bool = False
    counterparty_capital_jpy: int | None = None
    our_capital_jpy: int | None = None
    handles_personal_data: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


_KEN_19_KEYWORDS = (
    ("工事内容", "工事内容"),
    ("請負代金", "請負代金"),
    ("工期", "工期"),
    ("引渡", "引渡時期"),
    ("前金払", "前金払"),
    ("設計変更", "設計変更時の取扱"),
    ("不可抗力", "天災等不可抗力"),
    ("契約不適合", "契約不適合責任"),
    ("紛争解決", "紛争解決方法"),
)


class ComplianceChecker:
    """Apply a fixed rule set to a contract text."""

    async def check(self, contract: Any) -> list[ComplianceFinding]:
        snapshot = self._coerce(contract)
        text = snapshot.text or ""

        findings: list[ComplianceFinding] = []
        findings.extend(self._check_kenpou_19(snapshot, text))
        findings.extend(self._check_antisocial(text))
        findings.extend(self._check_subcontract_law(snapshot, text))
        findings.extend(self._check_electronic_books_law(text))
        findings.extend(self._check_personal_data(snapshot, text))
        findings.extend(self._check_disguised_contracting(snapshot, text))
        findings.extend(self._check_public_work(snapshot, text))

        logger.info(
            "compliance.check",
            contract_type=str(snapshot.contract_type),
            amount=snapshot.amount_jpy,
            findings=len(findings),
            blocking=sum(1 for f in findings if f.severity == ComplianceSeverity.BLOCK),
        )
        return findings

    # ------------------------------------------------------------------
    # Rule implementations
    # ------------------------------------------------------------------

    def _check_kenpou_19(
        self, snapshot: ContractSnapshot, text: str
    ) -> list[ComplianceFinding]:
        ct = snapshot.contract_type
        if ct not in (ContractType.UKEOI, "請負"):
            return []
        missing: list[str] = []
        for keyword, label in _KEN_19_KEYWORDS:
            if keyword not in text:
                missing.append(label)
        if not missing:
            return []
        return [
            ComplianceFinding(
                code="construction_law_19",
                title="建設業法 19 条 必要記載事項の欠落",
                severity=ComplianceSeverity.BLOCK,
                description=(
                    "建設業法 19 条 1 項の必要記載事項のうち、"
                    f"次が見当たりません: {', '.join(missing)}"
                ),
                citation="建設業法 19 条 1 項",
                suggestion="着工前に書面交付が必要です。社内雛形で補完してください。",
                matched_keywords=missing,
            )
        ]

    def _check_antisocial(self, text: str) -> list[ComplianceFinding]:
        if re.search(r"反社会的勢力|暴力団排除", text):
            return []
        return [
            ComplianceFinding(
                code="antisocial_clause_missing",
                title="反社条項の欠落",
                severity=ComplianceSeverity.BLOCK,
                description="反社会的勢力排除条項が見当たりません。",
                citation="社内規程 / 各都道府県暴力団排除条例",
                suggestion="社内雛形の反社条項を追記してください。",
            )
        ]

    def _check_subcontract_law(
        self, snapshot: ContractSnapshot, text: str
    ) -> list[ComplianceFinding]:
        """Trigger 下請法 review when the capital threshold matches."""
        ours = snapshot.our_capital_jpy
        theirs = snapshot.counterparty_capital_jpy
        if ours is None or theirs is None:
            return []
        # Simplified threshold: 製造委託・修理委託は資本金 3 億円超 / 1,000 万円超〜3 億円
        # for the purposes of Loop 2 we flag the typical "subject" pattern.
        if ours > 300_000_000 and theirs <= 300_000_000:
            findings: list[ComplianceFinding] = [
                ComplianceFinding(
                    code="subcontract_act_applies",
                    title="下請法適用の可能性",
                    severity=ComplianceSeverity.WARN,
                    description="資本金区分から下請法が適用される可能性があります。",
                    citation="下請代金支払遅延等防止法 2 条",
                )
            ]
            if not re.search(r"60 ?日|六十日", text):
                findings.append(
                    ComplianceFinding(
                        code="subcontract_act_payment_terms",
                        title="下請法 60 日支払サイトの記載なし",
                        severity=ComplianceSeverity.BLOCK,
                        description="下請代金の支払期日が 60 日以内である旨の記載が必要です。",
                        citation="下請代金支払遅延等防止法 2 条の 2",
                        suggestion="支払期日条項を追記してください。",
                    )
                )
            return findings
        return []

    def _check_electronic_books_law(self, text: str) -> list[ComplianceFinding]:
        if re.search(r"電子(契約|帳簿|取引)|タイムスタンプ|電子署名", text):
            return []
        return [
            ComplianceFinding(
                code="electronic_books_act_hint",
                title="電子帳簿保存法対応の記載なし",
                severity=ComplianceSeverity.INFO,
                description=(
                    "電子契約・タイムスタンプ・電子署名等の言及がありません。"
                    "電子保存対象の場合は要件適合を確認してください。"
                ),
                citation="電子帳簿保存法",
            )
        ]

    def _check_personal_data(
        self, snapshot: ContractSnapshot, text: str
    ) -> list[ComplianceFinding]:
        if not snapshot.handles_personal_data and "個人情報" not in text:
            return []
        findings: list[ComplianceFinding] = []
        if not re.search(r"利用目的", text):
            findings.append(
                ComplianceFinding(
                    code="pipa_purpose_missing",
                    title="個人情報の利用目的記載なし",
                    severity=ComplianceSeverity.WARN,
                    description="個人情報を取扱うが利用目的の特定・通知に関する記載がありません。",
                    citation="個人情報保護法 17・21 条",
                )
            )
        if not re.search(r"第三者提供|委託先|再委託", text):
            findings.append(
                ComplianceFinding(
                    code="pipa_third_party_missing",
                    title="第三者提供・委託先管理条項なし",
                    severity=ComplianceSeverity.WARN,
                    description="個人情報の第三者提供・委託先管理に関する条項が見当たりません。",
                    citation="個人情報保護法 27・25 条",
                )
            )
        return findings

    def _check_disguised_contracting(
        self, snapshot: ContractSnapshot, text: str
    ) -> list[ComplianceFinding]:
        if snapshot.contract_type not in (ContractType.ITAKU, "委託"):
            return []
        risk_phrases = ("指揮命令", "始業時間", "終業時間", "勤怠管理")
        hits = [p for p in risk_phrases if p in text]
        if not hits:
            return []
        return [
            ComplianceFinding(
                code="disguised_subcontracting_risk",
                title="偽装請負の懸念",
                severity=ComplianceSeverity.WARN,
                description=(
                    "業務委託契約において指揮命令・勤怠管理に関する記載が"
                    f"見られます: {', '.join(hits)}"
                ),
                citation="労働者派遣法 / 職業安定法 / 厚労省告示 37 号",
                suggestion="独立性の高い委託形態へ条項を整理してください。",
                matched_keywords=hits,
            )
        ]

    def _check_public_work(
        self, snapshot: ContractSnapshot, text: str
    ) -> list[ComplianceFinding]:
        if not snapshot.is_public_work:
            return []
        findings: list[ComplianceFinding] = []
        if not re.search(r"施工体制台帳", text):
            findings.append(
                ComplianceFinding(
                    code="construction_law_24_8",
                    title="施工体制台帳の記載なし",
                    severity=ComplianceSeverity.WARN,
                    description="公共工事ですが施工体制台帳に関する言及がありません。",
                    citation="建設業法 24 条の 8",
                )
            )
        if not re.search(r"談合", text):
            findings.append(
                ComplianceFinding(
                    code="public_collusion_clause",
                    title="談合関連表明保証なし",
                    severity=ComplianceSeverity.WARN,
                    description="公共工事ですが談合関連の表明保証条項が見当たりません。",
                    citation="独占禁止法 3 条, 入札談合等関与行為防止法",
                )
            )
        return findings

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _coerce(self, contract: Any) -> ContractSnapshot:
        if isinstance(contract, ContractSnapshot):
            return contract
        # Duck-type translation from the ORM model (or a dict).
        if isinstance(contract, dict):
            return ContractSnapshot(
                text=str(contract.get("text", "")),
                contract_type=contract.get("contract_type", ContractType.OTHER),
                amount_jpy=contract.get("amount_jpy"),
                is_public_work=bool(contract.get("is_public_work", False)),
                counterparty_capital_jpy=contract.get("counterparty_capital_jpy"),
                our_capital_jpy=contract.get("our_capital_jpy"),
                handles_personal_data=bool(contract.get("handles_personal_data", False)),
                metadata=contract.get("metadata", {}),
            )
        return ContractSnapshot(
            text=getattr(contract, "text", "") or "",
            contract_type=getattr(contract, "contract_type", ContractType.OTHER),
            amount_jpy=getattr(contract, "amount_jpy", None),
            is_public_work=bool(getattr(contract, "is_public_work", False)),
            counterparty_capital_jpy=getattr(contract, "counterparty_capital_jpy", None),
            our_capital_jpy=getattr(contract, "our_capital_jpy", None),
            handles_personal_data=bool(getattr(contract, "handles_personal_data", False)),
        )
