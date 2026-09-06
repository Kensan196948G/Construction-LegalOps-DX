"""労務費コミットメント・見積様式生成の単体テスト（#27/#28）."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.exceptions import ConflictError, ValidationError
from app.models.contract import Contract
from app.models.department import Department
from app.models.user import User
from app.services import estimate_form_service, labor_commitment_service


async def _seed_user_and_contract(db_session) -> tuple[int, int]:
    dept = Department(code=f"D-{uuid4().hex[:8]}", name="工事部")
    db_session.add(dept)
    await db_session.flush()
    user = User(
        entra_oid=uuid4(),
        email=f"{uuid4().hex[:10]}@test.example",
        display_name="作成者",
        role="reviewer",
        department_id=dept.id,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    contract = Contract(
        contract_no=f"CTR-LC-{uuid4().hex[:6]}",
        title="コミットメントテスト契約",
        counterparty="テスト（デモ）",
        contract_type="工事請負契約",
        amount=10_000_000,
        department_id=dept.id,
        drafter_id=user.id,
        status="approved",
    )
    db_session.add(contract)
    await db_session.flush()
    return int(user.id), int(contract.id)

async def test_commitment_lifecycle(db_session) -> None:
    """#28: 登録（active）→ fulfilled / violated（409 保護）."""
    uid, contract_id = await _seed_user_and_contract(db_session)

    row = await labor_commitment_service.create_commitment(
        db_session,
        actor_id=uid,
        contract_id=contract_id,
        commitment_type="wage_payment",
        title="賃金支払確約（テスト）",
        statement="下請労働者への賃金を適時に支払う。",
    )
    assert row.status == "active"

    fulfilled = await labor_commitment_service.verify_commitment(
        db_session,
        commitment_id=row.id,
        actor_id=uid,
        outcome="fulfilled",
        verify_note="支払記録を確認（テスト）",
    )
    assert fulfilled.status == "fulfilled"
    assert fulfilled.verified_at is not None

    with pytest.raises(ConflictError):
        await labor_commitment_service.verify_commitment(
            db_session, commitment_id=row.id, actor_id=uid, outcome="violated"
        )

    with pytest.raises(ValidationError):
        await labor_commitment_service.create_commitment(
            db_session,
            actor_id=uid,
            contract_id=contract_id,
            commitment_type="bogus",
            title="不正（テスト）",
        )
    with pytest.raises(ValidationError):
        await labor_commitment_service.verify_commitment(
            db_session, commitment_id=row.id, actor_id=uid, outcome="active"
        )

def test_estimate_form_generation() -> None:
    """#27: 総括表・明細表・内訳整合（決定論的）."""
    result = estimate_form_service.generate_estimate_form(
        title="◯◯工事見積書（テスト）",
        contractor_name="デモ建設（テスト）",
        items=[
            {
                "work_type": "土木",
                "spec": "掘削",
                "quantity": 100,
                "unit": "m3",
                "unit_price_jpy": 5_000,
                "labor_cost_jpy": 200_000,
                "material_cost_jpy": 150_000,
                "safety_cost_jpy": 75_000,
                "welfare_cost_jpy": 75_000,
            },
            {
                "work_type": "舗装",
                "spec": "表層",
                "quantity": 50,
                "unit": "m2",
                "unit_price_jpy": 8_000,
                "labor_cost_jpy": 100_000,
                "material_cost_jpy": 200_000,
                "safety_cost_jpy": 50_000,
                "welfare_cost_jpy": 50_000,
            },
        ],
        tax_rate=0.10,
    )
    assert result["subtotal_jpy"] == 900_000  # 500,000 + 400,000
    assert result["tax_jpy"] == 90_000
    assert result["grand_total_jpy"] == 990_000
    assert result["labor_cost_jpy"] == 300_000
    assert abs(result["labor_ratio"] - round(300_000 / 900_000, 4)) < 0.0001
    assert "【見積書（総括表）】" in result["formatted_text"]
    assert "【明細表】" in result["formatted_text"]
    assert len(result["items"]) == 2

def test_estimate_form_validation() -> None:
    """内訳不一致・空明細・税率範囲外 422."""
    with pytest.raises(ValidationError):
        estimate_form_service.generate_estimate_form(
            title="x",
            contractor_name="y",
            items=[
                {
                    "work_type": "土木",
                    "quantity": 1,
                    "unit_price_jpy": 1_000,
                    "labor_cost_jpy": 999,  # 内訳不一致（金額 1,000）
                }
            ],
        )
    with pytest.raises(ValidationError):
        estimate_form_service.generate_estimate_form(
            title="x", contractor_name="y", items=[]
        )
    with pytest.raises(ValidationError):
        estimate_form_service.generate_estimate_form(
            title="x",
            contractor_name="y",
            items=[{"work_type": "土木", "quantity": 1, "unit_price_jpy": 1_000}],
            tax_rate=1.5,
        )
