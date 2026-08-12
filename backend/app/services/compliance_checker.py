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
from datetime import date
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

import structlog

from app.models.enums import ContractType

logger = structlog.get_logger(__name__)


class ComplianceSeverity(StrEnum):
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
    counterparty_employees: int | None = None
    our_employees: int | None = None
    handles_personal_data: bool = False
    # 発注日・受領日・検収日・支払日（取適法/建設業法の期限計算に使用）
    order_date: date | None = None
    receipt_date: date | None = None
    inspection_date: date | None = None
    payment_date: date | None = None
    # manufacturing | repair | information | service | transport | construction
    transaction_kind: str | None = None
    # 契約パッケージ文書（約款・特記仕様書・見積条件書等）: {文書種別: 本文}
    documents: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 取適法（中小受託取引適正化法）— 2026-01-01 施行
# ---------------------------------------------------------------------------

TORITEKI_EFFECTIVE_DATE = date(2026, 1, 1)

# 取引類型ごとの適用マトリクス（資本金 / 常時雇用従業員数）
# - 委託事業者（旧: 親事業者）: 資本金超 または 従業員数超 のいずれか
# - 中小受託事業者（旧: 下請事業者）: 資本金以下 または 従業員数以下 のいずれか
# 基準は公取委「取適法」公式ページ
# （https://www.jftc.go.jp/partnership_package/toritekihou.html）および
# 中小企業基本法の中小企業者判定を踏襲する。
_TORITEKI_MATRIX: dict[str, dict[str, Any]] = {
    "manufacturing": {"label": "製造委託", "capital": 300_000_000, "employees": 300},
    "repair": {"label": "修理委託", "capital": 300_000_000, "employees": 300},
    "information": {
        "label": "情報成果物作成委託",
        "capital": 300_000_000,
        "employees": 300,
    },
    "service": {"label": "役務提供委託", "capital": 100_000_000, "employees": 100},
    "transport": {"label": "特定運送委託", "capital": 100_000_000, "employees": 100},
}

# 取適法 4 条（旧 3 条）書面交付の法定記載事項
_TORITEKI_DOC_ITEMS: tuple[tuple[str, str], ...] = (
    ("給付内容", "給付内容"),
    ("給付期日", "給付期日"),
    ("給付場所", "給付場所"),
    ("検査", "検査期日"),
    ("支払期日", "支払期日"),
    ("支払方法", "支払方法"),
    ("金額", "代金額"),
)


_KEN_19_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("工事内容", "工事内容"),
    ("請負代金", "請負代金"),
    ("工期", "工期"),
    ("引渡", "引渡時期"),
    ("前金払|部分払|出来高払", "前金払・部分払・出来高払"),
    ("設計変更", "設計変更時の取扱"),
    ("第三者損害", "第三者損害負担"),
    ("不可抗力|天災", "天災等不可抗力"),
    ("価格|変動|スライド", "価格等変動による請負代金変更"),
    ("契約不適合|瑕疵担保", "契約不適合責任"),
    ("紛争解決", "紛争解決方法"),
)


# ---------------------------------------------------------------------------
# 労務費・材料費等の内訳（改正建設業法 / 国交省ガイドライン第 8 版）
# ---------------------------------------------------------------------------

_LABOR_BREAKDOWN_KEYWORDS: tuple[str, ...] = (
    "労務費",
    "材料費",
    "安全衛生経費",
    "法定福利費",
    "建退共",
)


