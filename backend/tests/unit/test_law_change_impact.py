"""Unit tests for app.services.law_change_impact (法令改正影響分析)."""

from __future__ import annotations

from datetime import date
from uuid import UUID

import pytest

from app.models.contract import Contract
from app.models.department import Department
from app.models.user import User
from app.services.law_change_impact import analyze, load_manifests


@pytest.mark.asyncio
async def _seed_contract(
    db_session,
    *,
    contract_no: str,
    order_date: date,
    our_employees: int | None = None,
    receipt_date: date | None = None,
    payment_date: date | None = None,
    contract_type: str = "請負",
) -> Contract:
    dept = Department(code=f"D-{contract_no}", name="法務部")
    db_session.add(dept)
    await db_session.flush()
    user = User(
        entra_oid=UUID("00000000-0000-0000-0000-000000000001"),
        email=f"{contract_no}@example.com",
        display_name="テスト",
        department_id=dept.id,
        role="admin",
    )
    db_session.add(user)
    await db_session.flush()
    contract = Contract(
        contract_no=contract_no,
        title=f"契約 {contract_no}",
        counterparty="株式会社テスト",
        contract_type=contract_type,
        amount=1_000_000,
        start_date=order_date,
        department_id=dept.id,
        drafter_id=user.id,
        order_date=order_date,
        our_employees=our_employees,
        receipt_date=receipt_date,
        payment_date=payment_date,
        extra_metadata={},
    )
    db_session.add(contract)
    await db_session.flush()
    return contract


class TestManifests:
    def test_manifests_load(self) -> None:
        manifests = load_manifests()
        assert len(manifests) >= 2
        ids = {m["change_id"] for m in manifests}
        assert "toritekihou-2026-01-01" in ids
        assert "construction-business-act-2025-12-01" in ids

    def test_manifest_has_primary_sources(self) -> None:
        for manifest in load_manifests():
            assert manifest["primary_sources"]
            assert manifest["effective_date"]
            assert manifest["affected_rule_ids"]


class TestAnalyze:
    @pytest.mark.asyncio
    async def test_old_contract_with_large_workforce_is_impacted(
        self, db_session
    ) -> None:
        await _seed_contract(
            db_session,
            contract_no="C-OLD-001",
            order_date=date(2025, 6, 1),
            our_employees=150,
        )
        result = await analyze(db_session)
        assert result["contracts_checked"] == 1
        assert result["impacted_count"] >= 1
        reasons = result["impacted_contracts"][0]["impact_reasons"]
        assert any("従業員数基準" in r for r in reasons)

    @pytest.mark.asyncio
    async def test_new_contract_is_not_impacted_by_switch(self, db_session) -> None:
        await _seed_contract(
            db_session,
            contract_no="C-NEW-001",
            order_date=date(2026, 3, 1),
            our_employees=150,
        )
        result = await analyze(db_session)
        reasons = (
            result["impacted_contracts"][0]["impact_reasons"]
            if result["impacted_contracts"]
            else []
        )
        assert all("従業員数基準" not in r for r in reasons)

    @pytest.mark.asyncio
    async def test_payment_over_60_days_is_impacted(self, db_session) -> None:
        await _seed_contract(
            db_session,
            contract_no="C-PAY-001",
            order_date=date(2025, 6, 1),
            receipt_date=date(2025, 7, 1),
            payment_date=date(2025, 10, 1),
        )
        result = await analyze(db_session)
        assert result["impacted_count"] >= 1
        reasons = result["impacted_contracts"][0]["impact_reasons"]
        assert any("60 日超" in r for r in reasons)

    @pytest.mark.asyncio
    async def test_response_includes_manifest_details(self, db_session) -> None:
        result = await analyze(db_session)
        assert result["law_change_details"]
        assert result["law_changes"]
