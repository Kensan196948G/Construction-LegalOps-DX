"""保存期間ポリシーと Legal Hold（P0-6）.

- security_settings テーブルで AI 入出力の保存期間・WORM 出力先を管理。
- purge_ai_artifacts は Legal Hold 中の契約を尊重して古い AI 出力を消去。
- governance 互換の ensure_default_rules / enforce_ai_retention も提供。
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import config
from app.models.access_control import LegalHold
from app.models.audit_log import AuditLog
from app.models.legal_review import LegalReview
from app.models.retention import RetentionRule
from app.models.security_settings import SecuritySetting

logger = structlog.get_logger(__name__)

DEFAULT_AI_RETENTION_DAYS: int = 365
DEFAULT_AUDIT_EXPORT_DIR: str = "./data/worm-export"

_ALLOWED_KEYS: frozenset[str] = frozenset({"ai_retention_days", "audit_export_dir"})


def _default_settings() -> dict[str, Any]:
    return {
        "ai_retention_days": DEFAULT_AI_RETENTION_DAYS,
        "audit_export_dir": os.getenv("WORM_ARCHIVE_PATH") or DEFAULT_AUDIT_EXPORT_DIR,
    }


async def get_settings(session: AsyncSession) -> dict[str, Any]:
    """保存期間設定を返す（security_settings があれば上書き）。"""
    result = _default_settings()
    rows = (
        await session.execute(select(SecuritySetting).order_by(SecuritySetting.key.asc()))
    ).scalars().all()
    for row in rows:
        value = row.value
        if isinstance(value, dict) and "value" in value:
            result[row.key] = value["value"]
        else:
            result[row.key] = value
    return result


async def update_settings(
    session: AsyncSession,
    *,
    values: dict[str, Any],
    actor_id: int | None,
) -> dict[str, Any]:
    """保持期間設定を更新する。未知キーは ValueError。"""
    unknown = sorted(set(values) - _ALLOWED_KEYS)
    if unknown:
        raise ValueError(f"unknown settings key: {', '.join(unknown)}")
    for key, value in values.items():
        if key == "ai_retention_days":
            try:
                days = int(value)
            except (TypeError, ValueError):
                raise ValueError("ai_retention_days must be an integer") from None
            if days < 1:
                raise ValueError("ai_retention_days must be >= 1")
            stored: dict[str, Any] = {"value": days}
        elif key == "audit_export_dir":
            if not isinstance(value, str) or not value.strip():
                raise ValueError("audit_export_dir must be a non-empty string")
            stored = {"value": value.strip()}
        else:  # pragma: no cover - guarded by unknown check
            continue
        row = (
            await session.execute(
                select(SecuritySetting).where(SecuritySetting.key == key)
            )
        ).scalar_one_or_none()
        if row is None:
            row = SecuritySetting(key=key, value=stored, updated_by=actor_id)
            session.add(row)
        else:
            row.value = stored
            row.updated_by = actor_id
    await session.flush()
    return await get_settings(session)


async def is_under_legal_hold(session: AsyncSession, *, contract_id: int) -> bool:
    """契約が Legal Hold 中かを判定する（legal_hold_cases と legal_holds 双方を確認）。"""
    from app.models.legal_hold import LegalHoldCase
    from app.services import legal_hold_service

    if await legal_hold_service.is_under_legal_hold(session, contract_id=contract_id):
        return True
    rows = await session.execute(
        select(LegalHold.id).where(
            LegalHold.target_type == "contracts",
            LegalHold.target_id == contract_id,
            LegalHold.status == "active",
        ).limit(1)
    )
    if rows.scalar_one_or_none() is not None:
        return True
    rows2 = await session.execute(
        select(LegalHoldCase.id).where(
            LegalHoldCase.contract_id == contract_id,
            LegalHoldCase.ended_at.is_(None),
        ).limit(1)
    )
    return rows2.scalar_one_or_none() is not None


async def purge_ai_artifacts(
    session: AsyncSession,
    *,
    older_than_days: int,
    actor_id: int | None = None,
) -> dict[str, int]:
    """保存期間超過の AI 出力を消去する。Legal Hold 中はスキップ。"""
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=older_than_days)
    candidates = (
        await session.execute(
            select(LegalReview)
            .where(
                LegalReview.finished_at.is_not(None),
                LegalReview.finished_at < cutoff,
                LegalReview.status == "completed",
            )
            .order_by(LegalReview.id.asc())
            .limit(1000)
        )
    ).scalars().all()
    purged = 0
    skipped_legal_hold = 0
    for review in candidates:
        if await is_under_legal_hold(session, contract_id=review.contract_id):
            skipped_legal_hold += 1
            await _log_retention_event(
                session,
                action="retention.blocked",
                target_type="legal_reviews",
                target_id=review.id,
                detail={"reason": "legal_hold_active"},
                actor_id=actor_id,
            )
            continue
        if review.result:
            review.result = {}
            review.summary = (review.summary or "") + (
                f" [AI出力削除済み: {now.isoformat()}]"
            )
            purged += 1
            await _log_retention_event(
                session,
                action="retention.delete",
                target_type="legal_reviews",
                target_id=review.id,
                detail={"older_than_days": older_than_days},
                actor_id=actor_id,
            )
    await session.flush()
    return {"purged": purged, "skipped_legal_hold": skipped_legal_hold}


async def ensure_default_rules(session: AsyncSession) -> None:
    """governance 互換: retention_rules を seed する（冪等）。"""
    settings = config.get_settings()
    defaults = [
        ("ai_input", settings.retention_ai_input_days, "delete", "AI プロンプト入力"),
        ("ai_output", settings.retention_ai_output_days, "delete", "AI レビュー出力"),
        ("attachment", settings.retention_attachment_days, "delete", "添付ファイル"),
        ("audit_log", settings.audit_retention_years * 365, "archive", "監査ログ"),
    ]
    for data_type, days, action, note in defaults:
        exists = (
            await session.execute(
                select(RetentionRule).where(RetentionRule.data_type == data_type)
            )
        ).scalar_one_or_none()
        if exists is None:
            session.add(
                RetentionRule(
                    data_type=data_type,
                    retention_days=int(days),
                    action=action,
                    enabled=True,
                    note=note,
                )
            )
    await session.flush()


async def enforce_ai_retention(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    actor_id: int | None = None,
) -> dict[str, Any]:
    """governance 互換: ルールに基づき AI 出力を消去する。"""
    settings = config.get_settings()
    days = int(settings.retention_ai_output_days)
    stats = await purge_ai_artifacts(session, older_than_days=days, actor_id=actor_id)
    return {
        "deleted_inputs": 0,
        "deleted_outputs": stats["purged"],
        "blocked_by_hold": stats["skipped_legal_hold"],
    }


async def active_legal_holds(
    session: AsyncSession,
    *,
    target_type: str,
    target_id: int,
) -> list[LegalHold]:
    """governance 互換: LegalHold アクティブ一覧。"""
    rows = await session.execute(
        select(LegalHold).where(
            LegalHold.target_type == target_type,
            LegalHold.target_id == target_id,
            LegalHold.status == "active",
        )
    )
    return list(rows.scalars().all())


async def _log_retention_event(
    session: AsyncSession,
    *,
    action: str,
    target_type: str,
    target_id: int,
    detail: dict[str, Any],
    actor_id: int | None,
) -> None:
    import json

    canonical = json.dumps(detail, ensure_ascii=False, sort_keys=True)
    last = (
        await session.execute(
            select(AuditLog.hash_chain).order_by(AuditLog.id.desc()).limit(1)
        )
    ).scalar_one_or_none()
    session.add(
        AuditLog(
            actor_id=actor_id,
            actor_role="admin",
            action=action,
            target_type=target_type,
            target_id=target_id,
            payload=detail,
            previous_hash=last,
            hash_chain=AuditLog.compute_hash(last, canonical),
        )
    )


__all__ = [
    "DEFAULT_AI_RETENTION_DAYS",
    "DEFAULT_AUDIT_EXPORT_DIR",
    "active_legal_holds",
    "enforce_ai_retention",
    "ensure_default_rules",
    "get_settings",
    "is_under_legal_hold",
    "purge_ai_artifacts",
    "update_settings",
]
