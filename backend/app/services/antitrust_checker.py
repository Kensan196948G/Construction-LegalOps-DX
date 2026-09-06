"""独禁法・入札談合コンプライアンス — 決定論的ルールベースチェッカー（Issue #122）.

``app.services.compliance_checker.ComplianceChecker`` と同じ設計思想を踏襲する。
AI には最終法的判断をさせず、キーワード・入力フラグから機械的に判定した
:class:`AntitrustFinding` のリストを返す。呼び出し側（``antitrust_service``）が
これを ``antitrust_checks.findings`` へ永続化する。

対応する 5 種類のチェック（``AntitrustCheckType``）:

* ``general``        — #113 独禁法チェック（契約・取引文面の一般スクリーニング）
* ``bid_rigging``     — #114 入札談合リスクチェック
* ``price_exchange``  — #117 価格情報交換禁止チェック
* ``jv_formation``    — #118 JV 形成時競争法チェック
* ``joint_research``  — #119 競合との共同研究チェック
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import structlog

from app.models.enums import AntitrustCheckSeverity, AntitrustCheckType

logger = structlog.get_logger(__name__)

_SEVERITY_ORDER: dict[str, int] = {
    AntitrustCheckSeverity.INFO.value: 0,
    AntitrustCheckSeverity.WARN.value: 1,
    AntitrustCheckSeverity.BLOCK.value: 2,
}


@dataclass(slots=True)
class AntitrustFinding:
    """A single rule result (mirrors ``ComplianceFinding``)."""

    code: str
    title: str
    severity: AntitrustCheckSeverity
    description: str
    citation: str
    suggestion: str | None = None
    matched_keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "title": self.title,
            "severity": str(self.severity),
            "description": self.description,
            "citation": self.citation,
            "suggestion": self.suggestion,
            "matched_keywords": self.matched_keywords,
        }


def overall_severity(findings: list[AntitrustFinding]) -> str:
    """Return the worst severity among ``findings`` (``info`` when empty)."""
    if not findings:
        return AntitrustCheckSeverity.INFO.value
    return max((str(f.severity) for f in findings), key=lambda s: _SEVERITY_ORDER.get(s, 0))


# ---------------------------------------------------------------------------
# #113 独禁法チェック（一般スクリーニング）
# ---------------------------------------------------------------------------

_GENERAL_RED_FLAGS: tuple[tuple[str, str], ...] = (
    (r"価格を合わせ|価格の足並み|価格カルテル", "価格協定を示唆する表現"),
    (r"受注(調整|割当)|案件を融通", "受注調整を示唆する表現"),
    (r"市場(分割|割当)|顧客(割当|分割)|テリトリー(制|協定)", "市場・顧客分割を示唆する表現"),
    (r"入札(前|情報).{0,10}(共有|交換|相談)", "入札前の情報共有を示唆する表現"),
    (r"談合", "談合を示唆する直接的な表現"),
    (r"生産(調整|制限)|供給(調整|制限)", "生産・供給調整を示唆する表現"),
)


def check_general(text: str) -> list[AntitrustFinding]:
    """#113 契約書・取引文面の独禁法一般スクリーニング（キーワードベース）."""
    findings: list[AntitrustFinding] = []
    all_text = text or ""
    hits: list[str] = []
    for pattern, label in _GENERAL_RED_FLAGS:
        if re.search(pattern, all_text):
            hits.append(label)
    if hits:
        findings.append(
            AntitrustFinding(
                code="antitrust_general_red_flag",
                title="独占禁止法上のレッドフラッグ表現を検出",
                severity=AntitrustCheckSeverity.BLOCK,
                description=(
                    "不当な取引制限・私的独占等に該当し得る表現を検出しました: "
                    f"{', '.join(hits)}。参考情報であり、最終判断は法務担当者・"
                    "顧問弁護士が行ってください。"
                ),
                citation=(
                    "独占禁止法 3 条（私的独占・不当な取引制限の禁止）/ 8 条（事業者団体規制）"
                ),
                suggestion=(
                    "該当箇所の背景・意図を確認し、法務・コンプライアンス部門へ相談してください。"
                ),
                matched_keywords=hits,
            )
        )
    else:
        findings.append(
            AntitrustFinding(
                code="antitrust_general_no_flag",
                title="レッドフラッグ表現は検出されませんでした",
                severity=AntitrustCheckSeverity.INFO,
                description="キーワードベースの機械チェックでは懸念表現が見つかりませんでした。",
                citation="独占禁止法 3 条 / 8 条",
            )
        )
    return findings


