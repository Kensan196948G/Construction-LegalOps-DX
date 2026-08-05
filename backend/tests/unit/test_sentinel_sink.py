"""Sentinel 転送シンクのテスト."""

from __future__ import annotations

import httpx

from app.services import sentinel_sink


def _client_for(status_code: int) -> httpx.AsyncClient:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"].startswith("Bearer ")
        return httpx.Response(status_code, json={"ok": True})

    return httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://sentinel.local",
    )


async def test_send_batch_success() -> None:
    client = _client_for(200)
    ok = await sentinel_sink.send_batch(
        {"job_no": "EXP-1"},
        url="https://sentinel.local/ingest",
        token="tok",
        client=client,
    )
    assert ok is True
    await client.aclose()


async def test_send_batch_disabled_without_url() -> None:
    ok = await sentinel_sink.send_batch({"job_no": "EXP-1"})
    assert ok is False
