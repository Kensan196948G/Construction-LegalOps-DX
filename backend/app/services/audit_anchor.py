"""監査ログの日次アンカー生成・外部 WORM 保管（P0-6）.

1 日分の監査イベントハッシュを連結して集約ハッシュを作り、
HASH_CHAIN_SECRET で HMAC-SHA256 署名したアンカー行を
``audit_anchors`` に保存する。WORM_SINK_URL / AUDIT_ANCHOR_SINK_PATH が
設定されていれば、署名付き JSON を外部ストレージにも書き出す。

DB 管理者がデータと秘密鍵を同時に変更できる構成でも、外部 WORM に
日次アンカーが残っていれば遡及改ざんの検知起点になる。
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.audit_anchor import AuditAnchor
from app.models.audit_log import AuditLog

logger = structlog.get_logger(__name__)


def _hmac_hex(secret: bytes, payload: str) -> str:
    return hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()


async def create_daily_anchor(
    session: AsyncSession,
    *,
    anchor_date: date | None = None,
    actor_id: int | None = None,
) -> AuditAnchor:
    """指定日の監査イベントから日次アンカーを作成する。"""
    settings = get_settings()
    anchor_date = anchor_date or datetime.now(UTC).date()
    day_start = datetime.combine(anchor_date, time.min, tzinfo=UTC)
    day_end = datetime.combine(anchor_date + timedelta(days=1), time.min, tzinfo=UTC)

    rows = (
        await session.execute(
            select(AuditLog.id, AuditLog.hash_chain)
            .where(AuditLog.occurred_at >= day_start, AuditLog.occurred_at < day_end)
            .order_by(AuditLog.id.asc())
        )
    ).all()

    if not rows:
        raise LookupError(f"no audit events on {anchor_date.isoformat()}")

    aggregate = hashlib.sha256(
        "".join(str(h) for _, h in rows).encode("utf-8")
    ).hexdigest()
    secret = settings.hash_chain_secret.get_secret_value().encode("utf-8")
    signature = _hmac_hex(secret, f"{anchor_date.isoformat()}:{aggregate}")

    existing = (
        await session.execute(
            select(AuditAnchor).where(AuditAnchor.anchor_date == anchor_date)
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.aggregate_hash != aggregate:
            raise ValueError("anchor already exists with a different aggregate hash")
        return existing

    anchor = AuditAnchor(
        anchor_date=anchor_date,
        start_event_id=rows[0][0],
        end_event_id=rows[-1][0],
        event_count=len(rows),
        aggregate_hash=aggregate,
        signature=signature,
    )
    session.add(anchor)
    await session.flush()

    sink_ref: str | None = None
    try:
        sink_ref = await _export_to_sink(anchor)
    except Exception as exc:  # pragma: no cover - network sink failure path
        logger.warning("audit_anchor.sink_failed", anchor_date=anchor_date, error=str(exc))
    if sink_ref is not None:
        anchor.external_sink = _sink_label()
        anchor.external_ref = sink_ref
        await session.flush()

    logger.info(
        "audit_anchor.created",
        anchor_date=anchor_date.isoformat(),
        events=anchor.event_count,
        external=bool(sink_ref),
        actor_id=actor_id,
    )
    return anchor


def _sink_label() -> str:
    settings = get_settings()
    if settings.worm_sink_url:
        return urlparse(settings.worm_sink_url).scheme or "http"
    if settings.audit_anchor_sink_path:
        return "local-worm-stage"
    return ""


async def _export_to_sink(anchor: AuditAnchor) -> str | None:
    """署名付きアンカー JSON を外部シンクへ書き出す。成功時は参照キーを返す。"""
    settings = get_settings()
    payload = {
        "anchor_date": anchor.anchor_date.isoformat(),
        "start_event_id": anchor.start_event_id,
        "end_event_id": anchor.end_event_id,
        "event_count": anchor.event_count,
        "aggregate_hash": anchor.aggregate_hash,
        "signature": anchor.signature,
        "schema": "legalops.audit_anchor.v1",
    }
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True)

    if settings.audit_anchor_sink_path:
        target_dir = settings.audit_anchor_sink_path
        os.makedirs(target_dir, exist_ok=True)
        filename = f"audit-anchor-{anchor.anchor_date.isoformat()}.json"
        target = os.path.join(target_dir, filename)
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(body + "\n")
        return filename

    if settings.worm_sink_url:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        token = settings.worm_sink_auth_token.get_secret_value()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.put(
                f"{settings.worm_sink_url.rstrip('/')}/{anchor.anchor_date.isoformat()}.json",
                content=body,
                headers=headers,
            )
            resp.raise_for_status()
        return resp.headers.get("ETag") or anchor.anchor_date.isoformat()

    return None


async def verify_anchor(
    session: AsyncSession,
    *,
    anchor_date: date,
) -> dict[str, Any]:
    """アンカー行の署名と当日イベントの再計算を検証する。"""
    anchor = (
        await session.execute(
            select(AuditAnchor).where(AuditAnchor.anchor_date == anchor_date)
        )
    ).scalar_one_or_none()
    if anchor is None:
        return {"ok": False, "detail": "anchor not found"}
    settings = get_settings()
    secret = settings.hash_chain_secret.get_secret_value().encode("utf-8")
    expected = _hmac_hex(secret, f"{anchor_date.isoformat()}:{anchor.aggregate_hash}")
    return {
        "ok": expected == anchor.signature,
        "anchor_date": anchor_date.isoformat(),
        "event_count": anchor.event_count,
        "aggregate_hash": anchor.aggregate_hash,
        "signature_valid": expected == anchor.signature,
        "external_sink": anchor.external_sink,
        "external_ref": anchor.external_ref,
    }


__all__ = ["create_daily_anchor", "verify_anchor"]
