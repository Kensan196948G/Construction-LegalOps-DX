"""監査ログの WORM 相当外部保存（JSONL + 日次アンカー署名）."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_export import AuditExportJob
from app.models.audit_log import AuditLog

from . import retention_service
from .sentinel_sink import send_batch

logger = logging.getLogger(__name__)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _sign_anchor(payload: str, private_key_hex: str | None) -> str | None:
    """Ed25519 で日次アンカーに署名する（鍵未設定なら None）。"""
    if not private_key_hex:
        return None
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
        )
        from cryptography.hazmat.primitives.serialization import (
            Encoding,
            PublicFormat,
        )

        key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_key_hex))
        signature = key.sign(payload.encode("utf-8"))
        # 公開鍵も併記して検証可能にする
        public_key = key.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw
        )
        return f"{public_key.hex()}:{signature.hex()}"
    except (ValueError, TypeError) as exc:
        logger.warning("audit_export.sign_failed: %s", exc)
        return None


async def export_audit_batch(
    session: AsyncSession,
    *,
    since: datetime,
    until: datetime,
    export_dir: str | None = None,
    actor_id: int | None = None,
) -> dict[str, Any]:
    """監査ログを JSONL で外部保存し、ジョブレコードを作成する."""
    settings = await retention_service.get_settings(session)
    target_dir = export_dir or str(settings.get("audit_export_dir", "./data/worm-export"))
    path = Path(target_dir)
    path.mkdir(parents=True, exist_ok=True)

    rows = (
        await session.execute(
            select(AuditLog)
            .where(
                AuditLog.occurred_at >= since,
                AuditLog.occurred_at < until,
            )
            .order_by(AuditLog.id)
        )
    ).scalars().all()

    job_no = f"EXP-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
    filename = f"audit-export-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}.jsonl"
    file_path = path / filename

    digest = hashlib.sha256()
    line_count = 0
    with file_path.open("w", encoding="utf-8") as fh:
        for row in rows:
            record = {
                "id": row.id,
                "occurred_at": row.occurred_at.isoformat(),
                "actor_id": row.actor_id,
                "actor_role": row.actor_role,
                "action": row.action,
                "target_type": row.target_type,
                "target_id": row.target_id,
                "request_id": str(row.request_id) if row.request_id else None,
                "ip_address": str(row.ip_address) if row.ip_address else None,
                "user_agent": row.user_agent,
                "payload": row.payload,
                "previous_hash": row.previous_hash,
                "hash_chain": row.hash_chain,
            }
            line = _canonical_json(record)
            fh.write(line + "\n")
            digest.update(line.encode("utf-8"))
            line_count += 1

    merkle_root = digest.hexdigest()
    # 日次アンカー: 全行連結ハッシュ + 署名（鍵設定時）
    import os

    private_key = os.getenv("AUDIT_ANCHOR_PRIVATE_KEY")
    signature = _sign_anchor(merkle_root, private_key)
    with file_path.open("a", encoding="utf-8") as fh:
        meta = {
            "merkle_root": merkle_root,
            "signature": signature,
            "algorithm": "sha256+ed25519" if signature else "sha256",
            "record_count": line_count,
        }
        fh.write(_canonical_json(meta) + "\n")

    job = AuditExportJob(
        job_no=job_no,
        exported_from=since,
        exported_to=until,
        record_count=line_count,
        file_path=str(file_path),
        signature=signature,
        status="completed",
        error_message=None,
        created_by=actor_id,
    )
    session.add(job)
    await session.flush()

    # Sentinel 転送（未設定なら何もしない）
    try:
        await send_batch(
            {
                "job_no": job_no,
                "record_count": line_count,
                "merkle_root": merkle_root,
                "exported_from": since.isoformat(),
                "exported_to": until.isoformat(),
            }
        )
    except Exception as exc:  # pragma: no cover - external sink
        logger.warning("audit_export.sentinel_failed: %s", exc)

    return {
        "job_no": job_no,
        "file_path": str(file_path),
        "record_count": line_count,
        "merkle_root": merkle_root,
        "signature": signature,
        "status": "completed",
    }


async def list_export_jobs(session: AsyncSession, *, limit: int = 50) -> list[AuditExportJob]:
    rows = await session.execute(
        select(AuditExportJob).order_by(AuditExportJob.id.desc()).limit(limit)
    )
    return list(rows.scalars().all())
