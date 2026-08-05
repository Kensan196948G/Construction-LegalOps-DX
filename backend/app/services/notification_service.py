"""Notification service (Exchange Online / Teams / DeskNet's Neo).

Outbound senders remain adapter-backed so local and CI runs do not depend
on external messaging services. User-facing notification center APIs are
DB-backed through the ``notifications`` table.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, cast
from uuid import UUID, uuid4

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.enums import NotificationChannel, NotificationStatus
from app.models.notification import Notification

logger = structlog.get_logger(__name__)

_GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
_GRAPH_SCOPE = "https://graph.microsoft.com/.default"
_HTTP_TIMEOUT = 10.0


class NotificationError(RuntimeError):
    """Raised when a notification cannot be queued or sent."""


class TeamsCardKind(StrEnum):
    APPROVAL_REQUEST = "approval_request"
    SLA_WARNING = "sla_warning"
    SLA_BREACH = "sla_breach"
    OUTSIDE_COUNSEL_FLAG = "outside_counsel_flag"
    SEND_BACK = "send_back"
    INFO = "info"


@dataclass(slots=True)
class NotificationRecord:
    id: UUID
    channel: NotificationChannel
    status: NotificationStatus
    to: tuple[str, ...]
    subject: str
    body: str
    sent_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


class NotificationService:
    """Multi-channel notification dispatcher with an in-memory local adapter."""

    def __init__(
        self,
        *,
        mode: str | None = None,
        graph_sender: str | None = None,
        teams_webhook_url: str | None = None,
        desknets_webhook_url: str | None = None,
    ) -> None:
        settings = get_settings()
        self._mode = (mode or os.getenv("NOTIFY_MODE", "stub") or "stub").lower()
        if self._mode not in {"stub", "real", "queued", "disabled"}:
            raise RuntimeError(
                "NOTIFY_MODE must be 'stub', 'real', 'queued', or 'disabled', "
                f"got {self._mode!r}"
            )
        if settings.is_production and self._mode == "stub":
            raise RuntimeError(
                "NOTIFY_MODE=stub is disabled when APP_ENV=production "
                "(use NOTIFY_MODE=disabled for in-app-only delivery)"
            )
        self._graph_sender = graph_sender or os.getenv("EXCHANGE_SENDER_UPN", "").strip()
        self._teams_webhook_url = teams_webhook_url or os.getenv("TEAMS_WEBHOOK_URL", "").strip()
        self._desknets_webhook_url = (
            desknets_webhook_url or os.getenv("DESKNETS_WEBHOOK_URL", "").strip()
        )
        self._graph_access_token: str | None = None
        self._sent: list[NotificationRecord] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def send_email(
        self,
        to: list[str] | tuple[str, ...],
        subject: str,
        body: str,
        *,
        cc: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> NotificationRecord:
        """Queue an email through Exchange Online (Microsoft Graph)."""
        if not to:
            raise NotificationError("at least one recipient is required")

        record = NotificationRecord(
            id=uuid4(),
            channel=NotificationChannel.MAIL,
            status=(
                NotificationStatus.SENT
                if self._mode in ("stub", "disabled")
                else NotificationStatus.QUEUED
            ),
            to=tuple(to),
            subject=subject,
            body=body,
            sent_at=datetime.now(UTC),
            metadata={"cc": list(cc or []), **(metadata or {})},
        )
        if self._mode == "real":
            self._send_graph_mail(record)
            record.status = NotificationStatus.SENT
        self._sent.append(record)
        logger.info(
            "notify.email",
            mode=self._mode,
            to=record.to,
            subject=subject,
        )
        return record

    async def send_teams_card(
        self,
        channel_or_user: str,
        title: str,
        body: str,
        *,
        kind: TeamsCardKind = TeamsCardKind.INFO,
        deep_link: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> NotificationRecord:
        """Send a Microsoft Teams adaptive card."""
        record = NotificationRecord(
            id=uuid4(),
            channel=NotificationChannel.TEAMS,
            status=(
                NotificationStatus.SENT
                if self._mode in ("stub", "disabled")
                else NotificationStatus.QUEUED
            ),
            to=(channel_or_user,),
            subject=title,
            body=body,
            sent_at=datetime.now(UTC),
            metadata={
                "kind": kind.value,
                "deep_link": deep_link,
                **(metadata or {}),
            },
        )
        if self._mode == "real":
            self._post_webhook(
                self._teams_webhook_url,
                payload={
                    "type": "message",
                    "attachments": [
                        {
                            "contentType": "application/vnd.microsoft.card.adaptive",
                            "content": {
                                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                                "type": "AdaptiveCard",
                                "version": "1.5",
                                "body": [
                                    {"type": "TextBlock", "weight": "Bolder", "text": title},
                                    {"type": "TextBlock", "wrap": True, "text": body},
                                ],
                                "actions": (
                                    [
                                        {
                                            "type": "Action.OpenUrl",
                                            "title": "Open LegalOps",
                                            "url": deep_link,
                                        }
                                    ]
                                    if deep_link
                                    else []
                                ),
                            },
                        }
                    ],
                },
                action="notify.teams",
                missing_message="TEAMS_WEBHOOK_URL is required for real Teams notifications",
            )
            record.status = NotificationStatus.SENT
        self._sent.append(record)
        logger.info(
            "notify.teams",
            mode=self._mode,
            target=channel_or_user,
            kind=kind.value,
        )
        return record

    async def send_desknets(
        self,
        upn: str,
        subject: str,
        body: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> NotificationRecord:
        """Send a DeskNet's Neo workflow notification (stub)."""
        if not upn:
            raise NotificationError("DeskNet's recipient UPN is required")

        record = NotificationRecord(
            id=uuid4(),
            channel=NotificationChannel.DESKNETS,
            status=(
                NotificationStatus.SENT
                if self._mode in ("stub", "disabled")
                else NotificationStatus.QUEUED
            ),
            to=(upn,),
            subject=subject,
            body=body,
            sent_at=datetime.now(UTC),
            metadata=metadata or {},
        )
        if self._mode == "real":
            self._post_webhook(
                self._desknets_webhook_url,
                payload={
                    "to": upn,
                    "subject": subject,
                    "body": body,
                    "metadata": metadata or {},
                },
                action="notify.desknets",
                missing_message="DESKNETS_WEBHOOK_URL is required for real DeskNet's notifications",
            )
            record.status = NotificationStatus.SENT
        self._sent.append(record)
        logger.info("notify.desknets", mode=self._mode, upn=upn)
        return record

    # ------------------------------------------------------------------
    # Test / introspection helpers
    # ------------------------------------------------------------------

    def sent(self) -> list[NotificationRecord]:
        """Return all in-memory records (stub mode)."""
        return list(self._sent)

    def clear(self) -> None:
        self._sent.clear()

    # ------------------------------------------------------------------
    # Real adapters
    # ------------------------------------------------------------------

    def _send_graph_mail(self, record: NotificationRecord) -> None:
        sender = self._require_graph_sender()
        message = {
            "subject": record.subject,
            "body": {"contentType": "Text", "content": record.body},
            "toRecipients": [{"emailAddress": {"address": recipient}} for recipient in record.to],
            "ccRecipients": [
                {"emailAddress": {"address": recipient}}
                for recipient in record.metadata.get("cc", [])
            ],
        }
        encoded_sender = urllib.parse.quote(sender, safe="")
        url = f"{_GRAPH_BASE_URL}/users/{encoded_sender}/sendMail"
        req = urllib.request.Request(  # noqa: S310  # nosec B310
            url,
            data=json.dumps({"message": message, "saveToSentItems": True}).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {self._graph_token()}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        self._read_response(req, action="notify.email")

    def _require_graph_sender(self) -> str:
        if not self._graph_sender:
            raise NotificationError("EXCHANGE_SENDER_UPN is required for real email notifications")
        return self._graph_sender

    def _graph_token(self) -> str:
        if self._graph_access_token:
            return self._graph_access_token
        settings = get_settings()
        token_url = (
            f"https://login.microsoftonline.com/{settings.entra_tenant_id}/oauth2/v2.0/token"
        )
        body = urllib.parse.urlencode(
            {
                "client_id": settings.entra_client_id,
                "client_secret": settings.entra_client_secret.get_secret_value(),
                "grant_type": "client_credentials",
                "scope": _GRAPH_SCOPE,
            }
        ).encode("utf-8")
        # 接続先は Microsoft 固定エンドポイントのみ（ユーザー入力 URL は不使用）
        req = urllib.request.Request(
            token_url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
        )
        payload = self._read_json(req, action="notify.graph_token")
        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            raise NotificationError("Graph token response missing access_token")
        self._graph_access_token = token
        return token

    def _post_webhook(
        self,
        url: str,
        *,
        payload: dict[str, Any],
        action: str,
        missing_message: str,
    ) -> None:
        if not url:
            raise NotificationError(missing_message)
        req = urllib.request.Request(  # noqa: S310  # nosec B310
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        self._read_response(req, action=action)

    def _read_json(self, req: urllib.request.Request, *, action: str) -> dict[str, Any]:
        raw = self._read_response(req, action=action)
        if not raw:
            return {}
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise NotificationError(f"{action} returned invalid JSON") from exc
        if not isinstance(parsed, dict):
            raise NotificationError(f"{action} returned a non-object JSON payload")
        if "error" in parsed:
            raise NotificationError(f"{action} rejected request")
        return parsed

    def _read_response(self, req: urllib.request.Request, *, action: str) -> bytes:
        try:
            with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:  # noqa: S310  # nosec B310
                return cast(bytes, resp.read())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            logger.warning(action, status=exc.code, detail=detail[:512])
            raise NotificationError(f"{action} failed with HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise NotificationError(f"{action} endpoint unreachable: {exc.reason}") from exc


# ---------------------------------------------------------------------------
# Module-level convenience wrappers for notification-center CRUD.
# ---------------------------------------------------------------------------

from app.schemas.notification import NotificationOut  # noqa: E402

_nsvc: NotificationService = NotificationService()


def _to_out(notification: Notification) -> NotificationOut:
    """Map the persistence model to the public notification-center schema."""
    return NotificationOut(
        id=notification.id,
        user_id=notification.recipient_id,
        channel=notification.channel,
        title=notification.subject,
        body=notification.body,
        status="read" if notification.read_at is not None else "unread",
        related_type="contract" if notification.contract_id is not None else None,
        related_id=notification.contract_id,
        created_at=notification.created_at,
        read_at=notification.read_at,
    )


def _normalise_channel(channel: str | None) -> str | None:
    if channel is None:
        return None
    mapped = "mail" if channel == "email" else channel
    allowed = {item.value for item in NotificationChannel}
    if mapped not in allowed:
        raise ValueError(f"unsupported notification channel: {channel}")
    return mapped


def _apply_filters(statement: Any, *, user_id: Any, status: str | None, channel: str | None) -> Any:
    statement = statement.where(
        Notification.recipient_id == user_id,
        Notification.deleted_at.is_(None),
    )
    if status == "unread":
        statement = statement.where(Notification.read_at.is_(None))
    elif status == "read":
        statement = statement.where(Notification.read_at.is_not(None))
    elif status is not None:
        raise ValueError(f"unsupported notification status: {status}")
    normalised_channel = _normalise_channel(channel)
    if normalised_channel is not None:
        statement = statement.where(Notification.channel == normalised_channel)
    return statement


async def list_for_user(
    session: AsyncSession,
    *,
    user_id: Any,
    status: str | None = None,
    channel: str | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[NotificationOut], int]:
    """Return a paginated notification-center list for the authenticated user."""
    offset = max(page - 1, 0) * size
    total_statement = _apply_filters(
        select(func.count()).select_from(Notification),
        user_id=user_id,
        status=status,
        channel=channel,
    )
    total = int((await session.execute(total_statement)).scalar_one())

    items_statement = (
        _apply_filters(
            select(Notification),
            user_id=user_id,
            status=status,
            channel=channel,
        )
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset(offset)
        .limit(size)
    )
    rows = (await session.execute(items_statement)).scalars().all()
    return ([_to_out(row) for row in rows], total)


async def mark_read(
    session: AsyncSession,
    *,
    notification_id: Any,
    user_id: Any,
) -> NotificationOut:
    notification = (
        await session.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if notification is None:
        raise LookupError(f"notification {notification_id} not found")
    if notification.recipient_id != user_id:
        raise PermissionError(f"notification {notification_id} does not belong to user {user_id}")

    if notification.read_at is None:
        notification.read_at = datetime.now(UTC)
    notification.status = NotificationStatus.READ.value
    await session.flush()
    return _to_out(notification)


async def mark_all_read(
    session: AsyncSession,
    *,
    user_id: Any,
) -> int:
    rows = (
        (
            await session.execute(
                select(Notification).where(
                    Notification.recipient_id == user_id,
                    Notification.deleted_at.is_(None),
                    Notification.read_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    now = datetime.now(UTC)
    for notification in rows:
        notification.read_at = now
        notification.status = NotificationStatus.READ.value
    await session.flush()
    return len(rows)
