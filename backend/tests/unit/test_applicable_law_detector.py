"""Unit tests for app.services.applicable_law (適用法令自動判定)."""

from __future__ import annotations

from datetime import date

from app.services.applicable_law import determine


def _law_codes(result) -> list[str]:
    return [item.law_code for item in result.laws]


class TestApplicableLawDetector:
    def test_construction_contract_applies_construction_law(self) -> None:
        result = determine(contract_type="請負")
        assert "construction_industry_act" in _law_codes(result)
        law = next(item for item in result.laws if item.law_code == "construction_industry_act")
        assert law.applies is True
        assert law.confidence > 0.9

    def test_non_construction_does_not_apply(self) -> None:
        result = determine(contract_type="売買")
        law = next(item for item in result.laws if item.law_code == "construction_industry_act")
        assert law.applies is False

    def test_toritekihou_applies_by_capital(self) -> None:
        result = determine(
            contract_type="その他",
            transaction_kind="manufacturing",
            our_capital_jpy=400_000_000,
            counterparty_capital_jpy=100_000_000,
        )
        law = next(item for item in result.laws if item.law_code == "toritekihou")
        assert law.applies is True
        assert law.confidence >= 0.85

    def test_toritekihou_applies_by_employee_count(self) -> None:
        result = determine(
            transaction_kind="service",
            our_employees=150,
            counterparty_employees=50,
        )
        law = next(item for item in result.laws if item.law_code == "toritekihou")
        assert law.applies is True

    def test_toritekihou_not_applies_when_our_side_small(self) -> None:
        result = determine(
            transaction_kind="manufacturing",
            our_capital_jpy=10_000_000,
            counterparty_capital_jpy=500_000_000,
        )
        law = next(item for item in result.laws if item.law_code == "toritekihou")
        assert law.applies is False

    def test_law_version_switch_after_2026(self) -> None:
        result = determine(
            contract_type="請負",
            transaction_kind="manufacturing",
            order_date=date(2026, 3, 1),
            our_capital_jpy=400_000_000,
            counterparty_capital_jpy=50_000_000,
        )
        switch = next(
            item
            for item in result.laws
            if item.law_code == "law_version_switch"
        )
        assert "取適法" in switch.reason

    def test_law_version_switch_before_2026(self) -> None:
        result = determine(
            contract_type="請負",
            transaction_kind="manufacturing",
            order_date=date(2025, 6, 1),
            our_capital_jpy=400_000_000,
            counterparty_capital_jpy=50_000_000,
        )
        switch = next(
            item
            for item in result.laws
            if item.law_code == "law_version_switch"
        )
        assert "旧下請法" in switch.reason

    def test_public_work_applies_quality_act(self) -> None:
        result = determine(contract_type="請負", is_public_work=True)
        law = next(
            item
            for item in result.laws
            if item.law_code == "public_construction_quality_act"
        )
        assert law.applies is True

    def test_personal_data_flag(self) -> None:
        result = determine(handles_personal_data=True)
        law = next(item for item in result.laws if item.law_code == "pipa")
        assert law.applies is True

    def test_large_amount_requires_license_check(self) -> None:
        result = determine(contract_type="請負", amount_jpy=200_000_000)
        law = next(
            item
            for item in result.laws
            if item.law_code == "construction_license_requirement"
        )
        assert law.applies is True