class ComplianceChecker:
    """Apply a fixed rule set to a contract text."""

    async def check(self, contract: Any) -> list[ComplianceFinding]:
        snapshot = self._coerce(contract)
        text = snapshot.text or ""

        findings: list[ComplianceFinding] = []
        findings.extend(self._check_kenpou_19(snapshot, text))
        findings.extend(self._check_labor_cost(snapshot, text))
        findings.extend(self._check_antisocial(text))
        findings.extend(self._check_toritekihou(snapshot, text))
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
        if ct not in (ContractType.UKEOI, ContractType.KOUJI_UKEOI, ContractType.SHITAKE, "請負"):
            return []

        all_text = self._all_text(snapshot, text)
        missing: list[str] = []
        for pattern, label in _KEN_19_KEYWORDS:
            if not re.search(pattern, all_text):
                missing.append(label)

        findings: list[ComplianceFinding] = []
        if missing:
            findings.append(
                ComplianceFinding(
                    code="construction_law_19",
                    title="建設業法 19 条 必要記載事項の欠落",
                    severity=ComplianceSeverity.BLOCK,
                    description=(
                        "建設業法 19 条 1 項の必要記載事項のうち、"
                        f"次が見当たりません: {', '.join(missing)}"
                    ),
                    citation="建設業法 19 条 1 項（令和 7 年 12 月全面施行版）",
                    suggestion=(
                        "着工前に書面交付が必要です。社内雛形で補完してください。"
                        "約款・特記仕様書等の契約パッケージも横断確認済みです。"
                    ),
                    matched_keywords=missing,
                )
            )

        # 金額の内容妥当性
        extracted = self._extract_max_amount(all_text)
        if snapshot.amount_jpy is not None and extracted is None:
            findings.append(
                ComplianceFinding(
                    code="construction_law_19_amount_unverifiable",
                    title="請負代金額の記載を確認できない",
                    severity=ComplianceSeverity.WARN,
                    description=(
                        f"台帳上の契約金額 {snapshot.amount_jpy:,} 円に対し、"
                        "契約書面上に金額記載を確認できません。"
                    ),
                    citation="建設業法 19 条 1 項 2 号",
                    suggestion="契約書または内訳書の金額記載を確認してください。",
                )
            )
        elif snapshot.amount_jpy is not None and extracted is not None:
            deviation = abs(extracted - snapshot.amount_jpy) / max(snapshot.amount_jpy, 1)
            if deviation > 0.2:
                findings.append(
                    ComplianceFinding(
                        code="construction_law_19_amount_mismatch",
                        title="台帳金額と書面金額の乖離",
                        severity=ComplianceSeverity.WARN,
                        description=(
                            f"台帳金額 {snapshot.amount_jpy:,} 円に対し、"
                            f"書面に確認できる金額 {extracted:,} 円で 20% 超の乖離があります。"
                        ),
                        citation="建設業法 19 条 1 項 2 号",
                        suggestion="金額訂正か台帳更新かを確認してください。",
                    )
                )

        # 日付の内容妥当性（着工 < 完成）
        start, end = self._extract_start_end_dates(all_text)
        if start is not None and end is not None and start > end:
            findings.append(
                ComplianceFinding(
                    code="construction_law_19_date_order",
                    title="工期の日付順序が不自然",
                    severity=ComplianceSeverity.WARN,
                    description=(
                        f"着工/着手時期（{start.isoformat()}）が"
                        f"完成/引渡時期（{end.isoformat()}）より後になっています。"
                    ),
                    citation="建設業法 19 条 1 項 3・4 号",
                    suggestion="工期条項の日付を確認してください。",
                )
            )
        elif "工期" in all_text and start is None:
            findings.append(
                ComplianceFinding(
                    code="construction_law_19_dates_missing",
                    title="工期の具体的日付なし",
                    severity=ComplianceSeverity.INFO,
                    description="工期に関する言及はありますが、日付の記載を確認できません。",
                    citation="建設業法 19 条 1 項 3 号",
                    suggestion="着工時期・完成時期を具体的な日付で明記してください。",
                )
            )

        return findings

    def _check_labor_cost(
        self, snapshot: ContractSnapshot, text: str
    ) -> list[ComplianceFinding]:
        """改正建設業法（2025-12 全面施行）の労務費等ルール."""
        ct = snapshot.contract_type
        if ct not in (ContractType.UKEOI, ContractType.KOUJI_UKEOI, ContractType.SHITAKE, "請負"):
            return []

        all_text = self._all_text(snapshot, text)
        findings: list[ComplianceFinding] = []

        missing_breakdown = [k for k in _LABOR_BREAKDOWN_KEYWORDS if k not in all_text]
        if missing_breakdown:
            findings.append(
                ComplianceFinding(
                    code="construction_law_labor_breakdown",
                    title="労務費等の内訳確認が不足",
                    severity=ComplianceSeverity.WARN,
                    description=(
                        "労務費・材料費・安全衛生経費・法定福利費・建退共掛金の"
                        f"内訳に関する記載が見当たりません: {', '.join(missing_breakdown)}"
                    ),
                    citation=(
                        "建設業法 19 条 / 発注者・受注者間における建設業法令遵守ガイドライン"
                        "（国交省 第 8 版）"
                    ),
                    suggestion="見積条件書・内訳書で適正な労務費等が確保されているか確認してください。",
                    matched_keywords=missing_breakdown,
                )
            )

        if re.search(r"著しく低い(見積|価格)|低入札|ダンピング", all_text):
            findings.append(
                ComplianceFinding(
                    code="construction_law_abnormally_low_bid",
                    title="著しく低い見積り・価格の記載",
                    severity=ComplianceSeverity.WARN,
                    description=(
                        "著しく低い見積り・低入札・ダンピングに関する記載があります。"
                        "適正な工事価格・労務費の確保を確認してください。"
                    ),
                    citation="建設業法 19 条 / 公共工事の品質確保の促進に関する法律（品確法）",
                    suggestion="内訳書と労務費基準を照合してください。",
                )
            )

        if re.search(r"著しく短い工期|短すぎる工期|無理な工期", all_text):
            findings.append(
                ComplianceFinding(
                    code="construction_law_unreasonably_short_period",
                    title="著しく短い工期の記載",
                    severity=ComplianceSeverity.WARN,
                    description="著しく短い・無理な工期に関する記載があります。",
                    citation="建設業法 19 条 / 発注者・受注者間における建設業法令遵守ガイドライン",
                    suggestion="施工計画と実工程の整合を確認してください。",
                )
            )

        # 資材高騰・供給不足・労務不足の契約前通知
        if re.search(r"資材|供給不足|労務不足|高騰", all_text) and not re.search(
            r"通知|申出", all_text
        ):
            findings.append(
                ComplianceFinding(
                    code="construction_law_pre_notification",
                    title="価格・工期に影響する事象の事前通知条項なし",
                    severity=ComplianceSeverity.WARN,
                    description=(
                        "資材高騰・供給不足・労務不足等に言及がありますが、"
                        "発注者への事前通知・申出に関する条項が見当たりません。"
                    ),
                    citation="発注者・受注者間における建設業法令遵守ガイドライン（国交省 第 8 版）",
                    suggestion="契約前通知条項と根拠資料保存フローを整備してください。",
                )
            )

        # スライド条項 / 価格変更協議
        if not re.search(r"スライド|価格変更協議|価格等変動", all_text):
            findings.append(
                ComplianceFinding(
                    code="construction_law_price_revision_clause",
                    title="価格変更協議（スライド）条項なし",
                    severity=(
                        ComplianceSeverity.WARN
                        if snapshot.is_public_work
                        else ComplianceSeverity.INFO
                    ),
                    description=(
                        "資材価格等の変動に伴う請負代金の変更（スライド）に関する"
                        "条項が見当たりません。"
                    ),
                    citation="建設業法 19 条 1 項 / 公共工事標準請負約款 25 条ほか",
                    suggestion="スライド条項と変更額算定方法を定めてください。",
                )
            )

        return findings

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
        """Backward-compatible wrapper — delegates to the 取適法 checker."""
        return self._check_toritekihou(snapshot, text)

    def _check_toritekihou(
        self, snapshot: ContractSnapshot, text: str
    ) -> list[ComplianceFinding]:
        """取適法（2026-01-01 施行）と旧下請法の新旧切替を含む適用判定."""
        applicable, kind_label, reason = self._toriteki_applicability(snapshot)
        if not applicable:
            if self._has_toriteki_profile(snapshot):
                return [
                    ComplianceFinding(
                        code="toritekihou_transaction_kind_unknown",
                        title="取引類型の未設定（取適法適用判定不能）",
                        severity=ComplianceSeverity.INFO,
                        description=(
                            "資本金・従業員数から取適法（旧下請法）の適用対象となり得ますが、"
                            "取引類型（製造委託・修理委託・情報成果物作成委託・役務提供委託・"
                            "特定運送委託）が未設定のため適用判定できません。"
                        ),
                        citation=(
                            "取適法 2 条 — "
                            "https://www.jftc.go.jp/partnership_package/toritekihou.html"
                        ),
                        suggestion="取引類型を設定して再判定してください。",
                    )
                ]
            return []

        findings: list[ComplianceFinding] = []
        law_version = self._law_version(snapshot.order_date)

        if law_version == "toritekihou":
            findings.append(
                ComplianceFinding(
                    code="toritekihou_applies",
                    title="取適法（中小受託取引適正化法）適用の可能性",
                    severity=ComplianceSeverity.WARN,
                    description=(
                        f"{kind_label}に該当し、資本金・従業員数基準から"
                        "取適法の委託事業者/中小受託事業者関係に該当する可能性があります。"
                        f"（判定根拠: {reason}）"
                    ),
                    citation=(
                        "中小受託取引適正化法（取適法）— "
                        "https://www.jftc.go.jp/partnership_package/toritekihou.html"
                    ),
                )
            )
        else:
            findings.append(
                ComplianceFinding(
                    code="subcontract_act_applies",
                    title="下請法適用の可能性（2026-01-01 以降は取適法）",
                    severity=ComplianceSeverity.WARN,
                    description=(
                        f"{kind_label}に該当し、資本金区分から下請法が適用される可能性があります。"
                        "2026-01-01 以降発注分は取適法（中小受託取引適正化法）に置き換わります。"
                        f"（判定根拠: {reason}）"
                    ),
                    citation="下請代金支払遅延等防止法 2 条 / 中小受託取引適正化法（取適法）",
                )
            )

        if law_version == "unknown":
            findings.append(
                ComplianceFinding(
                    code="toritekihou_order_date_unknown",
                    title="発注日の未設定（新旧法切替の要確認）",
                    severity=ComplianceSeverity.WARN,
                    description=(
                        "発注日が未設定のため、2026-01-01 施行の取適法と"
                        "旧下請法のどちらを適用するか判定できません。"
                    ),
                    citation="取適法 附則（2026-01-01 施行）",
                    suggestion="発注日を設定して再判定してください。",
                )
            )

        findings.extend(self._toriteki_payment_checks(snapshot, text, law_version))
        findings.extend(self._toriteki_prohibited_means(snapshot, text, law_version))
        findings.extend(self._toriteki_document_checks(text, law_version))

        if snapshot.transaction_kind == "transport":
            findings.append(
                ComplianceFinding(
                    code="toritekihou_specific_transport",
                    title="特定運送委託の取扱確認",
                    severity=ComplianceSeverity.INFO,
                    description=(
                        "特定運送委託（物品運送委託）に該当します。"
                        "取適法の書面交付・支払規制の適用を確認してください。"
                    ),
                    citation=(
                        "取適法（特定運送委託）— "
                        "https://www.jftc.go.jp/partnership_package/toritekihou.html"
                    ),
                )
            )

        if not re.search(r"取引記録|2 ?年|二年", text):
            findings.append(
                ComplianceFinding(
                    code="toritekihou_record_retention",
                    title="取引記録の保存言及なし",
                    severity=ComplianceSeverity.INFO,
                    description="取引記録の作成・2 年間保存に関する言及がありません。",
                    citation="取適法 7 条 / 下請代金支払遅延等防止法 5 条",
                    suggestion="取引記録の作成・保存フローを整備してください。",
                )
            )

        return findings

    def _toriteki_payment_checks(
        self,
        snapshot: ContractSnapshot,
        text: str,
        law_version: str,
    ) -> list[ComplianceFinding]:
        findings: list[ComplianceFinding] = []
        payment_ok = bool(re.search(r"60 ?日|六十日", text))

        if not payment_ok:
            code = (
                "toritekihou_payment_terms"
                if law_version == "toritekihou"
                else "subcontract_act_payment_terms"
            )
            findings.append(
                ComplianceFinding(
                    code=code,
                    title="代金支払期日（受領後 60 日以内）の記載なし",
                    severity=ComplianceSeverity.BLOCK,
                    description=(
                        "代金の支払期日が受領日（納品日）から 60 日以内である旨の"
                        "記載が必要です。"
                    ),
                    citation=(
                        "取適法 3 条 1 項"
                        if law_version == "toritekihou"
                        else "下請代金支払遅延等防止法 2 条の 2"
                    ),
                    suggestion="支払期日条項を追記してください。",
                )
            )

        receipt = self._as_date(snapshot.receipt_date)
        payment = self._as_date(snapshot.payment_date)
        if receipt is not None and payment is not None and (payment - receipt).days > 60:
            findings.append(
                ComplianceFinding(
                    code="toritekihou_payment_late",
                    title="支払期日が受領後 60 日を超えている",
                    severity=ComplianceSeverity.BLOCK,
                    description=(
                        f"受領日 {receipt.isoformat()} から支払日 "
                        f"{payment.isoformat()} まで "
                        f"{(payment - receipt).days} 日あり、"
                        "60 日以内という法定支払期日を超えています。"
                    ),
                    citation="取適法 3 条 1 項（受領日から 60 日以内）",
                    suggestion="支払サイトの短縮または分割払いの見直しを検討してください。",
                )
            )

        return findings

    def _toriteki_prohibited_means(
        self,
        snapshot: ContractSnapshot,
        text: str,
        law_version: str,
    ) -> list[ComplianceFinding]:
        findings: list[ComplianceFinding] = []

        if re.search(r"手形", text):
            findings.append(
                ComplianceFinding(
                    code="toritekihou_promissory_note",
                    title="手形払いの記載（2026 年以降は禁止）",
                    severity=ComplianceSeverity.BLOCK,
                    description=(
                        "手形による代金支払いの記載があります。2026-01-01 以降に発注される"
                        "取適法対象取引では手形払いは一律禁止です。"
                    ),
                    citation=(
                        "取適法（手形払等の禁止）— "
                        "https://www.jftc.go.jp/partnership_package/toritekihou.html"
                    ),
                    suggestion="現金・振込払いに変更してください。",
                )
            )

        if re.search(r"電子記録債券|電子記録債権|ファクタリング", text):
            findings.append(
                ComplianceFinding(
                    code="toritekihou_ecb_factoring",
                    title="電子記録債権・ファクタリング条件の確認",
                    severity=ComplianceSeverity.WARN,
                    description=(
                        "電子記録債権・ファクタリングを使用する記載があります。"
                        "支払期日までに代金満額相当の現金を得ることが困難なものは"
                        "支払遅延（禁止行為）に該当します。"
                    ),
                    citation=(
                        "取適法（手形払等の禁止）— "
                        "https://www.jftc.go.jp/partnership_package/toritekihou.html"
                    ),
                    suggestion="受領日から 60 日以内に現金化できる条件であるか確認してください。",
                )
            )

        if re.search(
            r"一方的|協議に応じない|甲が(一方的に)?定める|乙の(異議|意見)を(聞か|聴か)",
            text,
        ):
            findings.append(
                ComplianceFinding(
                    code="toritekihou_unilateral_pricing",
                    title="一方的な代金決定の記載",
                    severity=ComplianceSeverity.BLOCK,
                    description=(
                        "代金を一方的に決定・変更する、または協議に応じない趣旨の"
                        "記載があります。取適法では協議を適切に行わない一方的な"
                        "代金決定は禁止されています。"
                    ),
                    citation="取適法（協議を適切に行わない一方的な代金決定の禁止）",
                    suggestion="価格協議・回答・説明の手続条項に修正してください。",
                )
            )

        return findings

    def _toriteki_document_checks(self, text: str, law_version: str) -> list[ComplianceFinding]:
        missing: list[str] = []
        for pattern, label in _TORITEKI_DOC_ITEMS:
            if not re.search(pattern, text):
                missing.append(label)
        if not missing:
            return []
        return [
            ComplianceFinding(
                code=(
                    "toritekihou_written_delivery"
                    if law_version == "toritekihou"
                    else "subcontract_act_written_delivery"
                ),
                title="取適法（旧下請法）書面交付事項の欠落",
                severity=ComplianceSeverity.WARN,
                description=(
                    "書面交付（電磁的方法による明示を含む）が必要な事項のうち、"
                    f"次が見当たりません: {', '.join(missing)}"
                ),
                citation=(
                    "取適法 4 条 1 項"
                    if law_version == "toritekihou"
                    else "下請代金支払遅延等防止法 3 条 1 項"
                ),
                suggestion="発注後直ちに書面（または電磁的記録）で明示してください。",
                matched_keywords=missing,
            )
        ]

    def _toriteki_applicability(
        self, snapshot: ContractSnapshot
    ) -> tuple[bool, str, str]:
        """Return (applicable, transaction_label, reason).

        資本金または従業員数が委託事業者基準を満たし、かつ相手方が
        中小受託事業者基準（いずれか）を満たす場合に適用となる。
        """
        kind = snapshot.transaction_kind or self._infer_transaction_kind(snapshot)
        if kind is None:
            return False, "不明", ""

        row = _TORITEKI_MATRIX.get(kind)
        if row is None:
            return False, kind, ""
        label = str(row["label"])
        cap = int(row["capital"])
        emp = int(row["employees"])

        ours_big = (snapshot.our_capital_jpy or 0) > cap
        theirs_big = (snapshot.counterparty_capital_jpy or 0) > cap
        ours_many = (snapshot.our_employees or 0) > emp
        theirs_many = (snapshot.counterparty_employees or 0) > emp

        # 相手方の規模が不明（資本金・従業員とも未設定）なら適用判定できない
        if (
            snapshot.counterparty_capital_jpy is None
            and snapshot.counterparty_employees is None
        ):
            return False, label, ""
        if not (ours_big or ours_many):
            return False, label, ""
        # 中小受託事業者 = 資本金以下 または 従業員以下（中小企業基本法の OR 判定）
        if not (not theirs_big or not theirs_many):
            return False, label, ""

        reasons: list[str] = []
        if ours_big:
            reasons.append(f"委託事業者側 資本金 {snapshot.our_capital_jpy:,} 円 > {cap:,} 円")
        if ours_many:
            reasons.append(f"委託事業者側 従業員 {snapshot.our_employees} 人 > {emp} 人")
        if snapshot.counterparty_capital_jpy is not None:
            reasons.append(
                f"中小受託事業者側 資本金 {snapshot.counterparty_capital_jpy:,} 円 <= {cap:,} 円"
            )
        if snapshot.counterparty_employees is not None:
            reasons.append(
                f"中小受託事業者側 従業員 {snapshot.counterparty_employees} 人 <= {emp} 人"
            )
        return True, label, "; ".join(reasons)

    @staticmethod
    def _has_toriteki_profile(snapshot: ContractSnapshot) -> bool:
        """資本金/従業員数だけで取適法対象となり得るか（取引類型不明時用）."""
        min_cap = min(int(row["capital"]) for row in _TORITEKI_MATRIX.values())
        min_emp = min(int(row["employees"]) for row in _TORITEKI_MATRIX.values())
        return (snapshot.our_capital_jpy or 0) > min_cap or (
            snapshot.our_employees or 0
        ) > min_emp

    @staticmethod
    def _infer_transaction_kind(snapshot: ContractSnapshot) -> str | None:
        ct = snapshot.contract_type
        if ct in (ContractType.UKEOI, ContractType.KOUJI_UKEOI, ContractType.SHITAKE, "請負"):
            return "construction"
        if ct in (ContractType.ITAKU, ContractType.GYOMU_ITAKU, "委託", "業務委託"):
            return "service"
        return None

    @staticmethod
    def _law_version(order_date: date | str | None) -> str:
        if order_date is None:
            return "unknown"
        if isinstance(order_date, str):
            try:
                order_date = date.fromisoformat(order_date)
            except ValueError:
                return "unknown"
        return "toritekihou" if order_date >= TORITEKI_EFFECTIVE_DATE else "subcontract_act"

    @staticmethod
    def _as_date(value: date | str | None) -> date | None:
        if value is None or isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value))
        except ValueError:
            return None

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

    @staticmethod
    def _all_text(snapshot: ContractSnapshot, text: str) -> str:
        """契約書本体 + 契約パッケージ文書（約款・特記仕様書等）の横断テキスト."""
        parts = [text]
        for doc_text in (snapshot.documents or {}).values():
            if doc_text:
                parts.append(str(doc_text))
        return "\n".join(parts)

    @staticmethod
    def _extract_max_amount(text: str) -> int | None:
        """Extract the largest monetary value from text (円/万円/億円)."""
        values: list[int] = []
        for unit, mult in (("億", 100_000_000), ("万", 10_000), ("", 1)):
            for m in re.finditer(rf"([\d,]+(?:\.[\d]+)?)\s*{unit}円", text):
                try:
                    values.append(int(float(m.group(1).replace(",", "")) * mult))
                except ValueError:
                    continue
        return max(values) if values else None

    @staticmethod
    def _extract_start_end_dates(text: str) -> tuple[date | None, date | None]:
        """Extract (着工/着手時期, 完成/引渡/納期) from the text."""

        def parse(section: str) -> date | None:
            m = re.search(r"(\d{4})[年/.](\d{1,2})[月/.](\d{1,2})日?", section)
            if not m:
                return None
            try:
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                return None

        start = None
        for pattern in (r"着工.{0,40}", r"着手.{0,40}", r"開始.{0,40}"):
            m = re.search(pattern, text)
            if m:
                start = parse(m.group(0))
                if start is not None:
                    break
        end = None
        for pattern in (r"完成.{0,40}", r"引渡.{0,40}", r"納期.{0,40}"):
            m = re.search(pattern, text)
            if m:
                end = parse(m.group(0))
                if end is not None:
                    break
        return start, end

    def _coerce(self, contract: Any) -> ContractSnapshot:
        if isinstance(contract, ContractSnapshot):
            return contract

        def _attr(name: str) -> Any:
            """MagicMock 等のテストダブルからは None を返す安全な getattr。"""
            try:
                from unittest.mock import Mock

                value = getattr(contract, name, None)
                return None if isinstance(value, Mock) else value
            except Exception:  # pragma: no cover - defensive
                return None

        # Duck-type translation from the ORM model (or a dict).
        if isinstance(contract, dict):
            return ContractSnapshot(
                text=str(contract.get("text", "")),
                contract_type=contract.get("contract_type", ContractType.OTHER),
                amount_jpy=contract.get("amount_jpy"),
                is_public_work=bool(contract.get("is_public_work", False)),
                counterparty_capital_jpy=contract.get("counterparty_capital_jpy"),
                our_capital_jpy=contract.get("our_capital_jpy"),
                counterparty_employees=contract.get("counterparty_employees"),
                our_employees=contract.get("our_employees"),
                handles_personal_data=bool(contract.get("handles_personal_data", False)),
                order_date=self._as_date(contract.get("order_date")),
                receipt_date=self._as_date(contract.get("receipt_date")),
                inspection_date=self._as_date(contract.get("inspection_date")),
                payment_date=self._as_date(contract.get("payment_date")),
                transaction_kind=contract.get("transaction_kind"),
                documents=contract.get("documents", {}),
                metadata=contract.get("metadata", {}),
            )
        return ContractSnapshot(
            text=_attr("text") or "",
            contract_type=_attr("contract_type") or ContractType.OTHER,
            amount_jpy=_attr("amount_jpy"),
            is_public_work=bool(_attr("is_public_work") or False),
            counterparty_capital_jpy=_attr("counterparty_capital_jpy"),
            our_capital_jpy=_attr("our_capital_jpy"),
            counterparty_employees=_attr("counterparty_employees"),
            our_employees=_attr("our_employees"),
            handles_personal_data=bool(_attr("handles_personal_data") or False),
            order_date=self._as_date(_attr("order_date")),
            receipt_date=self._as_date(_attr("receipt_date")),
            inspection_date=self._as_date(_attr("inspection_date")),
            payment_date=self._as_date(_attr("payment_date")),
            transaction_kind=_attr("transaction_kind"),
            documents=_attr("documents") or {},
        )
