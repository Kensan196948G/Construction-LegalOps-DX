"""Risk scoring service.

Implements the additive scoring model defined in
``docs/risk_scoring_policy.md`` (sections 3–5). The function
:func:`compute_risk_score` takes the structured AI-review issue list plus
contract metadata and returns ``(score: int, level: RiskLevel)`` clamped
to ``0..100``.

This module is pure (no I/O) so it is trivially unit-testable.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Final

from app.models.enums import ContractType, RiskLevel

# ---------------------------------------------------------------------------
# Issue codes
#
# The AIReviewService emits issues with a stable ``code`` string. Each code is
# mapped here to the policy-defined score delta. Keeping all weights in one
# table makes the quarterly review meeting (policy §8) tractable.
# ---------------------------------------------------------------------------

#: Score delta per issue code (positive = adds risk, negative = mitigates).
ISSUE_WEIGHTS: Final[dict[str, int]] = {
    # 4.1 損害賠償・責任
    "no_liability_cap": 20,
    "liability_cap_over_100pct": 10,
    "indirect_damages_included": 15,
    "punitive_damages": 20,
    "joint_liability": 10,
    "full_attorney_fees": 5,
    # 4.2 業務範囲・履行
    "ambiguous_scope": 10,
    "subcontract_prohibition_risk": 15,
    "unlimited_subcontracting": 15,
    "vague_acceptance_criteria": 10,
    "delivery_at_counterparty_will": 10,
    # 4.3 契約不適合責任・瑕疵
    "warranty_over_5_years": 10,
    "warranty_over_10_years": 20,
    "strict_liability": 10,
    "asymmetric_mitigation_duty": 5,
    # 4.4 解除・終了
    "counterparty_unconditional_termination": 15,
    "limited_self_termination": 10,
    "penalty_over_30pct": 15,
    "auto_renewal_long_optout": 5,
    # 4.5 知財・データ
    "full_copyright_transfer": 5,
    "no_moral_rights_waiver": 5,
    "personal_data_no_consent_clause": 10,
    "handles_my_number": 15,
    # 4.6 公共工事・コンプライアンス
    "public_jv": 10,
    "bid_qualification_impact": 15,
    "missing_antisocial_clause": 20,
    "no_fcpa_representation": 15,
    "no_collusion_representation": 10,
    "earnings_affects_keishin": 5,
    "scaffold_record_concern": 10,
    # 4.7 当事者属性
    "new_counterparty": 5,
    "credit_concern": 10,
    "antisocial_check_pending": 20,
    "foreign_law_party": 15,
    "individual_sole_proprietor": 5,
    # ---- 5. 減点 ----
    "uses_company_template_unchanged": -10,
    "uses_public_standard_contract": -10,
    "uses_private_standard_contract": -8,
    "outside_counsel_pre_reviewed": -10,
    "existing_counterparty_high_volume": -5,
    "liability_cap_under_30pct": -5,
    "complete_antisocial_clause": -3,
    "no_personal_data": -3,
    "jurisdiction_home_court": -3,
    "clear_force_majeure": -3,
    "esign_with_timestamp": -3,
}

# Base score per contract type (policy §3).
_CONTRACT_TYPE_BASE: Final[dict[ContractType, int]] = {
    ContractType.UKEOI: 25,  # default to 公共; 民間小口は下で減点扱い
    ContractType.ITAKU: 15,
    ContractType.JV: 30,
    ContractType.CHINSHAKU: 10,
    ContractType.NDA: 5,
    ContractType.BAIBAI: 10,
    ContractType.OTHER: 10,
}

_AMOUNT_BANDS: Final[tuple[tuple[int, int], ...]] = (
    (10_000_000, 0),
    (50_000_000, 5),
    (100_000_000, 10),
    (500_000_000, 15),
)
_AMOUNT_OVER_TOP: Final[int] = 20  # 5 億円超

_DURATION_BANDS_MONTHS: Final[tuple[tuple[int, int], ...]] = (
    (3, 0),
    (12, 3),
    (36, 5),
    (60, 8),
)
_DURATION_OVER_TOP: Final[int] = 12


@dataclass(slots=True, frozen=True)
class ScoreBreakdown:
    """Detailed score components, useful for audit-trail display."""

    base: int
    issue_total: int
    amount_adjust: int
    duration_adjust: int
    final_score: int
    level: RiskLevel
    issue_contributions: tuple[tuple[str, int], ...]


def _amount_adjust(amount_jpy: int | float | None) -> int:
    if amount_jpy is None or amount_jpy <= 0:
        return 0
    amt = int(amount_jpy)
    for ceiling, delta in _AMOUNT_BANDS:
        if amt < ceiling:
            return delta
    return _AMOUNT_OVER_TOP


def _duration_adjust(months: int | None) -> int:
    if months is None or months <= 0:
        return 0
    for ceiling, delta in _DURATION_BANDS_MONTHS:
        if months <= ceiling:
            return delta
    return _DURATION_OVER_TOP


def _classify(score: int) -> RiskLevel:
    """Bucket the final integer score into :class:`RiskLevel` per §2.1."""
    if score <= 29:
        return RiskLevel.LOW
    if score <= 59:
        return RiskLevel.MEDIUM
    if score <= 79:
        return RiskLevel.HIGH
    return RiskLevel.CRITICAL


def _normalize_contract_type(value: str | ContractType) -> ContractType:
    if isinstance(value, ContractType):
        return value
    try:
        return ContractType(value)
    except ValueError:
        # Loose match by name (e.g. "UKEOI") to be friendly to callers.
        upper = value.upper()
        for ct in ContractType:
            if ct.name == upper:
                return ct
        return ContractType.OTHER


def _extract_code(issue: Any) -> str | None:
    if isinstance(issue, Mapping):
        code = issue.get("code") or issue.get("issue_code")
        return str(code) if code else None
    code = getattr(issue, "code", None) or getattr(issue, "issue_code", None)
    return str(code) if code else None


def compute_risk_score(
    issues: Iterable[Any],
    contract_type: str | ContractType,
    *,
    amount_jpy: int | float | None = None,
    duration_months: int | None = None,
) -> tuple[int, RiskLevel]:
    """Return ``(score, level)`` for the given AI-review issues.

    ``issues`` is the list produced by :class:`AIReviewService` (or any
    iterable of objects/dicts carrying a ``code`` attribute/key). Unknown
    codes are ignored — they will appear in logs but never silently move
    the score.
    """
    breakdown = score_breakdown(
        issues,
        contract_type,
        amount_jpy=amount_jpy,
        duration_months=duration_months,
    )
    return breakdown.final_score, breakdown.level


def score_breakdown(
    issues: Iterable[Any],
    contract_type: str | ContractType,
    *,
    amount_jpy: int | float | None = None,
    duration_months: int | None = None,
) -> ScoreBreakdown:
    """Like :func:`compute_risk_score` but returns the full breakdown."""
    ct = _normalize_contract_type(contract_type)
    base = _CONTRACT_TYPE_BASE.get(ct, 10)

    contributions: list[tuple[str, int]] = []
    issue_total = 0
    for issue in issues:
        code = _extract_code(issue)
        if not code:
            continue
        delta = ISSUE_WEIGHTS.get(code)
        if delta is None:
            continue
        contributions.append((code, delta))
        issue_total += delta

    amount_adj = _amount_adjust(amount_jpy)
    duration_adj = _duration_adjust(duration_months)

    raw = base + issue_total + amount_adj + duration_adj
    final = max(0, min(100, raw))
    level = _classify(final)

    return ScoreBreakdown(
        base=base,
        issue_total=issue_total,
        amount_adjust=amount_adj,
        duration_adjust=duration_adj,
        final_score=final,
        level=level,
        issue_contributions=tuple(contributions),
    )
