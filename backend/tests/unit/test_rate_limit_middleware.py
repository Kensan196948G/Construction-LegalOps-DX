"""Unit tests for the application-layer rate limiting middleware."""

from __future__ import annotations

import pytest
from starlette.types import Message

from app.middleware.rate_limit import RateLimitMiddleware


async def _noop_app(scope: object, receive: object, send: object) -> None:
    """Minimal ASGI app that records nothing; used to assert pass-through."""
    return None


def _make_scope(path: str, client_ip: str = "203.0.113.10") -> dict[str, object]:
    return {
        "type": "http",
        "path": path,
        "method": "GET",
        "headers": [],
        "client": (client_ip, 12345),
        "query_string": b"",
        "scheme": "http",
        "server": ("testserver", 80),
        "root_path": "",
        "state": {},
        "app": None,
    }


@pytest.mark.asyncio
async def test_general_limit_rejects_after_window_filled() -> None:
    sent: list[dict[str, object]] = []
    downstream_calls = 0

    async def counting_app(scope: object, receive: object, send: object) -> None:
        nonlocal downstream_calls
        downstream_calls += 1

    async def fake_send(message: Message) -> None:
        sent.append(message)

    async def fake_receive() -> Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    middleware = RateLimitMiddleware(
        counting_app,
        enabled=True,
        general_per_minute=3,
        auth_per_minute=1,
    )
    scope = _make_scope("/api/v1/contracts")

    for _ in range(3):
        await middleware(scope, fake_receive, fake_send)
    await middleware(scope, fake_receive, fake_send)

    assert downstream_calls == 3
    start_message = next(m for m in sent if m["type"] == "http.response.start")
    assert start_message["status"] == 429
    headers = dict(start_message["headers"])
    assert headers[b"retry-after"] == b"60"


@pytest.mark.asyncio
async def test_auth_path_has_stricter_limit() -> None:
    sent: list[dict[str, object]] = []

    async def fake_send(message: Message) -> None:
        sent.append(message)

    async def fake_receive() -> Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    middleware = RateLimitMiddleware(
        _noop_app,
        enabled=True,
        general_per_minute=100,
        auth_per_minute=2,
    )
    scope = _make_scope("/api/v1/auth/sso/login")

    for _ in range(2):
        await middleware(scope, fake_receive, fake_send)
    await middleware(scope, fake_receive, fake_send)

    start_message = next(m for m in sent if m["type"] == "http.response.start")
    assert start_message["status"] == 429


@pytest.mark.asyncio
async def test_health_path_is_exempt() -> None:
    calls = 0

    async def counting_app(scope: object, receive: object, send: object) -> None:
        nonlocal calls
        calls += 1

    middleware = RateLimitMiddleware(
        counting_app,
        enabled=True,
        general_per_minute=1,
        auth_per_minute=1,
    )

    async def fake_send(message: Message) -> None:
        return None

    async def fake_receive() -> Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    scope = _make_scope("/healthz")
    for _ in range(5):
        await middleware(scope, fake_receive, fake_send)

    assert calls == 5


@pytest.mark.asyncio
async def test_disabled_middleware_passes_through() -> None:
    calls = 0

    async def counting_app(scope: object, receive: object, send: object) -> None:
        nonlocal calls
        calls += 1

    middleware = RateLimitMiddleware(
        counting_app,
        enabled=False,
        general_per_minute=1,
        auth_per_minute=1,
    )

    async def fake_send(message: Message) -> None:
        return None

    async def fake_receive() -> Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    scope = _make_scope("/api/v1/contracts")
    for _ in range(3):
        await middleware(scope, fake_receive, fake_send)

    assert calls == 3


@pytest.mark.asyncio
async def test_forwarded_for_header_is_used_as_key() -> None:
    sent: list[dict[str, object]] = []

    async def fake_send(message: Message) -> None:
        sent.append(message)

    async def fake_receive() -> Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    middleware = RateLimitMiddleware(
        _noop_app,
        enabled=True,
        general_per_minute=1,
        auth_per_minute=1,
    )
    scope = _make_scope("/api/v1/contracts", client_ip="10.0.0.1")
    scope["headers"] = [(b"x-forwarded-for", b"198.51.100.7, 10.0.0.1")]

    await middleware(scope, fake_receive, fake_send)
    await middleware(scope, fake_receive, fake_send)

    start_message = next(m for m in sent if m["type"] == "http.response.start")
    assert start_message["status"] == 429
