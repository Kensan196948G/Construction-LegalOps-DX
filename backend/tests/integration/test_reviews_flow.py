"""End-to-end review flow (``docs/api_design.md`` §5–§6).

Steps:

1. POST /contracts                      -- create
2. POST /contracts/{id}/reviews         -- start AI review (stub)
3. GET  /reviews/{id}                   -- poll for completed
4. POST /reviews/{id}/comments          -- add legal comment
5. POST /reviews/{id}/accept            -- final decision
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.xfail(
    strict=False, reason="Review service and comments endpoint are stubs"
)


async def test_full_review_flow(client, auth_headers_legal, monkeypatch):
    """Arrange: stub Claude. Act: full flow. Assert: status progresses."""
    # Arrange — force stub mode
    monkeypatch.setenv("AI_REVIEW_STUB", "1")

    r_create = await client.post(
        "/api/v1/contracts",
        json={
            "title": "AI レビュー対象契約",
            "contract_type": "ukeoi",
            "counterparty_name": "テスト建設",
            "contract_amount": 50_000_000,
        },
        headers=auth_headers_legal,
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

    # Act: legal comment
    r_comment = await client.post(
        f"/api/v1/reviews/{review_id}/comments",
        json={"body": "条項 12 を再検討", "visibility": "internal"},
        headers=auth_headers_legal,
    )
    # Assert
    assert r_comment.status_code in (200, 201)

    # Act: final decision (accept)
    r_accept = await client.post(
        f"/api/v1/reviews/{review_id}/accept",
        json={"comment": "承認"},
        headers=auth_headers_legal,
    )
    # Assert
    assert r_accept.status_code == 200
    assert r_accept.json().get("status") == "accepted"
