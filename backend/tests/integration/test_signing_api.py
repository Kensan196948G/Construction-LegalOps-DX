"""電子署名エンベロープ API の統合テスト（ロードマップ #1〜#4）.

フロー: 契約作成 → エンベロープ作成(draft) → 承諾証跡 → send → view →
sign → complete。遷移違反（409）と electronic 承諾未記録（422）も検証する。
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from app.services.signing_provider import SigningProviderUnavailableError

API = "/api/v1/signing"


async def _create_contract(client: Any, headers: dict[str, str]) -> int:
    r = await client.post(
        "/api/v1/contracts",
        json={
            "title": "電子締結テスト契約",
            "contract_type": "工事請負契約",
            "counterparty": "みらいテスト商事株式会社",
            "amount": 5_000_000,
            "department_id": 1,
        },
        headers=headers,
    )
    assert r.status_code in (200, 201), r.text
    return int(r.json()["id"])


async def _create_envelope(
    client: Any, headers: dict[str, str], contract_id: int, **overrides: Any
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "contract_id": contract_id,
        "method": "electronic",
        "provider": "demo",
        "counterparty_name": "みらいテスト商事株式会社",
        "counterparty_email": "partner@example.jp",
    }
    body.update(overrides)
    r = await client.post(API, json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def test_electronic_lifecycle_with_consent_trail(
    client: Any, auth_headers_legal: dict[str, str]
) -> None:
    """承諾証跡付き electronic フルライフサイクル."""
    contract_id = await _create_contract(client, auth_headers_legal)
    env = await _create_envelope(client, auth_headers_legal, contract_id)
    assert env["status"] == "draft"
    assert env["envelope_no"].startswith("ES-")
    assert env["provider"] == "demo"

    # 承諾証跡（建設業法 19 条・電磁的方法の相手方承諾）
    r_consent = await client.post(
        f"{API}/{env['id']}/consent",
        json={"consentor_name": "テスト商事 代表", "consentor_email": "partner@example.jp",
              "note": "メールにて電磁的方法による交付を承諾"},
        headers=auth_headers_legal,
    )
    assert r_consent.status_code == 200, r_consent.text
    assert r_consent.json()["consent_confirmed_at"] is not None
    assert r_consent.json()["status"] == "draft"

    # send → viewed → signed → completed
    r_send = await client.post(f"{API}/{env['id']}/send", headers=auth_headers_legal)
    assert r_send.status_code == 200
    assert r_send.json()["status"] == "sent"
    assert r_send.json()["sent_at"] is not None

    r_view = await client.post(f"{API}/{env['id']}/view", headers=auth_headers_legal)
    assert r_view.status_code == 200
    assert r_view.json()["status"] == "viewed"

    r_sign = await client.post(
        f"{API}/{env['id']}/sign",
        json={"signer_name": "テスト商事 代表", "signer_email": "partner@example.jp"},
        headers=auth_headers_legal,
    )
    assert r_sign.status_code == 200, r_sign.text
    assert r_sign.json()["status"] == "signed"
    assert r_sign.json()["signed_at"] is not None

    r_complete = await client.post(
        f"{API}/{env['id']}/complete", json={}, headers=auth_headers_legal
    )
    assert r_complete.status_code == 200, r_complete.text
    completed = r_complete.json()
    assert completed["status"] == "completed"
    assert completed["completed_at"] is not None

    # 証跡イベント列
    r_events = await client.get(f"{API}/{env['id']}/events", headers=auth_headers_legal)
    assert r_events.status_code == 200
    types = [e["event_type"] for e in r_events.json()]
    assert types == ["created", "consent_received", "sent", "viewed", "signed", "completed"]

    # 一覧フィルタ
    r_list = await client.get(f"{API}?status=completed", headers=auth_headers_legal)
    assert r_list.status_code == 200
    assert any(item["id"] == env["id"] for item in r_list.json()["items"])


async def test_electronic_sign_requires_consent_record(
    client: Any, auth_headers_legal: dict[str, str]
) -> None:
    """electronic 方式は承諾記録なしでは署名できない（422・fail-closed）."""
    contract_id = await _create_contract(client, auth_headers_legal)
    env = await _create_envelope(client, auth_headers_legal, contract_id)

    await client.post(f"{API}/{env['id']}/send", headers=auth_headers_legal)
    await client.post(f"{API}/{env['id']}/view", headers=auth_headers_legal)

    r_sign = await client.post(
        f"{API}/{env['id']}/sign", json={"signer_name": "X"}, headers=auth_headers_legal
    )
    assert r_sign.status_code == 422, r_sign.text
    assert "承諾" in r_sign.json()["detail"]

    # 承諾後は成功する
    r_consent = await client.post(
        f"{API}/{env['id']}/consent", json={"consentor_name": "X"}, headers=auth_headers_legal
    )
    assert r_consent.status_code == 200
    r_sign2 = await client.post(
        f"{API}/{env['id']}/sign", json={"signer_name": "X"}, headers=auth_headers_legal
    )
    assert r_sign2.status_code == 200
    assert r_sign2.json()["status"] == "signed"


async def test_invalid_transition_returns_409(
    client: Any, auth_headers_legal: dict[str, str]
) -> None:
    """二重送信（sent→sent）は 409 Conflict."""
    contract_id = await _create_contract(client, auth_headers_legal)
    env = await _create_envelope(client, auth_headers_legal, contract_id)

    r1 = await client.post(f"{API}/{env['id']}/send", headers=auth_headers_legal)
    assert r1.status_code == 200
    r2 = await client.post(f"{API}/{env['id']}/send", headers=auth_headers_legal)
    assert r2.status_code == 409, r2.text


async def test_cancel_then_complete_rejected(
    client: Any, auth_headers_legal: dict[str, str]
) -> None:
    """取消後の締結は 409."""
    contract_id = await _create_contract(client, auth_headers_legal)
    env = await _create_envelope(client, auth_headers_legal, contract_id)

    r_cancel = await client.post(
        f"{API}/{env['id']}/cancel", json={"reason": "条件変更"}, headers=auth_headers_legal
    )
    assert r_cancel.status_code == 200
    assert r_cancel.json()["status"] == "cancelled"

    r_complete = await client.post(
        f"{API}/{env['id']}/complete", json={}, headers=auth_headers_legal
    )
    assert r_complete.status_code == 409, r_complete.text


async def test_paper_method_skips_consent_requirement(
    client: Any, auth_headers_site: dict[str, str]
) -> None:
    """paper 方式は承諾記録なしでも署名できる."""
    contract_id = await _create_contract(client, auth_headers_site)
    env = await _create_envelope(
        client, auth_headers_site, contract_id, method="paper"
    )
    await client.post(f"{API}/{env['id']}/send", headers=auth_headers_site)
    r_sign = await client.post(
        f"{API}/{env['id']}/sign", json={"signer_name": "現場担当"}, headers=auth_headers_site
    )
    assert r_sign.status_code == 200, r_sign.text
    assert r_sign.json()["status"] == "signed"


@pytest.mark.skipif(
    bool(
        os.getenv("CLOUDSIGN_API_TOKEN")
        or os.getenv("CLOUDSIGN_API_KEY")
    ),
    reason="CloudSign 資格情報が設定されている環境では fail-closed 検証をスキップ",
)
async def test_cloudsign_without_credentials_returns_503(
    client: Any, auth_headers_legal: dict[str, str]
) -> None:
    """未設定の実プロバイダ利用は 503（fail-closed）."""
    contract_id = await _create_contract(client, auth_headers_legal)
    r = await client.post(
        API,
        json={
            "contract_id": contract_id,
            "method": "electronic",
            "provider": "cloudsign",
        },
        headers=auth_headers_legal,
    )
    assert r.status_code == SigningProviderUnavailableError.status_code, r.text
    assert "未設定" in r.json()["detail"]
