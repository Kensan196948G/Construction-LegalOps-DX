"""独禁法・入札談合コンプライアンス API の疎通テスト（Issue #122）.

``app.api.v1.antitrust.router`` は ``app/api/v1/__init__.py`` へ登録済み
（``include_router(antitrust.router)``）なので、``tests/integration/conftest.py``
の共有 ``client`` フィクスチャからも同じエンドポイントへ到達できる。

本テストは、それとは別に router を単体でマウントした自己完結の FastAPI
インスタンスに対して認証・認可・スキーマ・監査ログ連携を検証する
（他ドメインのルーターと混在しない最小構成で確認するため）。
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator
from typing import Any
from uuid import uuid4

import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.antitrust import router as antitrust_router
from app.core.exceptions import register_exception_handlers
from app.db.session import get_db
from app.db.test_session import create_all_for_tests
from app.deps import CurrentUser, get_current_user
from app.models.contract import Contract
from app.models.department import Department
from app.models.user import User
from app.services.antitrust_service import CONSULTATION_DISCLAIMER


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(antitrust_router, prefix="/api/v1")
    # AppError (Unauthorized/Forbidden/NotFound 等) を RFC 7807 応答へ変換する
    # ハンドラは app.main で登録される。ここでは router を単体マウントする
    # 自己完結テストのため、同じハンドラを明示的に登録する。
    register_exception_handlers(app)
    return app


@pytest_asyncio.fixture()
async def antitrust_engine() -> AsyncGenerator[Any, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True, echo=False)
    await create_all_for_tests(engine)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture()
async def seeded_ids(antitrust_engine: Any) -> tuple[int, int]:
    """Seed a department/user/contract row and return ``(user_id, contract_id)``."""
    Session = async_sessionmaker(bind=antitrust_engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as session:
        dept = Department(code=f"D-{uuid4().hex[:8]}", name="法務部")
        session.add(dept)
        await session.flush()
        user = User(
            entra_oid=uuid4(),
            email=f"{uuid4().hex[:10]}@test.local",
            display_name="テストユーザー",
            role="admin",
            department_id=dept.id,
            is_active=True,
        )
        session.add(user)
        await session.flush()
        contract = Contract(
            contract_no=f"CTR-ATAPI-{uuid4().hex[:6]}",
            title="独禁法 API テスト契約",
            counterparty="テスト（デモ）",
            contract_type="工事請負契約",
            amount=10_000_000,
            department_id=dept.id,
            drafter_id=user.id,
            status="approved",
        )
        session.add(contract)
        await session.flush()
        await session.commit()
        return int(user.id), int(contract.id)


@pytest_asyncio.fixture()
async def antitrust_client(
    antitrust_engine: Any, seeded_ids: tuple[int, int]
) -> AsyncGenerator[AsyncClient, None]:
    user_id, _contract_id = seeded_ids
    app = _make_app()
    Session = async_sessionmaker(bind=antitrust_engine, expire_on_commit=False, class_=AsyncSession)

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        session = Session()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def _override_get_current_user() -> CurrentUser:
        return CurrentUser(
            id="antitrust-tester@example.com",
            email="antitrust-tester@example.com",
            role="admin",
            department_ids=(),
            raw_claims={},
            db_id=user_id,
        )

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# #113/#114 チェック
# ---------------------------------------------------------------------------


async def test_run_check_and_get(antitrust_client: AsyncClient) -> None:
    r = await antitrust_client.post(
        "/api/v1/antitrust/checks",
        json={
            "check_type": "bid_rigging",
            "subject": "API テスト入札",
            "context": {
                "is_public_bid": True,
                "contacted_competitors": True,
                "procuring_agency_involvement": True,
            },
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["check_no"].startswith("ATC-")
    assert body["severity"] == "block"
    assert body["disclaimer"]

    r2 = await antitrust_client.get(f"/api/v1/antitrust/checks/{body['id']}")
    assert r2.status_code == 200
    assert r2.json()["id"] == body["id"]


async def test_run_check_invalid_type_returns_422(antitrust_client: AsyncClient) -> None:
    r = await antitrust_client.post(
        "/api/v1/antitrust/checks",
        json={"check_type": "bogus", "subject": "不正種別", "context": {}},
    )
    assert r.status_code == 422


async def test_get_check_not_found_returns_404(antitrust_client: AsyncClient) -> None:
    r = await antitrust_client.get("/api/v1/antitrust/checks/999999")
    assert r.status_code == 404


async def test_list_checks_returns_page_shape(antitrust_client: AsyncClient) -> None:
    await antitrust_client.post(
        "/api/v1/antitrust/checks",
        json={"check_type": "general", "subject": "一覧テスト", "context": {}},
    )
    r = await antitrust_client.get("/api/v1/antitrust/checks")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body and "total" in body


# ---------------------------------------------------------------------------
# #115〜#123 事前申請ワークフロー
# ---------------------------------------------------------------------------


async def test_application_workflow_end_to_end(antitrust_client: AsyncClient) -> None:
    create = await antitrust_client.post(
        "/api/v1/antitrust/applications",
        json={
            "application_type": "meeting_social",
            "title": "業界懇親会参加（API テスト）",
            "counterparty_organization": "業界団体",
        },
    )
    assert create.status_code == 201, create.text
    app_body = create.json()
    assert app_body["application_no"].startswith("AAP-")
    assert app_body["status"] == "submitted"

    decide = await antitrust_client.post(
        f"/api/v1/antitrust/applications/{app_body['id']}/decision",
        json={"decision": "approved", "decision_note": "問題なし"},
    )
    assert decide.status_code == 200
    assert decide.json()["status"] == "approved"

    complete = await antitrust_client.post(
        f"/api/v1/antitrust/applications/{app_body['id']}/complete",
        json={"outcome_note": "価格・数量の話題なし。懇親のみ。"},
    )
    assert complete.status_code == 200
    assert complete.json()["status"] == "completed"


async def test_application_decision_conflict_returns_409(antitrust_client: AsyncClient) -> None:
    create = await antitrust_client.post(
        "/api/v1/antitrust/applications",
        json={"application_type": "donation_sponsorship", "title": "寄付審査（API テスト）"},
    )
    app_id = create.json()["id"]
    first = await antitrust_client.post(
        f"/api/v1/antitrust/applications/{app_id}/decision",
        json={"decision": "rejected"},
    )
    assert first.status_code == 200
    second = await antitrust_client.post(
        f"/api/v1/antitrust/applications/{app_id}/decision",
        json={"decision": "approved"},
    )
    assert second.status_code == 409


async def test_application_cancel(antitrust_client: AsyncClient) -> None:
    create = await antitrust_client.post(
        "/api/v1/antitrust/applications",
        json={"application_type": "public_official_contact", "title": "公務員接触（API テスト）"},
    )
    app_id = create.json()["id"]
    r = await antitrust_client.post(
        f"/api/v1/antitrust/applications/{app_id}/cancel",
        json={"cancel_reason": "予定中止"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"


# ---------------------------------------------------------------------------
# #120 AI 相談 / #124 研修履歴
# ---------------------------------------------------------------------------


async def test_consultation_returns_answer_and_disclaimer(antitrust_client: AsyncClient) -> None:
    r = await antitrust_client.post(
        "/api/v1/antitrust/consultations",
        json={"query_text": "独占禁止法の不当な取引制限とは何ですか"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["answer_text"]
    assert body["disclaimer"]
    # 相談専用の免責文（チェック機能用の _CHECK_DISCLAIMER とは異なる）が返ること。
    assert body["disclaimer"] == CONSULTATION_DISCLAIMER
    assert "個別事案への当てはめ" in body["disclaimer"]


async def test_training_create_and_list(antitrust_client: AsyncClient) -> None:
    r = await antitrust_client.post(
        "/api/v1/antitrust/trainings",
        json={
            "training_title": "独占禁止法研修（API テスト）",
            "completed_at": "2026-04-01",
            "attendee_name": "テスト太郎",
            "category": "antitrust",
            "score": 88,
        },
    )
    assert r.status_code == 201, r.text

    listed = await antitrust_client.get("/api/v1/antitrust/trainings?category=antitrust")
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1


# ---------------------------------------------------------------------------
# 認証・認可
# ---------------------------------------------------------------------------


async def test_endpoints_require_authentication() -> None:
    """get_current_user を上書きしない裸のアプリでは 401/403 になる（未認証）."""
    app = _make_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/v1/antitrust/checks")
        assert r.status_code == 401


async def test_write_endpoint_requires_write_role(
    antitrust_engine: Any, seeded_ids: tuple[int, int]
) -> None:
    """viewer ロールでは書き込み系が 403 になる。"""
    user_id, _ = seeded_ids
    app = _make_app()
    Session = async_sessionmaker(bind=antitrust_engine, expire_on_commit=False, class_=AsyncSession)

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        session = Session()
        try:
            yield session
            await session.commit()
        finally:
            await session.close()

    async def _override_get_current_user() -> CurrentUser:
        return CurrentUser(
            id="viewer@example.com",
            email="viewer@example.com",
            role="viewer",
            department_ids=(),
            raw_claims={},
            db_id=user_id,
        )

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/v1/antitrust/checks",
            json={"check_type": "general", "subject": "権限テスト", "context": {}},
        )
        assert r.status_code == 403


async def test_create_consultation_requires_write_role(
    antitrust_engine: Any, seeded_ids: tuple[int, int]
) -> None:
    """viewer/auditor ロールでは AI 相談の作成（書き込み）が 403 になる。"""
    user_id, _ = seeded_ids
    app = _make_app()
    Session = async_sessionmaker(bind=antitrust_engine, expire_on_commit=False, class_=AsyncSession)

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        session = Session()
        try:
            yield session
            await session.commit()
        finally:
            await session.close()

    async def _override_get_current_user() -> CurrentUser:
        return CurrentUser(
            id="viewer@example.com",
            email="viewer@example.com",
            role="viewer",
            department_ids=(),
            raw_claims={},
            db_id=user_id,
        )

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/v1/antitrust/consultations",
            json={"query_text": "独占禁止法の不当な取引制限とは何ですか"},
        )
        assert r.status_code == 403