# ---------------------------------------------------------------------------
# #114 入札談合リスクチェック
# ---------------------------------------------------------------------------


def check_bid_rigging(context: dict[str, Any]) -> list[AntitrustFinding]:
    """#114 入札談合リスクチェック.

    ``context`` keys: ``is_public_bid`` (bool), ``contacted_competitors`` (bool),
    ``pre_bid_price_shared`` (bool), ``text`` (str, optional free text).
    """
    findings: list[AntitrustFinding] = []
    text = str(context.get("text") or "")
    is_public_bid = bool(context.get("is_public_bid", False))
    contacted_competitors = bool(context.get("contacted_competitors", False))
    pre_bid_price_shared = bool(context.get("pre_bid_price_shared", False))

    if contacted_competitors and is_public_bid:
        findings.append(
            AntitrustFinding(
                code="bid_rigging_competitor_contact",
                title="入札前の競合他社接触（談合リスク）",
                severity=AntitrustCheckSeverity.BLOCK,
                description=(
                    "公共・民間入札に関連して競合他社との接触があったと申告されています。"
                    "入札談合等関与行為防止法・独占禁止法上のリスクが高い可能性があります。"
                ),
                citation=(
                    "独占禁止法 3 条（不当な取引制限）/ "
                    "入札談合等関与行為の排除及び防止に関する法律"
                ),
                suggestion="接触の経緯・内容を記録し、法務・コンプライアンス部門へ即時相談してください。",
            )
        )
    if pre_bid_price_shared:
        findings.append(
            AntitrustFinding(
                code="bid_rigging_price_shared",
                title="入札前の価格情報共有",
                severity=AntitrustCheckSeverity.BLOCK,
                description="入札前に価格情報を競合と共有したと申告されています。",
                citation="独占禁止法 3 条（不当な取引制限） / 2 条 6 項",
                suggestion="価格情報交換の事実関係を保全し、直ちに法務部門へ報告してください。",
            )
        )
    if re.search(r"談合|入札.{0,10}調整|受注予定者", text):
        findings.append(
            AntitrustFinding(
                code="bid_rigging_text_flag",
                title="談合を示唆する記載を検出",
                severity=AntitrustCheckSeverity.BLOCK,
                description="自由記述欄に談合・受注調整を示唆する表現が含まれています。",
                citation="独占禁止法 3 条 / 入札談合等関与行為防止法",
            )
        )
    if not findings:
        findings.append(
            AntitrustFinding(
                code="bid_rigging_none",
                title="入札談合リスクは検出されませんでした",
                severity=AntitrustCheckSeverity.INFO,
                description="申告内容から機械的に検出されるリスク要因はありません。",
                citation="独占禁止法 3 条 / 入札談合等関与行為防止法",
            )
        )
    return findings


# ---------------------------------------------------------------------------
# #117 価格情報交換禁止チェック
# ---------------------------------------------------------------------------

_SENSITIVE_TOPICS: tuple[str, ...] = (
    "price",
    "cost",
    "output",
    "capacity",
    "bid_price",
    "customer_allocation",
    "territory",
    "wage",
)

_SENSITIVE_TOPIC_LABELS: dict[str, str] = {
    "price": "価格",
    "cost": "コスト・原価",
    "output": "生産・供給量",
    "capacity": "生産能力",
    "bid_price": "入札価格",
    "customer_allocation": "顧客配分",
    "territory": "販売地域",
    "wage": "賃金水準",
}


