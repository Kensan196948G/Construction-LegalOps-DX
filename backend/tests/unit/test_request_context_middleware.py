"""RequestContextMiddleware must treat ``scope["state"]`` as a plain dict.

Real ASGI servers (uvicorn) pre-populate ``scope["state"]`` as a dict and
Starlette's ``Request.state`` wraps that dict. The middleware previously
assigned an attribute on it (``scope["state"].request_id = ...``), which
raised AttributeError and 500'd EVERY request under uvicorn — first caught
by the k6 smoke workflow (run 29305692539), invisible to the integration
suite because httpx's ASGITransport never populates ``"state"``.
"""

from __future__ import annotations

from typing import Any

from app.main import RequestContextMiddleware


async def _ok_app(scope: Any, receive: Any, send: Any) -> None:
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


def _http_scope(*, state: Any = None) -> dict[str, Any]:
    scope: dict[str, Any] = {
        "type": "http",
        "method": "GET",
        "path": "/healthz",
        "headers": [],
        "query_string": b"",
    }
    if state is not None:
        scope["state"] = state
    return scope


async def _drive(scope: dict[str, Any]) -> list[dict[str, Any]]:
    sent: list[dict[str, Any]] = []

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    async def receive() -> dict[str, Any]:  # pragma: no cover — not pulled
        return {"type": "http.request"}

    await RequestContextMiddleware(_ok_app)(scope, receive, send)
    return sent


async def test_uvicorn_style_preexisting_dict_state() -> None:
    """uvicorn semantics: scope['state'] is already a dict — must not 500."""
    scope = _http_scope(state={})

    sent = await _drive(scope)

    assert scope["state"]["request_id"]
    start = next(m for m in sent if m["type"] == "http.response.start")
    assert start["status"] == 200


async def test_missing_state_is_created_as_plain_dict() -> None:
    """ASGITransport semantics: no 'state' key — created as a dict, not State."""
    scope = _http_scope()

    await _drive(scope)

    assert isinstance(scope["state"], dict)
    assert scope["state"]["request_id"]


async def test_existing_state_entries_are_preserved() -> None:
    """Lifespan-provided state entries must survive the middleware."""
    scope = _http_scope(state={"boot": "value"})

    await _drive(scope)

    assert scope["state"]["boot"] == "value"
    assert scope["state"]["request_id"]
