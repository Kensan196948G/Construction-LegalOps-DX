"""Integration tests for clause-library CRUD endpoints.

Now that create_clause and update_clause are DB-backed (Loop 18),
test the full CRUD cycle.

    - POST /clauses-library       → 201
    - GET  /clauses-library       → list (with filters)
    - PATCH /clauses-library/{id} → 200 / 404
"""

from __future__ import annotations

import uuid


def _unique_payload() -> dict:
    """Return a clause payload with a unique code to avoid UNIQUE constraint errors."""
    uid = uuid.uuid4().hex[:8]
    return {
        "code": f"CL-TEST-{uid}",
        "title": "テスト条項：損害賠償上限",
        "category": "損害賠償",
        "recommendation": "recommended",
        "text": "損害賠償の上限は請負代金額の20%とする。",
        "tags": ["損害賠償", "上限", "テスト"],
    }


async def _create_clause(client, headers) -> dict:
    r = await client.post("/api/v1/clauses-library", json=_unique_payload(), headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# POST /clauses-library
# ---------------------------------------------------------------------------


async def test_create_clause_returns_201(client, auth_headers_admin):
    """POST /clauses-library → 201 with correct schema."""
    payload = _unique_payload()
    r = await client.post("/api/v1/clauses-library", json=payload, headers=auth_headers_admin)
    assert r.status_code == 201
    body = r.json()
    assert body["code"] == payload["code"]
    assert body["title"] == payload["title"]
    assert body["text"] == payload["text"]
    assert body["tags"] == payload["tags"]
    assert "id" in body
    assert "created_at" in body


async def test_create_clause_requires_auth(client):
    """POST /clauses-library without auth → 401."""
    r = await client.post("/api/v1/clauses-library", json=_unique_payload())
    assert r.status_code == 401


async def test_create_clause_requires_admin_or_legal(client, auth_headers_site):
    """POST /clauses-library with drafter role → 403."""
    r = await client.post(
        "/api/v1/clauses-library", json=_unique_payload(), headers=auth_headers_site
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# GET /clauses-library (with fresh DB data)
# ---------------------------------------------------------------------------


async def test_list_clauses_after_create(client, auth_headers_admin):
    """GET /clauses-library after inserting returns the created clause."""
    created = await _create_clause(client, auth_headers_admin)
    clause_id = created["id"]

    r = await client.get("/api/v1/clauses-library", headers=auth_headers_admin)
    assert r.status_code == 200
    body = r.json()
    ids = [item["id"] for item in body["items"]]
    assert clause_id in ids


async def test_list_clauses_category_filter(client, auth_headers_admin):
    """GET /clauses-library?category=損害賠償 returns filtered results."""
    await _create_clause(client, auth_headers_admin)

    r = await client.get("/api/v1/clauses-library?category=損害賠償", headers=auth_headers_admin)
    assert r.status_code == 200
    for item in r.json()["items"]:
        assert item["category"] == "損害賠償"


async def test_list_clauses_search_query(client, auth_headers_admin):
    """GET /clauses-library?q=損害賠償 returns matching results."""
    await _create_clause(client, auth_headers_admin)

    r = await client.get("/api/v1/clauses-library?q=損害賠償", headers=auth_headers_admin)
    assert r.status_code == 200
    assert r.json()["total"] >= 1


# ---------------------------------------------------------------------------
# PATCH /clauses-library/{id}
# ---------------------------------------------------------------------------


async def test_update_clause_title(client, auth_headers_admin):
    """PATCH /clauses-library/{id} updates the title."""
    created = await _create_clause(client, auth_headers_admin)
    clause_id = created["id"]

    r = await client.patch(
        f"/api/v1/clauses-library/{clause_id}",
        json={"title": "更新済み条項タイトル"},
        headers=auth_headers_admin,
    )
    assert r.status_code == 200
    assert r.json()["title"] == "更新済み条項タイトル"


async def test_update_clause_not_found(client, auth_headers_admin):
    """PATCH /clauses-library/999999 → 404."""
    r = await client.patch(
        "/api/v1/clauses-library/999999",
        json={"title": "not found"},
        headers=auth_headers_admin,
    )
    assert r.status_code == 404
