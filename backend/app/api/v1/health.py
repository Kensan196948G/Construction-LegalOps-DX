"""ヘルスチェック / レディネスチェックエンドポイント。

- ``GET /healthz``: 軽量な liveness。プロセスが応答できることだけを示す。
- ``GET /readyz``: DB 接続 (``SELECT 1``) を実行し、依存関係が利用可能かを返す。
  ``infra/scripts/healthcheck.sh`` および compose の ``healthcheck`` ディレクティブが利用する。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.session import get_db

logger = get_logger(__name__)

router = APIRouter(tags=["meta"])


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
    summary="Readiness probe",
    description=(
        "依存リソース (DB) が利用可能かを検証する。"
        " DB 接続に失敗した場合は 503 を返す (fail-closed)。"
    ),
)
async def readyz(session: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Run ``SELECT 1`` against the configured DB and report status."""
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.warning("readyz_db_failure", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "not_ready", "db": "unavailable"},
        ) from exc

    return {"status": "ready", "db": "ok"}


@router.get(
    "/ping",
    summary="Connectivity ping",
    description="負荷の極めて軽い疎通確認用エンドポイント。",
    include_in_schema=False,
)
async def ping() -> dict[str, str]:
    return {"status": "pong"}


__all__ = ["router"]