def check_price_exchange(context: dict[str, Any]) -> list[AntitrustFinding]:
    """#117 競合との価格情報交換禁止チェック.

    ``context`` keys: ``counterparty_is_competitor`` (bool),
    ``exchanged_topics`` (list[str], values from ``_SENSITIVE_TOPICS``),
    ``has_legitimate_business_reason`` (bool).
    """
    findings: list[AntitrustFinding] = []
    is_competitor = bool(context.get("counterparty_is_competitor", False))
    topics = [t for t in (context.get("exchanged_topics") or []) if t in _SENSITIVE_TOPICS]
    has_reason = bool(context.get("has_legitimate_business_reason", False))

    if is_competitor and topics:
        labels = [_SENSITIVE_TOPIC_LABELS.get(t, t) for t in topics]
        findings.append(
            AntitrustFinding(
                code="price_exchange_with_competitor",
                title="競合他社との機微情報交換",
                severity=AntitrustCheckSeverity.BLOCK,
                description=(
                    f"競合他社との間で {', '.join(labels)} に関する情報交換があったと"
                    "申告されています。カルテル（不当な取引制限）の外形的事実に該当し"
                    "得るため、直ちに情報交換を停止し法務部門へ相談してください。"
                ),
                citation="独占禁止法 2 条 6 項・3 条（不当な取引制限）",
                suggestion="情報交換の経緯・参加者・内容を記録し保全してください。",
                matched_keywords=labels,
            )
        )
    elif is_competitor and not has_reason:
        findings.append(
            AntitrustFinding(
                code="price_exchange_no_business_reason",
                title="正当な事業目的が確認できない競合との接触",
                severity=AntitrustCheckSeverity.WARN,
                description=(
                    "競合他社との接触について正当な事業目的（共同購買・業界団体活動等）が"
                    "明記されていません。目的・議事録を整備してください。"
                ),
                citation="独占禁止法 3 条 / 8 条（事業者団体規制）",
            )
        )
    else:
        findings.append(
            AntitrustFinding(
                code="price_exchange_none",
                title="機微情報交換は検出されませんでした",
                severity=AntitrustCheckSeverity.INFO,
                description="申告内容から機械的に検出される機微情報交換はありません。",
                citation="独占禁止法 2 条 6 項・3 条",
            )
        )
    return findings


# ---------------------------------------------------------------------------
# #118 JV 形成時競争法チェック
# ---------------------------------------------------------------------------


def check_jv_formation(context: dict[str, Any]) -> list[AntitrustFinding]:
    """#118 JV 形成時競争法チェック.

    ``context`` keys: ``is_competitor_jv`` (bool), ``scope_covers_pricing`` (bool),
    ``combined_market_share_pct`` (float | None).
    """
    findings: list[AntitrustFinding] = []
    is_competitor_jv = bool(context.get("is_competitor_jv", False))
    scope_covers_pricing = bool(context.get("scope_covers_pricing", False))
    share = context.get("combined_market_share_pct")

    if is_competitor_jv and scope_covers_pricing:
        findings.append(
            AntitrustFinding(
                code="jv_formation_price_fixing_scope",
                title="競合企業間 JV が価格決定を含む",
                severity=AntitrustCheckSeverity.BLOCK,
                description=(
                    "競合関係にある企業間の JV で、価格決定・出荷数量調整を業務範囲に"
                    "含むと申告されています。共同の価格決定は不当な取引制限に該当し得ます。"
                ),
                citation=(
                    "独占禁止法 3 条 / 公正取引委員会「共同研究開発に関する独占禁止法上の"
                    "指針」（類推適用）"
                ),
                suggestion="価格決定・数量調整を JV の業務範囲から除外できないか検討してください。",
            )
        )
    elif is_competitor_jv:
        findings.append(
            AntitrustFinding(
                code="jv_formation_competitor_caution",
                title="競合関係にある企業間の JV（要事前確認）",
                severity=AntitrustCheckSeverity.WARN,
                description=(
                    "競合関係にある企業間の JV です。情報交換範囲の限定（チャイニーズ"
                    "ウォール）や独立した営業活動の維持を確認してください。"
                ),
                citation="独占禁止法 3 条・8 条",
            )
        )
    if share is not None:
        try:
            share_value = float(share)
        except (TypeError, ValueError):
            share_value = None
        if share_value is not None and share_value >= 25.0:
            findings.append(
                AntitrustFinding(
                    code="jv_formation_market_share_notice",
                    title="結合後の市場シェアが一定水準以上",
                    severity=AntitrustCheckSeverity.WARN,
                    description=(
                        f"JV 構成員合算の市場シェアが概算 {share_value:.1f}% です。"
                        "公正取引委員会への事前相談・企業結合届出の要否を確認してください。"
                        "（本判定は参考情報であり、正式な市場画定・シェア算定ではありません）"
                    ),
                    citation="独占禁止法 10 条・15 条（企業結合規制）/ 企業結合ガイドライン",
                    suggestion="正式な市場画定は法務部門・独占禁止法専門家に依頼してください。",
                )
            )
    if not findings:
        findings.append(
            AntitrustFinding(
                code="jv_formation_none",
                title="JV 形成時の競争法リスクは検出されませんでした",
                severity=AntitrustCheckSeverity.INFO,
                description="申告内容から機械的に検出されるリスク要因はありません。",
                citation="独占禁止法 3 条・10 条",
            )
        )
    return findings


