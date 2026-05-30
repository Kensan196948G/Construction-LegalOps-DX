"""Integration tests for knowledge search and template endpoints.

Covers:
    - GET /knowledge/search         → keyword search over contracts
    - GET /knowledge/similar/{id}   → similar contracts via TF-cosine
    - POST /knowledge               → 501 (not yet implemented)
    - GET /templates                → list in-memory templates
    - GET /templates/{id}           → single template
    - GET /templates/clauses-library → clause-library items
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CONTRACT_BODY = {
    "title": "知識・テンプレート テスト工事請負契約",
    "contract_type": "ukeoi",
    "counterparty": "サンプル建設株式会社",
    "department_id": 1,
}


async def _create_contract(client, headers, title: str = "") -> int:
    body = dict(_CONTRACT_BODY)
    if title:
        body["title"] = title
    r = await client.post("/api/v1/contracts", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ---------------------------------------------------------------------------
# Knowledge search
# ---------------------------------------------------------------------------


async def test_knowledge_search_requires_auth(client):
    """GET /knowledge/search without auth → 401."""
    r = await client.get("/api/v1/knowledge/search?q=工事")
    assert r.status_code == 401


async def test_knowledge_search_returns_page(client, auth_headers_legal):
    """GET /knowledge/search returns page schema."""
    await _create_contract(client, auth_headers_legal, "工事請負搜索テスト")
    r = await client.get("/api/v1/knowledge/search?q=工事", headers=auth_headers_legal)
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "total" in body


async def test_knowledge_search_no_results(client, auth_headers_admin):
    """GET /knowledge/search with no match returns empty list."""
    r = await client.get(
        "/api/v1/knowledge/search?q=xyzzy_no_match_xyz", headers=auth_headers_admin
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 0
    assert body["items"] == []


async def test_knowledge_similar_not_found(client, auth_headers_admin):
    """GET /knowledge/similar/999999 → 404 for unknown contract."""
    r = await client.get("/api/v1/knowledge/similar/999999", headers=auth_headers_admin)
    assert r.status_code == 404


async def test_knowledge_similar_returns_list(client, auth_headers_legal):
    """GET /knowledge/similar/{id} returns a list (possibly empty)."""
    # Create two contracts so there is at least one other to compare against.
    cid1 = await _create_contract(client, auth_headers_legal, "類似検索テスト 契約A")
    await _create_contract(client, auth_headers_legal, "類似検索テスト 契約B")

    r = await client.get(f"/api/v1/knowledge/similar/{cid1}", headers=auth_headers_legal)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_knowledge_create_article(client, auth_headers_admin):
    """POST /knowledge → 201 with the created article."""
    payload = {
        "title": "建設業法 第19条 書面要件 解説",
        "body": "建設業法第19条は、請負契約の書面化を義務付けています。",
        "tags": ["建設業法", "契約書面"],
        "contract_type": "請負",
    }
    r = await client.post("/api/v1/knowledge", json=payload, headers=auth_headers_admin)
    assert r.status_code == 201
    body = r.json()
    assert body["title"] == payload["title"]
    assert body["tags"] == payload["tags"]
    assert "id" in body
    assert "created_at" in body


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


async def test_list_templates_returns_seeded_data(client, auth_headers_admin):
    """GET /templates returns at least 5 pre-seeded templates."""
    r = await client.get("/api/v1/templates", headers=auth_headers_admin)
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert body["total"] >= 5


async def test_list_templates_requires_auth(client):
    """GET /templates without auth → 401."""
    r = await client.get("/api/v1/templates")
    assert r.status_code == 401


async def test_get_template_by_id(client, auth_headers_admin):
    """GET /templates/1 returns the seeded template with correct schema."""
    r = await client.get("/api/v1/templates/1", headers=auth_headers_admin)
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == 1
    assert "code" in body
    assert "name" in body
    assert "body" in body


async def test_get_template_not_found(client, auth_headers_admin):
    """GET /templates/999999 → 404."""
    r = await client.get("/api/v1/templates/999999", headers=auth_headers_admin)
    assert r.status_code == 404


async def test_list_clause_library_returns_page(client, auth_headers_admin):
    """GET /clauses-library returns page schema (DB-backed; may be empty in test env)."""
    r = await client.get("/api/v1/clauses-library", headers=auth_headers_admin)
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "total" in body
    assert isinstance(body["items"], list)


async def test_create_template_501(client, auth_headers_admin):
    """POST /templates → 501 until persistent store is ready."""
    payload = {
        "code": "TEST-001",
        "name": "テスト用テンプレート",
        "contract_type": "テスト",
        "body": "契約本文",
    }
    r = await client.post("/api/v1/templates", json=payload, headers=auth_headers_admin)
    assert r.status_code == 501
