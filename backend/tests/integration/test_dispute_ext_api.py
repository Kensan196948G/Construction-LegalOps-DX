"""紛争・クレーム管理高度化 API の統合テスト（ロードマップ #97〜#112 / Issue #121）.

``dispute_ext.router`` は ``app/api/v1/__init__.py`` へ登録済み
（``include_router(dispute_ext.router)``）。本テストはそれとは別に、
このルーターのみをマウントした最小の FastAPI アプリで疎通確認する
（他ドメインのルーターと混在しない最小構成で確認するため）。
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import date, timedelta
from typing import Any
from uuid import uuid4

import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.dispute_ext import router as dispute_ext_router
from app.core.exceptions import register_exception_handlers
from app.db.session import get_db
from app.deps import CurrentUser, get_current_user
from app.models.dispute import Dispute


def _fake_user(role: str = "admin") -> CurrentUser:
    return CurrentUser(
        id=f"{role}-user@test.local",
        email=f"{role}-user@test.local",
        role=role,
        department_ids=(),
        raw_claims={},
        db_id=None,
    )


@pytest_asyncio.fixture()
async def dispute_ext_client(db_session: Any) -> AsyncGenerator[AsyncClient, None]:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(dispute_ext_router, prefix="/api/v1")

    async def _override_get_db() -> AsyncGenerator[Any, None]:
        yield db_session

    async def _override_current_user() -> CurrentUser:
        return _fake_user("admin")

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


async def _seed_dispute(db_session: Any, **overrides: Any) -> Dispute:
    defaults: dict[str, Any] = {
        "dispute_no": f"D-{uuid4().hex[:10].upper()}",
        "dispute_type": "delay",
        "title": "統合テスト紛争案件",
        "status": "open",
        "priority": "中",
        "counterparty": "統合テスト相手方",
    }
    defaults.update(overrides)
    row = Dispute(**defaults)
    db_session.add(row)
    await db_session.flush()
    await db_session.refresh(row)
    return row


async def test_claim_notice_and_notice_deadline_flow(
    dispute_ext_client: AsyncClient, db_session: Any
) -> None:
    dispute = await _seed_dispute(db_session, dispute_type="claim")
    base = f"/api/v1/disputes/{dispute.id}"

    r_notice = await dispute_ext_client.post(
        f"{base}/claim-notice",
        json={"sender_name": "統合テスト元請株式会社"},
    )
    assert r_notice.status_code == 200, r_notice.text
    body = r_notice.json()
    assert dispute.dispute_no in body["formatted_text"]

    r_judge = await dispute_ext_client.post(
        f"{base}/notice-deadline/auto-judge",
        json={"event_date": "2026-01-01", "apply": True},
    )
    assert r_judge.status_code == 200, r_judge.text
    judged = r_judge.json()
    assert judged["notice_period_days"] == 14  # claim の既定
    assert judged["notice_deadline"] == "2026-01-15"
    assert judged["applied"] is True


async def test_delay_event_lifecycle_and_summary(
    dispute_ext_client: AsyncClient, db_session: Any
) -> None:
    dispute = await _seed_dispute(db_session)
    base = f"/api/v1/disputes/{dispute.id}"

    r_create = await dispute_ext_client.post(
        f"{base}/delay-events",
        json={
            "cause_category": "owner_caused",
            "title": "発注者指示による遅延",
            "occurred_from": "2026-01-01",
            "occurred_to": "2026-01-10",
            "delay_days": 9,
            "additional_cost_jpy": 200_000,
            "eot_days_requested": 9,
        },
    )
    assert r_create.status_code == 201, r_create.text
    event = r_create.json()
    assert event["eot_status"] == "pending"

    r_list = await dispute_ext_client.get(f"{base}/delay-events")
    assert r_list.status_code == 200
    assert len(r_list.json()) == 1

    r_summary = await dispute_ext_client.get(f"{base}/delay-events/summary")
    assert r_summary.status_code == 200
    summary = r_summary.json()
    assert summary["total_delay_days"] == 9
    assert summary["total_additional_cost_jpy"] == 200_000

    r_eot = await dispute_ext_client.patch(
        f"/api/v1/disputes/delay-events/{event['id']}/eot",
        json={"eot_status": "approved", "eot_days_granted": 9},
    )
    assert r_eot.status_code == 200, r_eot.text
    assert r_eot.json()["eot_status"] == "approved"

    # 二重判定は 409
    r_eot_again = await dispute_ext_client.patch(
        f"/api/v1/disputes/delay-events/{event['id']}/eot",
        json={"eot_status": "rejected"},
    )
    assert r_eot_again.status_code == 409


async def test_time_bar_alerts_endpoint(dispute_ext_client: AsyncClient, db_session: Any) -> None:
    soon = await _seed_dispute(
        db_session,
        status="open",
        statute_limitations_date=date.today() + timedelta(days=10),
    )
    await _seed_dispute(db_session, status="open")  # 期限なし → アラート対象外

    r = await dispute_ext_client.get("/api/v1/disputes/alerts/time-bar")
    assert r.status_code == 200
    ids = [a["dispute_id"] for a in r.json()]
    assert soon.id in ids

    r_single = await dispute_ext_client.get(f"/api/v1/disputes/{soon.id}/time-bar")
    assert r_single.status_code == 200
    assert r_single.json()["severity"] in ("critical", "warning")


async def test_evidence_score_and_chronology(
    dispute_ext_client: AsyncClient, db_session: Any
) -> None:
    dispute = await _seed_dispute(db_session, dispute_type="claim")
    base = f"/api/v1/disputes/{dispute.id}"

    r_score = await dispute_ext_client.get(f"{base}/evidence-score")
    assert r_score.status_code == 200
    score_body = r_score.json()
    assert score_body["score"] == 0
    assert set(score_body["missing_types"]) == {"contract", "email", "daily_report"}

    await dispute_ext_client.post(
        f"{base}/delay-events",
        json={
            "cause_category": "weather",
            "title": "台風による遅延",
            "occurred_from": "2026-01-05",
        },
    )
    r_chronology = await dispute_ext_client.get(f"{base}/chronology")
    assert r_chronology.status_code == 200
    entries = r_chronology.json()
    assert len(entries) == 1
    assert entries[0]["source_type"].startswith("delay_event:")


async def test_arguments_matrix_flow(dispute_ext_client: AsyncClient, db_session: Any) -> None:
    dispute = await _seed_dispute(db_session)
    base = f"/api/v1/disputes/{dispute.id}"

    r_create = await dispute_ext_client.post(
        f"{base}/arguments",
        json={
            "issue_no": 1,
            "issue_title": "遅延の帰責事由",
            "party": "ours",
            "stance": "claim",
            "content": "発注者側の指示遅延に起因する。",
        },
    )
    assert r_create.status_code == 201, r_create.text

    r_list = await dispute_ext_client.get(f"{base}/arguments")
    assert r_list.status_code == 200
    assert len(r_list.json()) == 1


async def test_settlement_options_flow(dispute_ext_client: AsyncClient, db_session: Any) -> None:
    dispute = await _seed_dispute(db_session)
    base = f"/api/v1/disputes/{dispute.id}"

    r_low = await dispute_ext_client.post(
        f"{base}/settlement-options",
        json={
            "option_no": 1,
            "title": "低額和解",
            "settlement_amount_jpy": 1_000_000,
            "probability_score": 90,
        },
    )
    r_high = await dispute_ext_client.post(
        f"{base}/settlement-options",
        json={
            "option_no": 2,
            "title": "訴訟",
            "settlement_amount_jpy": 5_000_000,
            "probability_score": 20,
        },
    )
    assert r_low.status_code == 201
    assert r_high.status_code == 201

    r_compare = await dispute_ext_client.get(f"{base}/settlement-options/compare")
    assert r_compare.status_code == 200
    ranked = r_compare.json()
    # 期待値: 低額和解 = 1,000,000×90% = 900,000 / 訴訟 = 5,000,000×20% = 1,000,000
    assert ranked[0]["title"] == "訴訟"
    assert ranked[0]["expected_value_jpy"] == 1_000_000
    assert ranked[0]["recommended"] is True

    option_id = r_low.json()["id"]
    r_update = await dispute_ext_client.patch(
        f"/api/v1/disputes/settlement-options/{option_id}",
        json={"status": "accepted"},
    )
    assert r_update.status_code == 200
    assert r_update.json()["status"] == "accepted"


async def test_proceeding_stages_flow(dispute_ext_client: AsyncClient, db_session: Any) -> None:
    dispute = await _seed_dispute(db_session)
    base = f"/api/v1/disputes/{dispute.id}"

    r1 = await dispute_ext_client.post(
        f"{base}/stages", json={"stage": "negotiation", "started_at": "2026-01-01"}
    )
    assert r1.status_code == 201
    r2 = await dispute_ext_client.post(
        f"{base}/stages", json={"stage": "mediation", "started_at": "2026-02-01"}
    )
    assert r2.status_code == 201

    r_list = await dispute_ext_client.get(f"{base}/stages")
    assert r_list.status_code == 200
    stages = r_list.json()
    assert len(stages) == 2
    assert stages[0]["status"] == "completed"
    assert stages[1]["status"] == "active"
