"""支払コンプライアンス判定（60日/50日・遅延利息・手形等禁止）のユニットテスト."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.services.payment_compliance import assess


def test_60_day_rule_toritekihou():
    result = assess(
        contract_id=1,
        order_date=date(2026, 2, 1),
        receipt_date=date(2026, 3, 1),
        inspection_date=date(2026, 3, 15),
        payment_date=date(2026, 5, 10),
        amount_jpy=Decimal("1000000"),
        transaction_kind="construction",
        is_public_work=False,
    )
    assert result.law_version == "toritekihou"
    assert result.applicable_threshold_days == 60
    assert result.days_receipt_to_payment == 70
    assert any(f.code == "payment_terms_over_limit" for f in result.findings)
    assert result.late_interest_jpy > 0


def test_public_work_50_day_rule():
    result = assess(
        contract_id=2,
        order_date=date(2026, 2, 1),
        receipt_date=date(2026, 3, 1),
        inspection_date=None,
        payment_date=date(2026, 4, 20),
        amount_jpy=None,
        transaction_kind="construction",
        is_public_work=True,
    )
    assert result.applicable_threshold_days == 50
    assert result.to_dict()["overall_status"] == "pass"


def test_old_law_before_2026():
    result = assess(
        contract_id=3,
        order_date=date(2025, 11, 1),
        receipt_date=date(2025, 12, 1),
        inspection_date=None,
        payment_date=date(2026, 1, 20),
        amount_jpy=None,
        transaction_kind="service",
        is_public_work=False,
    )
    assert result.law_version == "subcontract_act"
    assert result.days_receipt_to_payment == 50


def test_missing_dates_warns():
    result = assess(
        contract_id=4,
        order_date=None,
        receipt_date=None,
        inspection_date=None,
        payment_date=None,
        amount_jpy=None,
        transaction_kind=None,
        is_public_work=False,
    )
    assert result.law_version == "unknown"
    assert result.to_dict()["overall_status"] == "warning"
    assert any(f.code == "payment_dates_incomplete" for f in result.findings)