# ---------------------------------------------------------------------------
# #119 競合との共同研究チェック
# ---------------------------------------------------------------------------


def check_joint_research(context: dict[str, Any]) -> list[AntitrustFinding]:
    """#119 競合との共同研究開発における競争法チェック.

    ``context`` keys: ``with_competitor`` (bool),
    ``covers_pricing_or_output`` (bool), ``covers_customer_allocation`` (bool).
    """
    findings: list[AntitrustFinding] = []
    with_competitor = bool(context.get("with_competitor", False))
    covers_pricing_or_output = bool(context.get("covers_pricing_or_output", False))
    covers_customer_allocation = bool(context.get("covers_customer_allocation", False))

    if with_competitor and (covers_pricing_or_output or covers_customer_allocation):
        findings.append(
            AntitrustFinding(
                code="joint_research_scope_violation",
                title="競合との共同研究が価格・数量・顧客配分に及ぶ",
                severity=AntitrustCheckSeverity.BLOCK,
                description=(
                    "競合他社との共同研究開発の範囲が、価格・生産数量の調整または"
                    "顧客配分に及ぶと申告されています。研究開発の名目に留まらない"
                    "不当な取引制限に該当し得ます。"
                ),
                citation=(
                    "公正取引委員会「共同研究開発に関する独占禁止法上の指針」/ 独占禁止法 3 条"
                ),
                suggestion="研究開発の範囲を技術的事項に限定し、営業情報を遮断してください。",
            )
        )
    elif with_competitor:
        findings.append(
            AntitrustFinding(
                code="joint_research_competitor_caution",
                title="競合との共同研究（情報交換範囲の確認要）",
                severity=AntitrustCheckSeverity.WARN,
                description=(
                    "競合他社との共同研究開発です。技術情報と営業情報（価格・顧客・"
                    "数量）を分離し、参加者を必要最小限に限定してください。"
                ),
                citation="公正取引委員会「共同研究開発に関する独占禁止法上の指針」",
            )
        )
    else:
        findings.append(
            AntitrustFinding(
                code="joint_research_none",
                title="共同研究に関する競争法リスクは検出されませんでした",
                severity=AntitrustCheckSeverity.INFO,
                description="申告内容から機械的に検出されるリスク要因はありません。",
                citation="独占禁止法 3 条",
            )
        )
    return findings


_CheckFn = Callable[[dict[str, Any]], list[AntitrustFinding]]

_DISPATCH: dict[str, _CheckFn] = {
    AntitrustCheckType.GENERAL.value: lambda ctx: check_general(str(ctx.get("text") or "")),
    AntitrustCheckType.BID_RIGGING.value: check_bid_rigging,
    AntitrustCheckType.PRICE_EXCHANGE.value: check_price_exchange,
    AntitrustCheckType.JV_FORMATION.value: check_jv_formation,
    AntitrustCheckType.JOINT_RESEARCH.value: check_joint_research,
}


def run_check(check_type: str, context: dict[str, Any]) -> list[AntitrustFinding]:
    """Dispatch ``check_type`` to the matching rule function.

    Raises ``ValueError`` for an unknown ``check_type`` (validated upstream by
    the service layer against :class:`AntitrustCheckType`).
    """
    handler = _DISPATCH.get(check_type)
    if handler is None:
        raise ValueError(f"不正なチェック種別: {check_type!r}")
    findings = handler(context or {})
    logger.info(
        "antitrust.check",
        check_type=check_type,
        findings=len(findings),
        severity=overall_severity(findings),
    )
    return findings


__all__ = [
    "AntitrustFinding",
    "check_bid_rigging",
    "check_general",
    "check_joint_research",
    "check_jv_formation",
    "check_price_exchange",
    "overall_severity",
    "run_check",
]
