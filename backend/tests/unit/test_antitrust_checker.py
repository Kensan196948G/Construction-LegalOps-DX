"""独禁法・入札談合コンプライアンス — ルールベースチェッカーの単体テスト（Issue #122）."""

from __future__ import annotations

import pytest

from app.services import antitrust_checker


def test_check_general_no_flag() -> None:
    findings = antitrust_checker.check_general("通常の工事請負契約書です。")
    assert len(findings) == 1
    assert findings[0].code == "antitrust_general_no_flag"
    assert antitrust_checker.overall_severity(findings) == "info"


def test_check_general_detects_red_flag() -> None:
    findings = antitrust_checker.check_general("本件は競合他社と価格を合わせて入札する予定である。")
    codes = {f.code for f in findings}
    assert "antitrust_general_red_flag" in codes
    assert antitrust_checker.overall_severity(findings) == "block"


def test_check_bid_rigging_flags_competitor_contact_with_agency_involvement() -> None:
    """発注機関職員の関与がある場合のみ入札談合等関与行為防止法の対象として BLOCK."""
    findings = antitrust_checker.check_bid_rigging(
        {
            "is_public_bid": True,
            "contacted_competitors": True,
            "procuring_agency_involvement": True,
        }
    )
    codes = {f.code for f in findings}
    assert "bid_rigging_competitor_contact" in codes
    assert antitrust_checker.overall_severity(findings) == "block"


def test_check_bid_rigging_flags_competitor_contact_on_private_bid() -> None:
    """民間入札（is_public_bid=False）でも競合接触の申告は所見として検出されるべき."""
    findings = antitrust_checker.check_bid_rigging(
        {"is_public_bid": False, "contacted_competitors": True}
    )
    codes = {f.code for f in findings}
    assert "bid_rigging_competitor_contact" in codes
    # 発注機関職員の関与がないため、入札談合等関与行為防止法の対象外で WARN
    assert antitrust_checker.overall_severity(findings) == "warn"


def test_check_bid_rigging_public_bid_without_agency_involvement_is_warn() -> None:
    """公共入札でも発注機関職員の関与が申告されていなければ BLOCK にしない."""
    findings = antitrust_checker.check_bid_rigging(
        {"is_public_bid": True, "contacted_competitors": True}
    )
    codes = {f.code for f in findings}
    assert "bid_rigging_competitor_contact" in codes
    assert antitrust_checker.overall_severity(findings) == "warn"


def test_check_bid_rigging_no_risk() -> None:
    findings = antitrust_checker.check_bid_rigging({"is_public_bid": True})
    assert [f.code for f in findings] == ["bid_rigging_none"]
    assert antitrust_checker.overall_severity(findings) == "info"


def test_check_bid_rigging_price_shared() -> None:
    findings = antitrust_checker.check_bid_rigging({"pre_bid_price_shared": True})
    codes = {f.code for f in findings}
    assert "bid_rigging_price_shared" in codes


def test_check_bid_rigging_text_flag() -> None:
    findings = antitrust_checker.check_bid_rigging({"text": "今回は受注予定者を事前に決めている"})
    codes = {f.code for f in findings}
    assert "bid_rigging_text_flag" in codes


def test_check_price_exchange_with_competitor_blocks() -> None:
    findings = antitrust_checker.check_price_exchange(
        {
            "counterparty_is_competitor": True,
            "exchanged_topics": ["price", "customer_allocation"],
        }
    )
    codes = {f.code for f in findings}
    assert "price_exchange_with_competitor" in codes
    assert antitrust_checker.overall_severity(findings) == "block"


def test_check_price_exchange_no_business_reason_warns() -> None:
    findings = antitrust_checker.check_price_exchange(
        {"counterparty_is_competitor": True, "exchanged_topics": []}
    )
    codes = {f.code for f in findings}
    assert "price_exchange_no_business_reason" in codes
    assert antitrust_checker.overall_severity(findings) == "warn"


def test_check_price_exchange_none() -> None:
    findings = antitrust_checker.check_price_exchange({})
    assert [f.code for f in findings] == ["price_exchange_none"]


def test_check_jv_formation_price_fixing_scope_blocks() -> None:
    findings = antitrust_checker.check_jv_formation(
        {"is_competitor_jv": True, "scope_covers_pricing": True}
    )
    codes = {f.code for f in findings}
    assert "jv_formation_price_fixing_scope" in codes
    assert antitrust_checker.overall_severity(findings) == "block"


def test_check_jv_formation_market_share_notice() -> None:
    findings = antitrust_checker.check_jv_formation({"combined_market_share_pct": 40})
    codes = {f.code for f in findings}
    assert "jv_formation_market_share_notice" in codes
    assert antitrust_checker.overall_severity(findings) == "warn"


def test_check_jv_formation_none() -> None:
    findings = antitrust_checker.check_jv_formation({})
    assert [f.code for f in findings] == ["jv_formation_none"]


def test_check_joint_research_scope_violation() -> None:
    findings = antitrust_checker.check_joint_research(
        {"with_competitor": True, "covers_pricing_or_output": True}
    )
    codes = {f.code for f in findings}
    assert "joint_research_scope_violation" in codes
    assert antitrust_checker.overall_severity(findings) == "block"


def test_check_joint_research_caution() -> None:
    findings = antitrust_checker.check_joint_research({"with_competitor": True})
    codes = {f.code for f in findings}
    assert "joint_research_competitor_caution" in codes
    assert antitrust_checker.overall_severity(findings) == "warn"


def test_check_joint_research_none() -> None:
    findings = antitrust_checker.check_joint_research({})
    assert [f.code for f in findings] == ["joint_research_none"]


@pytest.mark.parametrize(
    "check_type",
    ["general", "bid_rigging", "price_exchange", "jv_formation", "joint_research"],
)
def test_run_check_dispatches_all_types(check_type: str) -> None:
    findings = antitrust_checker.run_check(check_type, {"text": "テスト"})
    assert isinstance(findings, list)
    assert len(findings) >= 1


def test_run_check_unknown_type_raises() -> None:
    with pytest.raises(ValueError):
        antitrust_checker.run_check("unknown_type", {})


def test_finding_to_dict_roundtrip() -> None:
    findings = antitrust_checker.check_general("談合をした。")
    as_dicts = [f.to_dict() for f in findings]
    assert as_dicts[0]["severity"] == "block"
    assert "citation" in as_dicts[0]
