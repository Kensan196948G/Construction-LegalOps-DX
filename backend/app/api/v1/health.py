"""ヘルスチェック / レディネスチェックエンドポイント。

- ``GET /healthz``: 軽量な liveness。プロセスが応答できることだけを示す。
- ``GET /readyz``: 依存サービスの deep check。
  * Critical: DB (PostgreSQL) — 失敗時 503
  * Optional: Redis / Claude API — 失敗時 200 + warnings (degraded)
  ``infra/scripts/healthcheck.sh`` および compose の ``healthcheck`` ディレクティブが利用する。
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.session import get_db

logger = get_logger(__name__)

router = APIRouter(tags=["meta"])

_DEEP_CHECK_TIMEOUT = 3.0  # seconds per check


async def _check_db(session: AsyncSession) -> tuple[str, str | None]:
    """Run SELECT 1 to verify DB connectivity. Returns (status, error)."""
    try:
        await asyncio.wait_for(
            session.execute(text("SELECT 1")),
            timeout=_DEEP_CHECK_TIMEOUT,
        )
        return "ok", None
    except (TimeoutError, SQLAlchemyError) as exc:
        return "unavailable", str(exc)


async def _check_redis() -> tuple[str, str | None]:
    """Ping Redis if configured. Degraded (not critical) if missing."""
    try:
        import os

        redis_url = os.getenv("REDIS_URL", "")
        if not redis_url:
            return "not_configured", None
        import redis.asyncio as aioredis  # type: ignore[import-untyped]

        client = aioredis.from_url(redis_url, socket_connect_timeout=_DEEP_CHECK_TIMEOUT)
        await asyncio.wait_for(client.ping(), timeout=_DEEP_CHECK_TIMEOUT)
        await client.aclose()  # type: ignore[attr-defined]
        return "ok", None
    except Exception as exc:  # pragma: no cover
        return "degraded", str(exc)


async def _check_claude_api() -> tuple[str, str | None]:
    """Lightweight check that CLAUDE_API_KEY is configured."""
    import os

    key = os.getenv("CLAUDE_API_KEY", "")
    if not key:
        return "not_configured", "CLAUDE_API_KEY is not set"
    # Key present — assume reachable (avoid real API call on every probe)
    return "ok", None


@router.get(
    "/healthz",
    summary="Liveness probe",
    description="プロセスが応答可能であることのみを保証する軽量チェック。",
    include_in_schema=False,
)
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get(
    "/readyz",
    summary="Readiness probe (deep check)",
    description=(
        "依存サービスの deep check。"
        " DB (Critical) 失敗 → 503。"
        " Redis / Claude API (Optional) 失敗 → 200 + degraded warnings。"
    ),
)
async def readyz(session: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Deep readiness check: DB (critical) + Redis + Claude API (optional)."""
    db_status, db_err = await _check_db(session)
    redis_status, redis_err = await _check_redis()
    claude_status, claude_err = await _check_claude_api()

    checks: dict[str, Any] = {
        "db": {"status": db_status},
        "redis": {"status": redis_status},
        "claude_api": {"status": claude_status},
    }
    if db_err:
        checks["db"]["error"] = db_err
    if redis_err:
        checks["redis"]["error"] = redis_err
    if claude_err:
        checks["claude_api"]["error"] = claude_err

    warnings = [
        svc
        for svc, info in checks.items()
        if info["status"] in ("degraded", "unavailable") and svc != "db"
    ]

    if db_status != "ok":
        logger.warning("readyz_db_failure", error=db_err)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "not_ready", "checks": checks},
        )

    overall = "degraded" if warnings else "ready"
    if warnings:
        logger.warning("readyz_degraded", warnings=warnings)

    return {"status": overall, "checks": checks, "warnings": warnings}


@router.get(
    "/ping",
    summary="Connectivity ping",
    description="負荷の極めて軽い疎通確認用エンドポイント。",
    include_in_schema=False,
)
async def ping() -> dict[str, str]:
    return {"status": "pong"}


__all__ = ["router"]
