"""内部通報・調査管理 API の統合テスト（Issue #123）.

NOTE: ``app.api.v1.whistleblower`` は並列実装との衝突を避けるため
``app.api.v1.__init__`` に未登録（意図的）。そのため本テストはメインアプリ
ではなく、当該 router のみをマウントした軽量 FastAPI アプリを構築して
HTTP 層（ステータスコード・スキーマ検証・ACL 強制）を検証する。統合後は
``tests/integration/test_matter_api.py`` と同様にメインアプリ経由でも
到達可能になる。

最重要: 通報者情報（``/reports/{id}/reporter``）が ACL 非保有ロールから
確実に 403 になることを HTTP レベルで検証する。
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pytest

from app.deps import CurrentUser


def _current_user(*, role: str, db_id: int | None) -> CurrentUser:
    return CurrentUser(
        id=uuid.uuid4(),
        email=f"{role}@test.local",
        role=role,
        department_ids=(),
        raw_claims={},
        db_id=db_id,
    )


@pytest.fixture()
async def wb_client(db_session: Any) -> AsyncGenerator[Any, None]:
    """whistleblower router のみをマウントした ASGI テストアプリ."""
    try:
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient
    except ImportError:  # pragma: no cover
        pytest.skip("fastapi/httpx unavailable")

    from app.api.v1 import whistleblower
    from app.core.exceptions import register_exception_handlers
    from app.db.session import get_db
    from app.deps import get_current_user

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(whistleblower.router, prefix="/api/v1")

    async def _override_get_db() -> AsyncGenerator[Any, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    # テストごとに呼び出し元が current_user を差し替えられるよう、
    # mutable な box を dependency_overrides 経由で共有する。
    state: dict[str, CurrentUser] = {"user": _current_user(role="admin", db_id=None)}

    async def _override_get_current_user() -> CurrentUser:
        return state["user"]

    app.dependency_overrides[get_current_user] = _override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        client.state = state  # type: ignore[attr-defined]
        yield client


def _as(client: Any, *, role: str, db_id: int | None) -> None:
    client.state["user"] = _current_user(role=role, db_id=db_id)  # type: ignore[attr-defined]


async def _make_user(db_session: Any, *, role: str, name: str) -> int:
    from app.models.department import Department
    from app.models.user import User

    dept = Department(code=f"D-{uuid.uuid4().hex[:8]}", name="部署")
    db_session.add(dept)
    await db_session.flush()
    user = User(
        entra_oid=uuid.uuid4(),
        email=f"{uuid.uuid4().hex[:10]}@test.local",
        display_name=name,
        role=role,
        department_id=dept.id,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return int(user.id)


async def test_report_lifecycle_and_identity_isolation(wb_client: Any, db_session: Any) -> None:
    reporter_id = await _make_user(db_session, role="drafter", name="通報者")
    investigator_id = await _make_user(db_session, role="reviewer", name="調査担当者")
    outsider_id = await _make_user(db_session, role="drafter", name="無関係者")

    _as(wb_client, role="drafter", db_id=reporter_id)
    r_create = await wb_client.post(
        "/api/v1/whistleblower/reports",
        json={
            "category": "harassment",
            "title": "上司からのハラスメント",
            "description": "詳細内容をここに記載",
            "reporter_name": "通報 花子",
            "contact_email": "hanako@example.com",
        },
    )
    assert r_create.status_code == 201, r_create.text
    body = r_create.json()
    assert body["report_no"].startswith("WB-")
    report_id = body["id"]

    # 無関係な一般ロールは詳細・通報者情報のいずれも見えない（隔離の核心）。
    _as(wb_client, role="drafter", db_id=outsider_id)
    r_detail_forbidden = await wb_client.get(f"/api/v1/whistleblower/reports/{report_id}")
    assert r_detail_forbidden.status_code == 403
    r_reporter_forbidden = await wb_client.get(
        f"/api/v1/whistleblower/reports/{report_id}/reporter"
    )
    assert r_reporter_forbidden.status_code == 403

    # admin は ACL 無しでも全件・識別情報にアクセス可。
    _as(wb_client, role="admin", db_id=None)
    r_reporter_admin = await wb_client.get(f"/api/v1/whistleblower/reports/{report_id}/reporter")
    assert r_reporter_admin.status_code == 200
    assert r_reporter_admin.json()["reporter_name"] == "通報 花子"

    # admin が調査担当者 ACL を付与する。
    r_grant = await wb_client.post(
        f"/api/v1/whistleblower/reports/{report_id}/access",
        json={"user_id": investigator_id, "role_in_case": "investigator"},
    )
    assert r_grant.status_code == 201, r_grant.text

    # 調査担当者は ACL 付与後、案件・通報者情報の双方にアクセス可能。
    _as(wb_client, role="reviewer", db_id=investigator_id)
    r_detail_ok = await wb_client.get(f"/api/v1/whistleblower/reports/{report_id}")
    assert r_detail_ok.status_code == 200
    r_reporter_ok = await wb_client.get(f"/api/v1/whistleblower/reports/{report_id}/reporter")
    assert r_reporter_ok.status_code == 200
    assert r_reporter_ok.json()["contact_email"] == "hanako@example.com"

    # 証拠・ヒアリング・是正措置の登録（調査担当者権限で可能）。
    r_evidence = await wb_client.post(
        f"/api/v1/whistleblower/reports/{report_id}/evidence",
        json={"evidence_type": "email", "description": "メール証跡", "preserved": True},
    )
    assert r_evidence.status_code == 201

    r_action = await wb_client.post(
        f"/api/v1/whistleblower/reports/{report_id}/actions",
        json={"action_category": "corrective", "title": "懲戒処分の実施"},
    )
    assert r_action.status_code == 201

    r_timeline = await wb_client.get(f"/api/v1/whistleblower/reports/{report_id}/timeline")
    assert r_timeline.status_code == 200
    types = [e["event_type"] for e in r_timeline.json()]
    assert "received" in types
    assert "access_granted" in types
    assert "evidence_added" in types
    assert "action_added" in types

    # 依然として無関係者は隔離されたまま（ACL 付与後も他人には波及しない）。
    _as(wb_client, role="drafter", db_id=outsider_id)
    r_still_forbidden = await wb_client.get(f"/api/v1/whistleblower/reports/{report_id}/reporter")
    assert r_still_forbidden.status_code == 403


async def test_anonymous_report_returns_no_identity(wb_client: Any, db_session: Any) -> None:
    reporter_id = await _make_user(db_session, role="drafter", name="通報者")
    _as(wb_client, role="drafter", db_id=reporter_id)
    r = await wb_client.post(
        "/api/v1/whistleblower/reports",
        json={
            "category": "corruption",
            "title": "談合の疑い",
            "description": "詳細内容",
            "is_anonymous": True,
        },
    )
    assert r.status_code == 201, r.text
    report_id = r.json()["id"]

    _as(wb_client, role="admin", db_id=None)
    r_reporter = await wb_client.get(f"/api/v1/whistleblower/reports/{report_id}/reporter")
    assert r_reporter.status_code == 200
    assert r_reporter.json() is None


async def test_aggregate_requires_admin_role(wb_client: Any, db_session: Any) -> None:
    reporter_id = await _make_user(db_session, role="drafter", name="通報者")
    _as(wb_client, role="drafter", db_id=reporter_id)
    r_forbidden = await wb_client.get("/api/v1/whistleblower/reports/aggregate")
    assert r_forbidden.status_code == 403

    _as(wb_client, role="auditor", db_id=None)
    r_ok = await wb_client.get("/api/v1/whistleblower/reports/aggregate")
    assert r_ok.status_code == 200
    assert "by_category" in r_ok.json()
