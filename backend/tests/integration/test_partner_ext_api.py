"""協力会社拡張 API の統合テスト（#136〜#152）."""

from __future__ import annotations

from typing import Any

PE = "/api/v1/partners"


async def _create_partner(client: Any, headers: dict[str, str], name: str) -> dict[str, Any]:
    r = await client.post(
        "/api/v1/partners",
        json={"name": name, "partner_type": "下請"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


async def test_review_flow_and_risk_score(
    client: Any, auth_headers_admin: dict[str, str], auth_headers_legal: dict[str, str]
) -> None:
    """再審査起票 → 完了（次回期限反映）→ Risk Score 保存."""
    partner = await _create_partner(client, auth_headers_legal, "統合テスト協力会社（デモ）")
    partner_id = partner["id"]

    r_create = await client.post(
        f"{PE}/{partner_id}/reviews",
        json={"review_type": "periodic", "title": "定期再審査（デモ）"},
        headers=auth_headers_admin,
    )
    assert r_create.status_code == 201, r_create.text
    review = r_create.json()
    assert review["review_no"].startswith("PRV-")
    assert review["status"] == "open"

    r_complete = await client.post(
        f"{PE}/partner-reviews/{review['id']}/complete",
        json={"safety_score": 90, "findings": "特記事項なし（デモ）"},
        headers=auth_headers_admin,
    )
    assert r_complete.status_code == 200
    assert r_complete.json()["status"] == "completed"
    assert r_complete.json()["next_review_due"] is not None

    r_complete2 = await client.post(
        f"{PE}/partner-reviews/{review['id']}/complete",
        json={"safety_score": 95},
        headers=auth_headers_admin,
    )
    assert r_complete2.status_code == 409

    r_score = await client.post(
        f"{PE}/{partner_id}/risk-score/refresh", headers=auth_headers_admin
    )
    assert r_score.status_code == 200
    body = r_score.json()
    assert 0 <= body["risk_score"] <= 100
    assert body["risk_level"] in ("low", "medium", "high", "critical")

    r_score_get = await client.get(f"{PE}/{partner_id}/risk-score", headers=auth_headers_admin)
    assert r_score_get.status_code == 200

    r_flags = await client.get(f"{PE}/{partner_id}/expiry-flags", headers=auth_headers_admin)
    assert r_flags.status_code == 200
    assert r_flags.json()["insurance_state"] == "unset"


async def test_expiry_alerts_endpoint(
    client: Any, auth_headers_admin: dict[str, str]
) -> None:
    """#138/#146 期限アラート一覧."""
    r = await client.get(f"{PE}/alerts", headers=auth_headers_admin)
    assert r.status_code == 200
    assert isinstance(r.json(), list)
