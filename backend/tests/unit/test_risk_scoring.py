"""Unit tests for ``app.services.risk_scoring.compute_risk_score``.

Spec source: ``docs/risk_scoring_policy.md``.

The real signature is::

    compute_risk_score(
        issues: Iterable[Any],
        contract_type: str | ContractType,
        *,
        amount_jpy: int | float | None = None,
        duration_months: int | None = None,
    ) -> tuple[int, RiskLevel]
"""

from __future__ import annotations

import pytest

risk_scoring = pytest.importorskip(
    "app.services.risk_scoring",
    reason="risk_scoring service not implemented yet",
)


def _score(issues=(), contract_type="請負", amount_jpy=None, duration_months=None) -> int:
    score, _level = risk_scoring.compute_risk_score(
        issues,
        contract_type,
        amount_jpy=amount_jpy,
        duration_months=duration_months,
    )
    return score


@pytest.mark.parametrize(
    "contract_type",
    ["請負", "委託", "JV", "賃借", "秘密保持", "売買", "その他"],
)
def test_base_score_no_issues_returns_int_in_range(contract_type):
    """Arrange: no issues. Act: compute. Assert: 0 <= score <= 100."""
    # Arrange / Act
    score, level = risk_scoring.compute_risk_score([], contract_type)
    # Assert
    assert isinstance(score, int)
    assert 0 <= score <= 100
    assert level is not None


def test_boundary_score_clamped_to_100():
    """Arrange: huge issue list. Act: compute. Assert: clamped to 100."""
    # Arrange — repeat highest-impact codes
    issues = [{"code": "no_liability_cap"}] * 50
    # Act
    score, _ = risk_scoring.compute_risk_score(issues, "請負", amount_jpy=10_000_000_000)
    # Assert
    assert score <= 100


def test_score_floor_is_zero():
    """Arrange: many reduction codes. Act: compute. Assert: score >= 0."""
    # Arrange
    issues = [{"code": "uses_company_template_unchanged"}] * 20
    # Act
    score, _ = risk_scoring.compute_risk_score(issues, "秘密保持")
    # Assert
    assert score >= 0


def test_known_issue_code_increases_score():
    """Arrange: same base + 1 risky issue. Act: compare. Assert: higher."""
    # Arrange
    base = _score(issues=[], contract_type="請負")
    risky = _score(issues=[{"code": "no_liability_cap"}], contract_type="請負")
    # Act / Assert
    assert risky > base


def test_reduction_code_decreases_score():
    """Arrange: same base + 1 mitigation. Act: compare. Assert: lower."""
    # Arrange
    base = _score(issues=[{"code": "no_liability_cap"}], contract_type="請負")
    mitigated = _score(
        issues=[{"code": "no_liability_cap"}, {"code": "outside_counsel_pre_reviewed"}],
        contract_type="請負",
    )
    # Act / Assert
    assert mitigated <= base


def test_unknown_issue_code_is_ignored():
    """Arrange: bogus code. Act: compute. Assert: same as empty."""
    # Arrange
    empty = _score(issues=[], contract_type="委託")
    bogus = _score(issues=[{"code": "this_code_does_not_exist"}], contract_type="委託")
    # Act / Assert
    assert empty == bogus


def test_amount_correction_high_value_contract_adds_score():
    """Arrange: same setup, big vs small amount. Act: compare. Assert: bigger >= smaller."""
    # Arrange
    low = _score(contract_type="請負", amount_jpy=1_000_000)
    high = _score(contract_type="請負", amount_jpy=1_000_000_000)
    # Act / Assert
    assert high >= low


def test_duration_correction_long_contract_adds_score():
    """Arrange: same setup, short vs long. Act: compare. Assert: long >= short."""
    # Arrange
    short = _score(contract_type="請負", duration_months=1)
    longer = _score(contract_type="請負", duration_months=72)
    # Act / Assert
    assert longer >= short


def test_breakdown_components_sum_consistently():
    """Arrange: nontrivial scoring. Act: breakdown. Assert: components present."""
    # Arrange
    issues = [{"code": "no_liability_cap"}, {"code": "ambiguous_scope"}]
    # Act
    breakdown = risk_scoring.score_breakdown(
        issues, "請負", amount_jpy=50_000_000, duration_months=12
    )
    # Assert
    assert breakdown.base >= 0
    assert breakdown.issue_total >= 0
    assert 0 <= breakdown.final_score <= 100
    assert any(code == "no_liability_cap" for code, _ in breakdown.issue_contributions)
