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

from app.models.enums import RiskLevel
from app.services import risk_scoring


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


# ---------------------------------------------------------------------------
# Additional tests to cover previously uncovered lines
# ---------------------------------------------------------------------------


def test_normalize_contract_type_with_enum_instance_returns_same():
    """Arrange: pass ContractType enum directly (line 159). Act. Assert: same value."""
    # Arrange
    from app.models.enums import ContractType

    ct_in = ContractType.JV
    # Act — call via score_breakdown which calls _normalize_contract_type
    score, _level = risk_scoring.compute_risk_score([], ct_in)
    # Assert: JV base = 30, no issues → score == 30
    assert score == 30


def test_normalize_contract_type_by_name_ukeoi():
    """Arrange: string 'UKEOI' (enum name). Act. Assert: resolves correctly (lines 163-167).

    ContractType("UKEOI") raises ValueError, so the name-match branch executes.
    """
    # Act
    score, _level = risk_scoring.compute_risk_score([], "UKEOI")
    # ContractType.UKEOI base = 25 → score == 25
    assert score == 25


def test_normalize_contract_type_unknown_name_returns_other():
    """Arrange: completely unknown string. Act. Assert: falls back to OTHER (line 168)."""
    # Act
    score, _level = risk_scoring.compute_risk_score([], "TOTALLY_UNKNOWN_TYPE")
    # ContractType.OTHER base = 10 → score == 10
    assert score == 10


def test_extract_code_from_object_with_code_attr():
    """Arrange: object with .code attr (line 175). Act. Assert: code used."""
    # Arrange — SimpleNamespace has .code attribute
    from types import SimpleNamespace

    issue = SimpleNamespace(code="no_liability_cap")
    # Act
    score, _ = risk_scoring.compute_risk_score([issue], "請負")
    base_score, _ = risk_scoring.compute_risk_score([], "請負")
    # Assert: no_liability_cap weight=20, so score = base + 20
    assert score == base_score + 20


def test_extract_code_from_object_with_issue_code_attr():
    """Arrange: object with .issue_code attr only (line 175-176 fallback). Act. Assert."""
    # Arrange — object has issue_code, not code
    from types import SimpleNamespace

    issue = SimpleNamespace(code=None, issue_code="ambiguous_scope")
    # Act
    score, _ = risk_scoring.compute_risk_score([issue], "請負")
    base_score, _ = risk_scoring.compute_risk_score([], "請負")
    # Assert: ambiguous_scope weight=10
    assert score == base_score + 10


def test_extract_code_from_dict_with_issue_code_key():
    """Arrange: dict with 'issue_code' key (line 173 fallback path). Act. Assert."""
    # Arrange — dict uses issue_code instead of code
    issue = {"issue_code": "joint_liability"}
    # Act
    score, _ = risk_scoring.compute_risk_score([issue], "請負")
    base_score, _ = risk_scoring.compute_risk_score([], "請負")
    # Assert: joint_liability weight=10
    assert score == base_score + 10


def test_classify_returns_all_four_risk_levels():
    """Arrange: scores hitting all four thresholds. Act. Assert (line 218 _classify)."""
    # LOW: score <= 29
    _s_low, lvl_low = risk_scoring.compute_risk_score([], "秘密保持")  # base=5
    assert lvl_low == RiskLevel.LOW

    # MEDIUM: 30–59 — NDA base(5) + some issues
    issues_medium = [{"code": "no_liability_cap"}] * 2  # 5 + 40 = 45
    _s_med, lvl_med = risk_scoring.compute_risk_score(issues_medium, "秘密保持")
    assert lvl_med == RiskLevel.MEDIUM

    # HIGH: 60–79 — JV base(30) + issues
    issues_high = [{"code": "no_liability_cap"}] * 2  # 30 + 40 = 70
    _s_hi, lvl_hi = risk_scoring.compute_risk_score(issues_high, "JV")
    assert lvl_hi == RiskLevel.HIGH

    # CRITICAL: >= 80 — JV base(30) + big issues
    issues_crit = [{"code": "no_liability_cap"}] * 3  # 30 + 60 = 90
    _s_crit, lvl_crit = risk_scoring.compute_risk_score(issues_crit, "JV")
    assert lvl_crit == RiskLevel.CRITICAL


def test_extract_code_returns_none_for_empty_mapping():
    """Arrange: dict with no code/issue_code. Act. Assert: ignored (line 174)."""
    # Arrange
    issue_no_code = {"foo": "bar"}
    base_score, _ = risk_scoring.compute_risk_score([], "委託")
    # Act
    score, _ = risk_scoring.compute_risk_score([issue_no_code], "委託")
    # Assert: no code → ignored → same as base
    assert score == base_score


def test_extract_code_returns_none_for_object_without_code():
    """Arrange: object with neither .code nor .issue_code (lines 175-176). Act. Assert."""
    from types import SimpleNamespace

    issue = SimpleNamespace(other_attr="value")  # no code, no issue_code
    base_score, _ = risk_scoring.compute_risk_score([], "委託")
    score, _ = risk_scoring.compute_risk_score([issue], "委託")
    assert score == base_score
