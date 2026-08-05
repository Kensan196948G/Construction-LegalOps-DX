"""支払・出来高・検収コンプライアンス（評価: 優先度 高 #3）.

発注日・受領日・検収日・支払日から法定期限を実日で計算し、
遅延利息・不当減額・保留金・手形等の禁止判定を行う。
取適法（2026-01-01 施行）と公共工事 50 日基準の両方を考慮する。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from app.services.compliance_checker import (
    _TORITEKI_MATRIX,
    TORITEKI_EFFECTIVE_DATE,
)


@dataclass(slots=True)
class PaymentFinding:
    code: str
    severity: str  # block | warn | info
    message: str
    citation: str
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PaymentComplianceResult:
    contract_id: int
    order_date: date | None
    receipt_date: date | None
    inspection_date: date | None
    payment_date: date | None
    transaction_kind: str | None
    is_public_work: bool
    law_version: str  # toritekihou | subcontract_act | unknown
    applicable_threshold_days: int
    days_receipt_to_payment: int | None = None
    days_inspection_to_payment: int | None = None
    late_interest_jpy: Decimal = Decimal("0")
    findings: list[PaymentFinding] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "order_date": self.order_date.isoformat() if self.order_date else None,
            "receipt_date": self.receipt_date.isoformat() if self.receipt_date else None,
            "inspection_date": self.inspection_date.isoformat() if self.inspection_date else None,
            "payment_date": self.payment_date.isoformat() if self.payment_date else None,
            "transaction_kind": self.transaction_kind,
            "is_public_work": self.is_public_work,
            "law_version": self.law_version,
            "applicable_threshold_days": self.applicable_threshold_days,
            "days_receipt_to_payment": self.days_receipt_to_payment,
            "days_inspection_to_payment": self.days_inspection_to_payment,
            "late_interest_jpy": str(self.late_interest_jpy),
            "overall_status": (
                "fail"
                if any(f.severity == "block" for f in self.findings)
                else "warning"
                if any(f.severity == "warn" for f in self.findings)
                else "pass"
            ),
            "findings": [
                {
                    "code": f.code,
                    "severity": f.severity,
                    "message": f.message,
                    "citation": f.citation,
                    "detail": f.detail,
                }
                for f in self.findings
            ],
        }


def _threshold_days(is_public_work: bool, law_version: str) -> int:
    if is_public_work:
        return 50
    if law_version == "toritekihou":
        return 60
    return 60


def _law_version(order_date: date | None) -> str:
    if order_date is None:
        return "unknown"
    return "toritekihou" if order_date >= TORITEKI_EFFECTIVE_DATE else "subcontract_act"


def assess(
    *,
    contract_id: int,
    order_date: date | None,
    receipt_date: date | None,
    inspection_date: date | None,
    payment_date: date | None,
    amount_jpy: Decimal | int | None,
    transaction_kind: str | None,
    is_public_work: bool,
    text: str = "",
    counterparty_capital_jpy: int | None = None,
    counterparty_employees: int | None = None,
    our_capital_jpy: int | None = None,
    our_employees: int | None = None,
) -> PaymentComplianceResult:
    """支払コンプライアンス判定を実行する。"""
    law_version = _law_version(order_date)
    threshold = _threshold_days(is_public_work, law_version)
    result = PaymentComplianceResult(
        contract_id=contract_id,
        order_date=order_date,
        receipt_date=receipt_date,
        inspection_date=inspection_date,
        payment_date=payment_date,
        transaction_kind=transaction_kind,
        is_public_work=is_public_work,
        law_version=law_version,
        applicable_threshold_days=threshold,
    )

    if order_date is None:
        result.findings.append(
            PaymentFinding(
                code="payment_order_date_unknown",
                severity="warn",
                message="発注日が未設定のため新旧法（取適法/旧下請法）の適用判定ができません。",
                citation="取適法 附則（2026-01-01 施行）",
            )
        )

    if receipt_date is None or payment_date is None:
        result.findings.append(
            PaymentFinding(
                code="payment_dates_incomplete",
                severity="warn",
                message="受領日または支払日が未設定のため法定支払期日の実日計算ができません。",
                citation="取適法 3 条 1 項（受領日から 60 日以内）",
            )
        )
    else:
        days = (payment_date - receipt_date).days
        result.days_receipt_to_payment = days
        if days > threshold:
            result.findings.append(
                PaymentFinding(
                    code="payment_terms_over_limit",
                    severity="block",
                    message=(
                        f"受領日 {receipt_date.isoformat()} から支払日 "
                        f"{payment_date.isoformat()} まで {days} 日あり、"
                        f"{threshold} 日以内という基準を超えています。"
                    ),
                    citation=(
                        "取適法 3 条 1 項 / 公共工事標準請負約款"
                        if law_version == "toritekihou"
                        else "下請代金支払遅延等防止法 2 条の 2"
                    ),
                    detail={"days": days, "threshold": threshold},
                )
            )
            if amount_jpy is not None and amount_jpy > 0:
                late_days = max(days - threshold, 0)
                interest = Decimal(str(amount_jpy)) * Decimal("0.146") / Decimal("365") * Decimal(
                    str(late_days)
                )
                result.late_interest_jpy = interest.quantize(Decimal("1"))
                result.findings.append(
                    PaymentFinding(
                        code="payment_late_interest",
                        severity="info",
                        message=(
                            f"遅延利息の概算は年 14.6% 基準で約 "
                            f"{result.late_interest_jpy:,} 円です。"
                        ),
                        citation="民法 404 条 / 商事法定利率（参考値）",
                        detail={"late_days": late_days, "rate": "14.6%/year"},
                    )
                )

    if inspection_date is not None and payment_date is not None:
        result.days_inspection_to_payment = (payment_date - inspection_date).days

    if re.search(r"手形", text):
        result.findings.append(
            PaymentFinding(
                code="payment_promissory_note",
                severity="block",
                message="手形による支払いの記載があります（2026 年以降の取適法対象取引では禁止）。",
                citation="取適法（手形払等の禁止）",
            )
        )
    if re.search(r"電子記録債権|電子記録債券|ファクタリング", text):
        result.findings.append(
            PaymentFinding(
                code="payment_ecb_factoring",
                severity="warn",
                message=(
                    "電子記録債権・ファクタリング条件の記載があります。"
                    "60 日以内に現金化できるか確認してください。"
                ),
                citation="取適法（手形払等の禁止）",
            )
        )
    if re.search(r"不当|一方的に(減額|値引)|無条件減額|相殺|赤伝", text):
        result.findings.append(
            PaymentFinding(
                code="payment_improper_reduction",
                severity="warn",
                message="不当な減額・相殺・赤伝の疑いがある記載があります。",
                citation="取適法（減額の禁止）",
            )
        )
    if re.search(r"保留金", text):
        result.findings.append(
            PaymentFinding(
                code="payment_retention",
                severity="info",
                message=(
                    "保留金の記載があります。上限と返還時期"
                    "（出来高の 10% 以内等）を確認してください。"
                ),
                citation="公共工事標準請負約款 / 下請取引適正化の運用指針",
            )
        )

    # 取適法適用判定（対象取引なら文言で通知）
    if transaction_kind in _TORITEKI_MATRIX:
        kind_row = _TORITEKI_MATRIX[transaction_kind]
        cap = int(kind_row["capital"])
        emp = int(kind_row["employees"])
        counterparty_small = (
            (counterparty_capital_jpy is not None and counterparty_capital_jpy <= cap)
            or (counterparty_employees is not None and counterparty_employees <= emp)
        )
        ours_big = (
            (our_capital_jpy or 0) > cap
            or (our_employees or 0) > emp
        )
        if ours_big and counterparty_small:
            result.findings.append(
                PaymentFinding(
                    code="payment_toritekihou_applies",
                    severity="info",
                    message="取適法の委託事業者/中小受託事業者関係に該当するため、支払期日・書面交付の法定要件が適用されます。",
                    citation="取適法 2・3 条",
                )
            )

    return result


__all__ = ["PaymentComplianceResult", "assess"]
