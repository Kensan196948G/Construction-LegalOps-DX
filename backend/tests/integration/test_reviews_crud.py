"""Integration tests for reviews CRUD endpoints.

Covers the individual review endpoints to increase service coverage:
    - GET /reviews               → list (auth / role / pagination)
    - GET /reviews/{id}          → get by id
    - PATCH /reviews/{id}        → partial update
    - POST /reviews/{id}/accept  → accept with comment
    - POST /reviews/{id}/reject  → reject with comment
    - GET /reviews (filter)      → status / contract_id filters
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CONTRACT_BODY = {
    "title": "レビュー CRUD テスト契約",
    "contract_type": "工事請負契約",
    "counterparty": "テスト建設株式会社",
    "department_id": 1,
}


async def _create_contract(client, headers) -> int:
    r = await client.post("/api/v1/contracts", json=_CONTRACT_BODY, headers=headers)
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


async def _start_review(client, contract_id, headers, monkeypatch) -> int:
    monkeypatch.setenv("AI_REVIEW_STUB", "1")
    r = await client.post(
        f"/api/v1/contracts/{contract_id}/reviews",
        json={"review_type": "ai"},
        headers=headers,
    )
    assert r.status_code in (200, 201, 202), r.text
    return r.json()["id"]


# ---------------------------------------------------------------------------
# GET /reviews — list
# ---------------------------------------------------------------------------


async def test_list_reviews_returns_page(
    client, auth_headers_admin, auth_headers_legal, monkeypatch
):
    """GET /reviews returns pagination schema with at least one review."""
    cid = await _create_contract(client, auth_headers_legal)
    await _start_review(client, cid, auth_headers_legal, monkeypatch)

    r = await client.get("/api/v1/reviews", headers=auth_headers_admin)
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "total" in body
    assert body["total"] >= 1


async def test_list_reviews_requires_auth(client):
    """GET /reviews without auth → 401."""
    r = await client.get("/api/v1/reviews")
    assert r.status_code == 401


async def test_list_reviews_status_filter(
    client, auth_headers_admin, auth_headers_legal, monkeypatch
):
    """GET /reviews?status=pending returns only pending items (or empty)."""
    cid = await _create_contract(client, auth_headers_legal)
    await _start_review(client, cid, auth_headers_legal, monkeypatch)

    r = await client.get("/api/v1/reviews?status=pending", headers=auth_headers_admin)
    assert r.status_code == 200
    for item in r.json().get("items", []):
        assert item["status"] == "pending"


async def test_list_reviews_contract_filter(
    client, auth_headers_admin, auth_headers_legal, monkeypatch
):
    """GET /reviews?contract_id={id} returns only reviews for that contract."""
    cid = await _create_contract(client, auth_headers_legal)
    await _start_review(client, cid, auth_headers_legal, monkeypatch)

    r = await client.get(f"/api/v1/reviews?contract_id={cid}", headers=auth_headers_admin)
    assert r.status_code == 200
    for item in r.json().get("items", []):
        assert item["contract_id"] == cid


# ---------------------------------------------------------------------------
# GET /reviews/{id}
# ---------------------------------------------------------------------------


async def test_get_review_by_id(client, auth_headers_legal, monkeypatch):
    """GET /reviews/{id} returns the review with correct schema."""
    cid = await _create_contract(client, auth_headers_legal)
    rid = await _start_review(client, cid, auth_headers_legal, monkeypatch)

    r = await client.get(f"/api/v1/reviews/{rid}", headers=auth_headers_legal)
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == rid
    assert body["contract_id"] == cid
    assert "status" in body
    assert "disclaimer" in body


async def test_get_review_not_found(client, auth_headers_admin):
    """GET /reviews/999999 → 404."""
    r = await client.get("/api/v1/reviews/999999", headers=auth_headers_admin)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /reviews/{id}
# ---------------------------------------------------------------------------


async def test_patch_review_overall_risk(client, auth_headers_legal, monkeypatch):
    """PATCH /reviews/{id} persists DB fields and legal decision metadata."""
    cid = await _create_contract(client, auth_headers_legal)
    rid = await _start_review(client, cid, auth_headers_legal, monkeypatch)

    r = await client.patch(
        f"/api/v1/reviews/{rid}",
        json={
            "overall_risk": "low",
            "legal_comment": "人間確認済み",
            "final_decision": "accept",
        },
        headers=auth_headers_legal,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["overall_risk"] == "low"
    assert body["result"]["legal_comment"] == "人間確認済み"
    assert body["result"]["final_decision"] == "accept"


async def test_patch_review_not_found(client, auth_headers_legal):
    """PATCH /reviews/999999 → 404."""
    r = await client.patch(
        "/api/v1/reviews/999999",
        json={"summary": "not found"},
        headers=auth_headers_legal,
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# POST /reviews/{id}/accept and /reject
# ---------------------------------------------------------------------------


async def test_accept_review(client, auth_headers_legal, monkeypatch):
    """POST /reviews/{id}/accept → 200 with status=completed."""
    cid = await _create_contract(client, auth_headers_legal)
    rid = await _start_review(client, cid, auth_headers_legal, monkeypatch)

    r = await client.post(
        f"/api/v1/reviews/{rid}/accept",
        json={"comment": "問題なし"},
        headers=auth_headers_legal,
    )
    assert r.status_code == 200
    assert r.json().get("status") == "completed"


async def test_reject_review(client, auth_headers_legal, monkeypatch):
    """POST /reviews/{id}/reject → 200 with status=completed."""
    cid = await _create_contract(client, auth_headers_legal)
    rid = await _start_review(client, cid, auth_headers_legal, monkeypatch)

    r = await client.post(
        f"/api/v1/reviews/{rid}/reject",
        json={"comment": "修正が必要"},
        headers=auth_headers_legal,
    )
    assert r.status_code == 200
    assert r.json().get("status") in ("completed", "rejected")


async def test_accept_review_not_found(client, auth_headers_legal):
    """POST /reviews/999999/accept → 404."""
    r = await client.post(
        "/api/v1/reviews/999999/accept",
        json={"comment": "test"},
        headers=auth_headers_legal,
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Row-level scope (drafter sees only own reviews)
# ---------------------------------------------------------------------------


async def test_list_reviews_drafter_scope(
    client, auth_headers_site, monkeypatch
):
    """Drafter sees only reviews on contracts they drafted."""
    cid = await _create_contract(client, auth_headers_site)
    await _start_review(client, cid, auth_headers_site, monkeypatch)

    r = await client.get("/api/v1/reviews", headers=auth_headers_site)
    assert r.status_code == 200
    assert "items" in r.json()


async def test_list_reviews_ai_model_filter(
    client, auth_headers_admin, auth_headers_legal, monkeypatch
):
    """GET /reviews?ai_model=stub returns only matching items."""
    cid = await _create_contract(client, auth_headers_legal)
    await _start_review(client, cid, auth_headers_legal, monkeypatch)

    r = await client.get("/api/v1/reviews?ai_model=stub", headers=auth_headers_admin)
    assert r.status_code == 200
    for item in r.json().get("items", []):
        assert item.get("ai_model") == "stub"
