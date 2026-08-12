"""Integration tests for the legal-AI API contract (RAG evidence lookup)."""

from __future__ import annotations


async def test_evidence_lookup_get_returns_primary_source_hits(
    client, auth_headers_legal
) -> None:
    """GET /ai/evidence is the public contract used by the frontend.

    Regression guard: the frontend previously called POST /ai/evidence with a
    ``query`` body, which does not exist on the backend (405). The documented
    contract is ``GET /ai/evidence?q=...&limit=...``.
    """
    resp = await client.get(
        "/api/v1/ai/evidence",
        params={"q": "下請法 支払期日", "limit": 5},
        headers=auth_headers_legal,
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["query"] == "下請法 支払期日"
    assert isinstance(body["hits"], list)
    if body["hits"]:
        hit = body["hits"][0]
        assert hit["title"]
        assert isinstance(hit["source_verified"], bool)
        assert "score" in hit


async def test_evidence_lookup_requires_auth(client) -> None:
    resp = await client.get("/api/v1/ai/evidence", params={"q": "建設業法"})
    assert resp.status_code in (401, 403)


async def test_evidence_lookup_validates_query(client, auth_headers_legal) -> None:
    resp = await client.get("/api/v1/ai/evidence", headers=auth_headers_legal)
    assert resp.status_code == 422

    too_long = await client.get(
        "/api/v1/ai/evidence",
        params={"q": "あ" * 201},
        headers=auth_headers_legal,
    )
    assert too_long.status_code == 422
