"""協力会社コンプライアンス台帳のユニットテスト（リスクスコア判定）. """

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import partner_service
from app.services.partner_service import assess_risk


def _actor(user_id: int = 1) -> MagicMock:
    actor = MagicMock()
    actor.role = "admin"
    actor.db_id = user_id
    return actor


def _session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock(return_value=None)
    session.refresh = AsyncMock(side_effect=lambda obj: obj)
    return session


def _partner(**kwargs) -> MagicMock:
    p = MagicMock()
    p.id = kwargs.get("id", 1)
    p.name = kwargs.get("name", "テスト株式会社")
    p.partner_type = kwargs.get("partner_type", "下請")
    p.permit_expiry = kwargs.get("permit_expiry")
    p.social_insurance_joined = kwargs.get("social_insurance_joined")
    p.ccus_registered = kwargs.get("ccus_registered")
    p.anti_social_check = kwargs.get("anti_social_check", "confirmed")
    p.bankruptcy_risk = kwargs.get("bankruptcy_risk", "unknown")
    p.risk_level = kwargs.get("risk_level", "low")
    p.deleted_at = kwargs.get("deleted_at")
    return p


def test_risk_unconfirmed_antisocial_is_high():
    level, reasons = assess_risk(_partner(anti_social_check="unconfirmed"))
    assert level == "high"
    assert any(r["code"] == "antisocial_unconfirmed" for r in reasons)


def test_risk_expired_permit_is_critical():
    level, reasons = assess_risk(_partner(permit_expiry=date.today() - timedelta(days=5)))
    assert level == "critical"
    assert any(r["code"] == "permit_expired" for r in reasons)


def test_risk_bankruptcy_high_is_critical():
    level, _ = assess_risk(_partner(bankruptcy_risk="high"))
    assert level == "critical"


def test_risk_expiring_90_days_is_high():
    level, _ = assess_risk(_partner(permit_expiry=date.today() + timedelta(days=30)))
    assert level == "high"


def test_risk_no_social_insurance_is_high():
    level, _ = assess_risk(_partner(social_insurance_joined=False))
    assert level == "high"


def test_risk_low_when_healthy():
    level, reasons = assess_risk(
        _partner(
            permit_expiry=date.today() + timedelta(days=365),
            social_insurance_joined=True,
            ccus_registered=True,
        )
    )
    assert level == "low"
    assert reasons == []


@pytest.mark.asyncio
async def test_create_partner_applies_risk_score():
    session = _session()
    actor = _actor()
    partner = await partner_service.create_partner(
        session,
        actor=actor,
        data={
            "name": "テスト土木株式会社",
            "partner_type": "下請",
            "anti_social_check": "unconfirmed",
        },
    )
    session.add.assert_called_once()
    assert partner.risk_level == "high"
    assert partner.created_by == 1


@pytest.mark.asyncio
async def test_summary_counts():
    session = _session()
    rows = [
        _partner(id=1, anti_social_check="unconfirmed"),
        _partner(id=2, permit_expiry=date.today() + timedelta(days=30)),
        _partner(id=3, permit_expiry=date.today() - timedelta(days=1)),
        _partner(id=4, social_insurance_joined=False),
        _partner(id=5),
    ]
    result_obj = MagicMock()
    result_obj.scalars.return_value.all.return_value = rows
    session.execute = AsyncMock(return_value=result_obj)

    result = await partner_service.summary(session)
    assert result["total"] == 5
    assert result["antisocial_unconfirmed"] == 1
    assert result["permit_expiring_within_90d"] == 1
    assert result["by_risk_level"]["high"] == 3
    assert result["by_risk_level"]["critical"] == 1
    assert result["by_risk_level"]["low"] == 1
