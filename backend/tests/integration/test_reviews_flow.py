"""End-to-end review flow (``docs/api_design.md`` §5–§6).

Steps:

1. POST /contracts                      -- create
2. POST /contracts/{id}/reviews         -- start AI review
3. GET  /reviews/{id}                   -- poll for completed
4. PATCH /reviews/{id}                  -- add legal comment via update
5. POST /reviews/{id}/accept            -- final decision
"""

from __future__ import annotations


async def test_full_review_flow(client, auth_headers_legal, monkeypatch):
    """Arrange: stub Claude. Act: full flow. Assert: status progresses."""
    # Arrange — force stub mode
    monkeypatch.setenv("AI_REVIEW_STUB", "1")

    r_create = await client.post(
        "/api/v1/contracts",
        json={
            "title": "AI レビュー対象契約",
            "contract_type": "ukeoi",
            "counterparty": "テスト建設",
            "department_id": 1,
        },
        headers=auth_headers_legal,
    )
    assert r_create.status_code in (200, 201), (
        f"contract creation failed: {r_create.status_code} {r_create.text}"
    )
    contract_id = r_create.json()["id"]

    # Act: start review
    r_start = await client.post(
        f"/api/v1/contracts/{contract_id}/reviews",
        json={"review_type": "ai"},
        headers=auth_headers_legal,
    )
    # Assert
    assert r_start.status_code in (200, 201, 202)
    review_id = r_start.json()["id"]

    # Act: fetch
    r_get = await client.get(f"/api/v1/reviews/{review_id}", headers=auth_headers_legal)
    # Assert
    assert r_get.status_code == 200
    body = r_get.json()
    assert body["status"] in {"pending", "running", "completed"}

    # Act: add legal decision metadata via PATCH (no separate comments endpoint)
    r_patch = await client.patch(
        f"/api/v1/reviews/{review_id}",
        json={
            "legal_comment": "条項 12 を再検討済み",
            "final_decision": "accept",
            "overall_risk": "low",
        },
        headers=auth_headers_legal,
    )
    assert r_patch.status_code == 200, r_patch.text
    patched = r_patch.json()
    assert patched["overall_risk"] == "low"
    assert patched["result"]["legal_comment"] == "条項 12 を再検討済み"
    assert patched["result"]["final_decision"] == "accept"

    # Act: final decision (accept)
    r_accept = await client.post(
        f"/api/v1/reviews/{review_id}/accept",
        json={"comment": "承認"},
        headers=auth_headers_legal,
    )
    # Assert
    assert r_accept.status_code == 200
    assert r_accept.json().get("status") == "completed"
