"""Microsoft Sentinel / Purview 等への外部転送（P0-6・fail-closed）.

転送は durable outbox（external_forward_events）経由で行う。
SENTINEL_ENABLED=true なのに必須設定が不足している場合は
イベントを送信せず status=blocked に留める（false-positive 送信防止）。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.retention import ExternalForwardEvent

logger = structlog.get_logger(__name__)


def is_configured() -> bool:
    """Sentinel 転送が設定済みか（true かつ必須値が揃っている場合のみ）。"""
    settings = get_settings()
    if not settings.sentinel_enabled:
        return False
    return bool(
        settings.sentinel_workspace_id.strip()
        and settings.sentinel_primary_key.get_secret_value().strip()
    )


def configuration_errors() -> list[str]:
    settings = get_settings()
    errors: list[str] = []
    if not settings.sentinel_enabled:
        return errors
    if not settings.sentinel_workspace_id.strip():
        errors.append("SENTINEL_WORKSPACE_ID is required when SENTINEL_ENABLED=true")
    if not settings.sentinel_primary_key.get_secret_value().strip():
        errors.append("SENTINEL_PRIMARY_KEY is required when SENTINEL_ENABLED=true")
    return errors


async def enqueue_event(
    session: AsyncSession,
    *,
    source_type: str,
    source_id: int | None,
    event_type: str,
    payload: dict[str, Any],
) -> ExternalForwardEvent:
    """外部転送イベントをアウトボックスに記録する。"""
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    payload_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    status = "pending" if is_configured() else "blocked"
    row = ExternalForwardEvent(
        source_type=source_type,
        source_id=source_id,
        event_type=event_type,
        payload=payload,
        payload_hash=payload_hash,
        status=status,
    )
    session.add(row)
    await session.flush()
    if status == "blocked":
        logger.warning(
            "sentinel.forward_blocked",
            source_type=source_type,
            event_type=event_type,
            reason="sentinel not configured",
        )
    return row


def _sign(workspace_id: str, primary_key: str, body: str, date_str: str) -> str:
    string_to_hash = f"POST\n{len(body)}\napplication/json\nx-ms-date:{date_str}\n/api/logs"
    decoded = base64.b64decode(primary_key)
    digest = hmac.new(decoded, string_to_hash.encode("utf-8"), hashlib.sha256).digest()
    return f"SharedKey {workspace_id}:{base64.b64encode(digest).decode('ascii')}"


async def flush_pending(session: AsyncSession, *, limit: int = 100) -> dict[str, int]:
    """pending イベントを転送する。設定不足なら何も送らない。"""
    settings = get_settings()
    result = {"sent": 0, "failed": 0, "blocked": 0}
    if not is_configured():
        rows = (
            await session.execute(
                select(ExternalForwardEvent)
                .where(ExternalForwardEvent.status == "pending")
                .limit(limit)
            )
        ).scalars().all()
        for row in rows:
            row.status = "blocked"
            row.error = "sentinel not configured"
            result["blocked"] += 1
        await session.flush()
        return result

    workspace_id = settings.sentinel_workspace_id
    primary_key = settings.sentinel_primary_key.get_secret_value()
    dcr_uri = settings.sentinel_dcr_uri or (
        f"https://{workspace_id}.ods.opinsights.azure.com/api/logs?api-version=2016-04-01"
    )

    rows = (
        await session.execute(
            select(ExternalForwardEvent)
            .where(ExternalForwardEvent.status == "pending")
            .order_by(ExternalForwardEvent.id.asc())
            .limit(limit)
        )
    ).scalars().all()

    for row in rows:
        payload = {
            "source_type": row.source_type,
            "source_id": row.source_id,
            "event_type": row.event_type,
            "payload": row.payload,
            "payload_hash": row.payload_hash,
            "sent_at": datetime.now(UTC).isoformat(),
        }
        body = json.dumps({"LegalOpsAudit": [payload]}, ensure_ascii=False)
        date_str = datetime.now(UTC).strftime("%a, %d %b %Y %H:%M:%S GMT")
        headers = {
            "Content-Type": "application/json",
            "Log-Type": "LegalOpsAudit",
            "x-ms-date": date_str,
            "Authorization": _sign(workspace_id, primary_key, body, date_str),
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(dcr_uri, content=body.encode("utf-8"), headers=headers)
                resp.raise_for_status()
            row.status = "sent"
            row.forwarded_at = datetime.now(UTC)
            row.error = None
            result["sent"] += 1
        except Exception as exc:  # pragma: no cover - external failure path
            row.status = "failed"
            row.error = str(exc)[:2000]
            result["failed"] += 1
            logger.warning("sentinel.forward_failed", id=row.id, error=str(exc))
    await session.flush()
    return result


__all__ = ["configuration_errors", "enqueue_event", "flush_pending", "is_configured"]
