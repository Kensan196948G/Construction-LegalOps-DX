"""Unit tests for app.services.compliance_checker.

Covers the ComplianceChecker rule methods and ContractSnapshot construction,
targeting the uncovered lines:
  121-127, 144, 166-188, 192, 211-232, 239-243, 263-284, 294-305
"""

from __future__ import annotations

import pytest

from app.models.enums import ContractType
from app.services.compliance_checker import (
    ComplianceChecker,
    ComplianceFinding,
    ComplianceSeverity,
    ContractSnapshot,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _snap(**kwargs) -> ContractSnapshot:
    """Return a minimal ContractSnapshot with sensible defaults."""
    defaults = {
        "text": "",
        "contract_type": ContractType.OTHER,
        "amount_jpy": None,
        "is_public_work": False,
        "counterparty_capital_jpy": None,
        "our_capital_jpy": None,
        "handles_personal_data": False,
    }
    defaults.update(kwargs)
    return ContractSnapshot(**defaults)


# Full text that satisfies all 建設業法19条 keywords
_KEN19_FULL_TEXT = (
    "工事内容 請負代金 工期 引渡 前金払 部分払 出来高払 設計変更 第三者損害 "
    "天災 価格変動 スライド 瑕疵担保 紛争解決 反社会的勢力 "
    "2026年4月1日着工、2027年3月31日完成"
)

# 労務費等の内訳・価格変動対応を含む完全テキスト
_FULL_UKEOI_TEXT = (
    _KEN19_FULL_TEXT
    + " 労務費 材料費 安全衛生経費 法定福利費 建退共 契約前通知 価格変更協議"
    " 2026年4月1日着工、2027年3月31日完成。請負代金 100,000,000円。"
)


# ---------------------------------------------------------------------------
# ContractSnapshot construction
# ---------------------------------------------------------------------------


class TestContractSnapshot:
    def test_default_values(self) -> None:
        snap = ContractSnapshot(text="some text")
        assert snap.contract_type == ContractType.OTHER
        assert snap.amount_jpy is None
        assert snap.is_public_work is False
        assert snap.handles_personal_data is False
        assert snap.metadata == {}

    def test_custom_values(self) -> None:
        snap = ContractSnapshot(
            text="テキスト",
            contract_type=ContractType.UKEOI,
            amount_jpy=5_000_000,
            is_public_work=True,
            our_capital_jpy=400_000_000,
            counterparty_capital_jpy=100_000_000,
            handles_personal_data=True,
            metadata={"key": "val"},
        )
        assert snap.contract_type == ContractType.UKEOI
        assert snap.amount_jpy == 5_000_000
        assert snap.is_public_work is True
        assert snap.handles_personal_data is True
        assert snap.metadata == {"key": "val"}


# ---------------------------------------------------------------------------
# ComplianceChecker._coerce
# ---------------------------------------------------------------------------


class TestCoerce:
    def setup_method(self) -> None:
        self.checker = ComplianceChecker()

    def test_coerce_returns_snapshot_unchanged(self) -> None:
        snap = _snap(text="hello")
        result = self.checker._coerce(snap)
        assert result is snap

    def test_coerce_dict_minimal(self) -> None:
        """dict with only 'text' key populates defaults correctly."""
        result = self.checker._coerce({"text": "foo"})
        assert isinstance(result, ContractSnapshot)
        assert result.text == "foo"
        assert result.contract_type == ContractType.OTHER
        assert result.amount_jpy is None
        assert result.is_public_work is False
        assert result.handles_personal_data is False
        assert result.metadata == {}

    def test_coerce_dict_full(self) -> None:
        """dict with all supported keys is coerced correctly."""
        d = {
            "text": "本文",
            "contract_type": ContractType.UKEOI,
            "amount_jpy": 3_000_000,
            "is_public_work": True,
            "counterparty_capital_jpy": 200_000_000,
            "our_capital_jpy": 500_000_000,
            "handles_personal_data": True,
            "metadata": {"ref": "ABC"},
        }
        result = self.checker._coerce(d)
        assert result.text == "本文"
        assert result.contract_type == ContractType.UKEOI
        assert result.amount_jpy == 3_000_000
        assert result.is_public_work is True
        assert result.counterparty_capital_jpy == 200_000_000
        assert result.our_capital_jpy == 500_000_000
        assert result.handles_personal_data is True
        assert result.metadata == {"ref": "ABC"}

    def test_coerce_orm_like_object(self) -> None:
        """Duck-typed ORM object is coerced via getattr path."""

        class FakeOrm:
            text = "ORM テキスト"
            contract_type = ContractType.ITAKU
            amount_jpy = 1_000_000
            is_public_work = False
            counterparty_capital_jpy = None
            our_capital_jpy = None
            handles_personal_data = True

        result = self.checker._coerce(FakeOrm())
        assert isinstance(result, ContractSnapshot)
        assert result.text == "ORM テキスト"
        assert result.contract_type == ContractType.ITAKU
        assert result.handles_personal_data is True

    def test_coerce_orm_missing_text_defaults_to_empty(self) -> None:
        """ORM object without .text attribute falls back to empty string."""

        class NoText:
            contract_type = ContractType.OTHER

        result = self.checker._coerce(NoText())
        assert result.text == ""


# ---------------------------------------------------------------------------
# _check_kenpou_19
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCheckKenpou19:
    def setup_method(self) -> None:
        self.checker = ComplianceChecker()

    async def test_non_ukeoi_type_returns_empty(self) -> None:
        """Non-UKEOI contract type skips the rule entirely (lines 119-120)."""
        snap = _snap(text="工事内容 請負代金", contract_type=ContractType.ITAKU)
        findings = self.checker._check_kenpou_19(snap, snap.text)
        assert findings == []

    async def test_other_type_string_returns_empty(self) -> None:
        snap = _snap(text="工事内容 請負代金", contract_type="その他")
        findings = self.checker._check_kenpou_19(snap, snap.text)
        assert findings == []

    async def test_ukeoi_all_keywords_present_returns_empty(self) -> None:
        """All 11 required items present → no finding."""
        snap = _snap(text=_KEN19_FULL_TEXT, contract_type=ContractType.UKEOI)
        findings = self.checker._check_kenpou_19(snap, snap.text)
        assert findings == []

    async def test_ukeoi_string_all_keywords_present_returns_empty(self) -> None:
        """contract_type as plain string '請負' is also accepted."""
        snap = _snap(text=_KEN19_FULL_TEXT, contract_type="請負")
        findings = self.checker._check_kenpou_19(snap, snap.text)
        assert findings == []

    async def test_ukeoi_missing_all_keywords_fires_block(self) -> None:
        """All items absent → BLOCK finding with all 11 labels."""
        snap = _snap(text="契約書", contract_type=ContractType.UKEOI)
        findings = self.checker._check_kenpou_19(snap, snap.text)
        assert len(findings) == 1
        f = findings[0]
        assert f.code == "construction_law_19"
        assert f.severity == ComplianceSeverity.BLOCK
        assert len(f.matched_keywords) == 11

    async def test_ukeoi_missing_some_keywords_lists_them(self) -> None:
        """Partially-filled text reports only the missing labels."""
        text = "工事内容 請負代金 工期 引渡 前金払"  # 5 of 11 present
        snap = _snap(text=text, contract_type=ContractType.UKEOI)
        findings = self.checker._check_kenpou_19(snap, text)
        main = next(f for f in findings if f.code == "construction_law_19")
        assert len(main.matched_keywords) == 6  # 6 missing

    async def test_finding_citation(self) -> None:
        snap = _snap(text="", contract_type=ContractType.UKEOI)
        findings = self.checker._check_kenpou_19(snap, snap.text)
        assert "建設業法 19 条" in findings[0].citation


# ---------------------------------------------------------------------------
# _check_antisocial
# ---------------------------------------------------------------------------


class TestCheckAntisocial:
    def setup_method(self) -> None:
        self.checker = ComplianceChecker()

    def test_antisocial_keyword_present_returns_empty(self) -> None:
        """反社会的勢力 keyword found → no finding (line 144)."""
        findings = self.checker._check_antisocial("反社会的勢力排除について定める。")
        assert findings == []

    def test_bouryokudan_keyword_present_returns_empty(self) -> None:
        """暴力団排除 keyword found → no finding."""
        findings = self.checker._check_antisocial("本契約に暴力団排除条項を含む。")
        assert findings == []

    def test_no_keyword_fires_block(self) -> None:
        """Neither keyword present → BLOCK finding."""
        findings = self.checker._check_antisocial("普通の契約書。")
        assert len(findings) == 1
        assert findings[0].code == "antisocial_clause_missing"
        assert findings[0].severity == ComplianceSeverity.BLOCK


# ---------------------------------------------------------------------------
# _check_subcontract_law
# ---------------------------------------------------------------------------


class TestCheckSubcontractLaw:
    def setup_method(self) -> None:
        self.checker = ComplianceChecker()

    def test_both_capital_none_returns_empty(self) -> None:
        """Missing capital info → skip the rule."""
        snap = _snap()
        findings = self.checker._check_subcontract_law(snap, "")
        assert findings == []

    def test_our_capital_none_returns_empty(self) -> None:
        snap = _snap(our_capital_jpy=None, counterparty_capital_jpy=100_000_000)
        findings = self.checker._check_subcontract_law(snap, "")
        assert findings == []

    def test_counterparty_capital_none_flags_unknown_kind(self) -> None:
        """相手方資本金が不明でも自社規模から対象可能性は通知する。"""
        snap = _snap(our_capital_jpy=400_000_000, counterparty_capital_jpy=None)
        findings = self.checker._check_subcontract_law(snap, "")
        codes = [f.code for f in findings]
        assert codes == ["toritekihou_transaction_kind_unknown"]

    def test_threshold_not_met_flags_unknown_kind(self) -> None:
        """Capital equal 300M → not applicable, but 取引類型不明は通知する。"""
        snap = _snap(our_capital_jpy=300_000_000, counterparty_capital_jpy=300_000_000)
        findings = self.checker._check_subcontract_law(snap, "")
        codes = [f.code for f in findings]
        assert codes == ["toritekihou_transaction_kind_unknown"]

    def test_threshold_met_fires_warn(self) -> None:
        """ours > 300M, theirs <= 300M → WARN finding."""
        snap = _snap(
            our_capital_jpy=400_000_000,
            counterparty_capital_jpy=100_000_000,
            transaction_kind="manufacturing",
        )
        findings = self.checker._check_subcontract_law(snap, "60日以内に支払う。")
        codes = [f.code for f in findings]
        assert "subcontract_act_applies" in codes

    def test_payment_term_absent_fires_additional_block(self) -> None:
        """60-day payment text absent → BLOCK finding added (lines 176-186)."""
        snap = _snap(
            our_capital_jpy=400_000_000,
            counterparty_capital_jpy=100_000_000,
            transaction_kind="manufacturing",
        )
        findings = self.checker._check_subcontract_law(snap, "特に規定なし。")
        codes = [f.code for f in findings]
        assert "subcontract_act_applies" in codes
        assert "subcontract_act_payment_terms" in codes
        block = next(f for f in findings if f.code == "subcontract_act_payment_terms")
        assert block.severity == ComplianceSeverity.BLOCK

    def test_payment_term_60days_kansuji_prevents_block(self) -> None:
        """六十日 (kanji form) also satisfies the payment-term check."""
        snap = _snap(
            our_capital_jpy=400_000_000,
            counterparty_capital_jpy=100_000_000,
            transaction_kind="manufacturing",
        )
        findings = self.checker._check_subcontract_law(snap, "代金は六十日以内に支払う。")
        codes = [f.code for f in findings]
        assert "subcontract_act_payment_terms" not in codes


# ---------------------------------------------------------------------------
# _check_electronic_books_law
# ---------------------------------------------------------------------------


class TestCheckElectronicBooksLaw:
    def setup_method(self) -> None:
        self.checker = ComplianceChecker()

    def test_denshi_keiyaku_present_returns_empty(self) -> None:
        """電子契約 keyword → no finding (line 192 branch)."""
        findings = self.checker._check_electronic_books_law("本契約は電子契約にて締結する。")
        assert findings == []

    def test_timestamp_present_returns_empty(self) -> None:
        findings = self.checker._check_electronic_books_law("タイムスタンプを付与する。")
        assert findings == []

    def test_denshi_sign_present_returns_empty(self) -> None:
        findings = self.checker._check_electronic_books_law("電子署名により締結する。")
        assert findings == []

    def test_no_keyword_fires_info(self) -> None:
        """No electronic-book keyword → INFO finding."""
        findings = self.checker._check_electronic_books_law("紙媒体で締結する契約書。")
        assert len(findings) == 1
        assert findings[0].code == "electronic_books_act_hint"
        assert findings[0].severity == ComplianceSeverity.INFO


# ---------------------------------------------------------------------------
# _check_personal_data
# ---------------------------------------------------------------------------


class TestCheckPersonalData:
    def setup_method(self) -> None:
        self.checker = ComplianceChecker()

    def test_no_personal_data_flag_and_no_keyword_returns_empty(self) -> None:
        """Neither flag nor text keyword → skip (lines 209-210)."""
        snap = _snap(handles_personal_data=False)
        findings = self.checker._check_personal_data(snap, "通常の契約書。")
        assert findings == []

    def test_handles_personal_data_flag_with_both_clauses_returns_empty(self) -> None:
        """Flag set but text contains both required clauses → no findings."""
        snap = _snap(handles_personal_data=True)
        text = "利用目的は○○とする。第三者提供には同意が必要。"
        findings = self.checker._check_personal_data(snap, text)
        assert findings == []

    def test_keyword_in_text_triggers_checks(self) -> None:
        """'個人情報' in text even without flag triggers checks."""
        snap = _snap(handles_personal_data=False)
        findings = self.checker._check_personal_data(snap, "個人情報を取り扱う。")
        assert len(findings) > 0

    def test_purpose_missing_fires_warn(self) -> None:
        """利用目的 absent → WARN pipa_purpose_missing (lines 212-221)."""
        snap = _snap(handles_personal_data=True)
        text = "個人情報を処理する。第三者提供はしない。委託先を管理する。"
        findings = self.checker._check_personal_data(snap, text)
        codes = [f.code for f in findings]
        assert "pipa_purpose_missing" in codes

    def test_third_party_missing_fires_warn(self) -> None:
        """第三者提供/委託先/再委託 absent → WARN pipa_third_party_missing (lines 222-231)."""
        snap = _snap(handles_personal_data=True)
        text = "個人情報を利用する。利用目的は業務遂行とする。"
        findings = self.checker._check_personal_data(snap, text)
        codes = [f.code for f in findings]
        assert "pipa_third_party_missing" in codes

    def test_both_clauses_missing_fires_two_warns(self) -> None:
        """Both clauses absent → two WARN findings."""
        snap = _snap(handles_personal_data=True)
        text = "個人情報を扱う業務委託。"
        findings = self.checker._check_personal_data(snap, text)
        assert len(findings) == 2
        assert all(f.severity == ComplianceSeverity.WARN for f in findings)

    def test_itaku_keyword_present_passes_third_party_check(self) -> None:
        """委託先 is one of the alternatives that satisfies the third-party check."""
        snap = _snap(handles_personal_data=True)
        text = "利用目的を特定する。委託先は○○社とする。"
        findings = self.checker._check_personal_data(snap, text)
        codes = [f.code for f in findings]
        assert "pipa_third_party_missing" not in codes


# ---------------------------------------------------------------------------
# _check_disguised_contracting
# ---------------------------------------------------------------------------


class TestCheckDisguisedContracting:
    def setup_method(self) -> None:
        self.checker = ComplianceChecker()

    def test_non_itaku_type_returns_empty(self) -> None:
        """UKEOI type skips the rule (lines 237-238)."""
        snap = _snap(contract_type=ContractType.UKEOI)
        findings = self.checker._check_disguised_contracting(snap, "指揮命令を行う。")
        assert findings == []

    def test_itaku_no_risk_phrases_returns_empty(self) -> None:
        """ITAKU contract without risk phrases → no finding (lines 241-242)."""
        snap = _snap(contract_type=ContractType.ITAKU)
        findings = self.checker._check_disguised_contracting(
            snap, "業務成果物の納品について定める。"
        )
        assert findings == []

    def test_itaku_with_shiki_meirei_fires_warn(self) -> None:
        """指揮命令 in ITAKU contract → WARN finding (lines 243-255)."""
        snap = _snap(contract_type=ContractType.ITAKU)
        findings = self.checker._check_disguised_contracting(snap, "指揮命令に従い作業する。")
        assert len(findings) == 1
        assert findings[0].code == "disguised_subcontracting_risk"
        assert findings[0].severity == ComplianceSeverity.WARN
        assert "指揮命令" in findings[0].matched_keywords

    def test_itaku_string_type_also_fires(self) -> None:
        """contract_type '委託' (string) is treated as ITAKU."""
        snap = _snap(contract_type="委託")
        findings = self.checker._check_disguised_contracting(snap, "始業時間は9時とする。")
        assert len(findings) == 1

    def test_multiple_risk_phrases_all_captured(self) -> None:
        """Multiple risk phrases are all listed in matched_keywords."""
        snap = _snap(contract_type=ContractType.ITAKU)
        text = "指揮命令を行い、始業時間・終業時間を管理し、勤怠管理を実施する。"
        findings = self.checker._check_disguised_contracting(snap, text)
        assert len(findings) == 1
        assert len(findings[0].matched_keywords) == 4


# ---------------------------------------------------------------------------
# _check_public_work
# ---------------------------------------------------------------------------


class TestCheckPublicWork:
    def setup_method(self) -> None:
        self.checker = ComplianceChecker()

    def test_non_public_work_returns_empty(self) -> None:
        """is_public_work=False skips the rule (line 261-262)."""
        snap = _snap(is_public_work=False)
        findings = self.checker._check_public_work(snap, "施工体制台帳について。")
        assert findings == []

    def test_public_work_all_present_returns_empty(self) -> None:
        """Both 施工体制台帳 and 談合 present → no findings."""
        snap = _snap(is_public_work=True)
        findings = self.checker._check_public_work(snap, "施工体制台帳を整備する。談合を禁止する。")
        assert findings == []

    def test_public_work_missing_sekou_fires_warn(self) -> None:
        """施工体制台帳 absent → WARN construction_law_24_8 (lines 264-273)."""
        snap = _snap(is_public_work=True)
        findings = self.checker._check_public_work(snap, "談合を禁止する。")
        codes = [f.code for f in findings]
        assert "construction_law_24_8" in codes

    def test_public_work_missing_dangou_fires_warn(self) -> None:
        """談合 absent → WARN public_collusion_clause (lines 274-283)."""
        snap = _snap(is_public_work=True)
        findings = self.checker._check_public_work(snap, "施工体制台帳を整備する。")
        codes = [f.code for f in findings]
        assert "public_collusion_clause" in codes

    def test_public_work_both_missing_fires_two_warns(self) -> None:
        """Both missing → two WARN findings."""
        snap = _snap(is_public_work=True)
        findings = self.checker._check_public_work(snap, "公共工事の契約書。")
        assert len(findings) == 2
        assert all(f.severity == ComplianceSeverity.WARN for f in findings)


# ---------------------------------------------------------------------------
# ComplianceChecker.check (integration via async)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCheckerCheckIntegration:
    def setup_method(self) -> None:
        self.checker = ComplianceChecker()

    async def test_empty_text_other_type_returns_antisocial_and_ebook_findings(self) -> None:
        """Empty text with OTHER type triggers antisocial + ebook findings."""
        snap = _snap(text="", contract_type=ContractType.OTHER)
        findings = await self.checker.check(snap)
        codes = [f.code for f in findings]
        assert "antisocial_clause_missing" in codes
        assert "electronic_books_act_hint" in codes

    async def test_ukeoi_missing_keywords_fires_construction_law_19(self) -> None:
        snap = _snap(text="反社会的勢力排除。電子契約。", contract_type=ContractType.UKEOI)
        findings = await self.checker.check(snap)
        codes = [f.code for f in findings]
        assert "construction_law_19" in codes

    async def test_dict_input_is_accepted(self) -> None:
        """check() accepts a plain dict via _coerce."""
        data = {
            "text": _KEN19_FULL_TEXT + " 反社会的勢力 電子契約",
            "contract_type": ContractType.UKEOI,
        }
        findings = await self.checker.check(data)
        codes = [f.code for f in findings]
        assert "construction_law_19" not in codes
        assert "antisocial_clause_missing" not in codes

    async def test_public_work_snap_triggers_public_work_rules(self) -> None:
        text = _KEN19_FULL_TEXT + " 反社会的勢力 電子契約"
        snap = _snap(text=text, contract_type=ContractType.UKEOI, is_public_work=True)
        findings = await self.checker.check(snap)
        codes = [f.code for f in findings]
        assert "construction_law_24_8" in codes
        assert "public_collusion_clause" in codes

    async def test_returns_list_of_compliance_findings(self) -> None:
        snap = _snap(text="", contract_type=ContractType.OTHER)
        findings = await self.checker.check(snap)
        assert all(isinstance(f, ComplianceFinding) for f in findings)


# ---------------------------------------------------------------------------
# 取適法（中小受託取引適正化法）— P0-1
# ---------------------------------------------------------------------------


class TestToritekihou:
    def setup_method(self) -> None:
        self.checker = ComplianceChecker()

    def test_employee_based_applicability(self) -> None:
        """従業員数基準だけで適用判定できる（資本金なしでも）。"""
        snap = _snap(
            our_employees=400,
            counterparty_employees=120,
            transaction_kind="manufacturing",
            order_date="2026-03-01",
        )
        findings = self.checker._check_toritekihou(snap, "60日以内に支払う。")
        codes = [f.code for f in findings]
        assert "toritekihou_applies" in codes
        assert "subcontract_act_applies" not in codes

    def test_service_kind_uses_100_employee_threshold(self) -> None:
        """役務提供委託は従業員 100 人超で委託事業者となる。"""
        snap = _snap(
            our_employees=150,
            counterparty_employees=50,
            transaction_kind="service",
            order_date="2026-03-01",
        )
        findings = self.checker._check_toritekihou(snap, "60日以内に支払う。")
        codes = [f.code for f in findings]
        assert "toritekihou_applies" in codes

    def test_order_date_switch_to_new_law(self) -> None:
        """2026-01-01 以降発注は取適法、以前は旧下請法。"""
        snap = _snap(
            our_capital_jpy=400_000_000,
            counterparty_capital_jpy=100_000_000,
            transaction_kind="manufacturing",
            order_date="2026-01-01",
        )
        findings = self.checker._check_toritekihou(snap, "60日以内に支払う。")
        codes = [f.code for f in findings]
        assert "toritekihou_applies" in codes
        assert "toritekihou_payment_terms" not in codes

        snap_old = _snap(
            our_capital_jpy=400_000_000,
            counterparty_capital_jpy=100_000_000,
            transaction_kind="manufacturing",
            order_date="2025-12-31",
        )
        findings_old = self.checker._check_toritekihou(snap_old, "60日以内に支払う。")
        codes_old = [f.code for f in findings_old]
        assert "subcontract_act_applies" in codes_old
        assert "toritekihou_applies" not in codes_old

    def test_payment_date_exceeding_60_days_fires_block(self) -> None:
        from datetime import date

        snap = _snap(
            our_capital_jpy=400_000_000,
            counterparty_capital_jpy=100_000_000,
            transaction_kind="manufacturing",
            order_date=date(2026, 3, 1),
            receipt_date=date(2026, 3, 10),
            payment_date=date(2026, 5, 30),  # 81 days later
        )
        findings = self.checker._check_toritekihou(snap, "60日以内に支払う。")
        codes = [f.code for f in findings]
        assert "toritekihou_payment_late" in codes
        assert (
            next(f for f in findings if f.code == "toritekihou_payment_late").severity
            == ComplianceSeverity.BLOCK
        )

    def test_promissory_note_prohibited(self) -> None:
        snap = _snap(
            our_capital_jpy=400_000_000,
            counterparty_capital_jpy=100_000_000,
            transaction_kind="manufacturing",
            order_date="2026-03-01",
        )
        findings = self.checker._check_toritekihou(snap, "支払は手形にて行う。")
        codes = [f.code for f in findings]
        assert "toritekihou_promissory_note" in codes

    def test_unilateral_pricing_fires_block(self) -> None:
        snap = _snap(
            our_capital_jpy=400_000_000,
            counterparty_capital_jpy=100_000_000,
            transaction_kind="manufacturing",
            order_date="2026-03-01",
        )
        findings = self.checker._check_toritekihou(snap, "代金は甲が一方的に定める。")
        codes = [f.code for f in findings]
        assert "toritekihou_unilateral_pricing" in codes

    def test_specific_transport(self) -> None:
        snap = _snap(
            our_capital_jpy=400_000_000,
            counterparty_capital_jpy=100_000_000,
            transaction_kind="transport",
            order_date="2026-03-01",
        )
        findings = self.checker._check_toritekihou(snap, "60日以内に支払う。")
        codes = [f.code for f in findings]
        assert "toritekihou_specific_transport" in codes

    def test_unknown_kind_flags_profile(self) -> None:
        """取引類型不明でも資本金・従業員から対象となり得る場合は通知する。"""
        snap = _snap(our_capital_jpy=400_000_000, counterparty_capital_jpy=100_000_000)
        findings = self.checker._check_toritekihou(snap, "60日以内に支払う。")
        codes = [f.code for f in findings]
        assert "toritekihou_transaction_kind_unknown" in codes


# ---------------------------------------------------------------------------
# 改正建設業法・労務費基準（P0-2）
# ---------------------------------------------------------------------------


class TestLaborCostRules:
    def setup_method(self) -> None:
        self.checker = ComplianceChecker()

    def test_ukeoi_missing_breakdown_fires_warn(self) -> None:
        snap = _snap(contract_type=ContractType.UKEOI)
        findings = self.checker._check_labor_cost(snap, "工事内容 請負代金 工期。")
        codes = [f.code for f in findings]
        assert "construction_law_labor_breakdown" in codes

    def test_full_breakdown_prevents_warn(self) -> None:
        text = "労務費 材料費 安全衛生経費 法定福利費 建退共 スライド条項"
        snap = _snap(contract_type=ContractType.UKEOI)
        findings = self.checker._check_labor_cost(snap, text)
        codes = [f.code for f in findings]
        assert "construction_law_labor_breakdown" not in codes

    def test_abnormally_low_bid_detected(self) -> None:
        snap = _snap(contract_type=ContractType.UKEOI)
        findings = self.checker._check_labor_cost(snap, "著しく低い見積りに基づく価格。")
        codes = [f.code for f in findings]
        assert "construction_law_abnormally_low_bid" in codes

    def test_pre_notification_missing_when_material_costs_mentioned(self) -> None:
        snap = _snap(contract_type=ContractType.UKEOI)
        findings = self.checker._check_labor_cost(snap, "資材価格の高騰が懸念される。")
        codes = [f.code for f in findings]
        assert "construction_law_pre_notification" in codes

    def test_price_revision_clause_warn_for_public_work(self) -> None:
        snap = _snap(contract_type=ContractType.UKEOI, is_public_work=True)
        findings = self.checker._check_labor_cost(snap, "工事内容 請負代金 工期。")
        codes = [f.code for f in findings]
        assert "construction_law_price_revision_clause" in codes


# ---------------------------------------------------------------------------
# 建設業法 19 条拡充（P0-3）
# ---------------------------------------------------------------------------


class TestKenpou19Expanded:
    def setup_method(self) -> None:
        self.checker = ComplianceChecker()

    def test_cross_document_scan_satisfies_required_items(self) -> None:
        """本文にない項目でも約款・特記仕様書にあれば充足とする。"""
        main_text = "工事内容 請負代金 工期 引渡 前金払 部分払 出来高払 設計変更"
        documents = {
            "約款": "第三者損害 天災 価格変動 スライド 瑕疵担保 紛争解決",
        }
        snap = _snap(
            text=main_text,
            contract_type=ContractType.UKEOI,
            documents=documents,
        )
        findings = self.checker._check_kenpou_19(snap, main_text)
        codes = [f.code for f in findings]
        assert "construction_law_19" not in codes

    def test_amount_mismatch_fires_warn(self) -> None:
        snap = _snap(
            contract_type=ContractType.UKEOI,
            amount_jpy=100_000_000,
        )
        text = "請負代金は 50,000,000円 とする。"
        findings = self.checker._check_kenpou_19(snap, text)
        codes = [f.code for f in findings]
        assert "construction_law_19_amount_mismatch" in codes

    def test_amount_unverifiable_fires_warn(self) -> None:
        snap = _snap(
            contract_type=ContractType.UKEOI,
            amount_jpy=100_000_000,
        )
        findings = self.checker._check_kenpou_19(snap, "請負代金は別途協議とする。")
        codes = [f.code for f in findings]
        assert "construction_law_19_amount_unverifiable" in codes

    def test_reversed_dates_fires_warn(self) -> None:
        text = "着工 2027年4月1日。完成 2026年3月31日。"
        snap = _snap(contract_type=ContractType.UKEOI)
        findings = self.checker._check_kenpou_19(snap, text)
        codes = [f.code for f in findings]
        assert "construction_law_19_date_order" in codes
