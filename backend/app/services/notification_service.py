"""Notification service (Exchange Online / Teams / DeskNet's Neo).

Loop 2 keeps every send in-memory so the rest of the platform can wire
up notification triggers without an external dependency. The recorded
messages can be inspected via :meth:`NotificationService.sent` in
tests.

Loop 4 will replace the channel-specific senders with real Microsoft
Graph (mail / Teams) and DeskNet's Neo API calls.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

import structlog

from app.models.enums import NotificationChannel, NotificationStatus

logger = structlog.get_logger(__name__)


class NotificationError(RuntimeError):
    """Raised when a notification cannot be queued or sent."""


class TeamsCardKind(str, Enum):
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
    """Multi-channel notification dispatcher with a stub backend."""

    def __init__(self, *, mode: str | None = None) -> None:
        self._mode = (mode or os.getenv("NOTIFY_MODE", "stub")).lower()
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
            status=NotificationStatus.SENT if self._mode == "stub" else NotificationStatus.QUEUED,
            to=tuple(to),
            subject=subject,
            body=body,
            sent_at=datetime.now(timezone.utc),
            metadata={"cc": list(cc or []), **(metadata or {})},
        )
        self._sent.append(record)
        logger.info(
            "notify.email",
            mode=self._mode,
            to=record.to,
            subject=subject,
        )
        # The real implementation would call Microsoft Graph here.
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
            status=NotificationStatus.SENT if self._mode == "stub" else NotificationStatus.QUEUED,
            to=(channel_or_user,),
            subject=title,
            body=body,
            sent_at=datetime.now(timezone.utc),
            metadata={
                "kind": kind.value,
                "deep_link": deep_link,
                **(metadata or {}),
            },
        )
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
        record = NotificationRecord(
            id=uuid4(),
            channel=NotificationChannel.DESKNETS,
            status=NotificationStatus.SENT if self._mode == "stub" else NotificationStatus.QUEUED,
            to=(upn,),
            subject=subject,
            body=body,
            sent_at=datetime.now(timezone.utc),
            metadata=metadata or {},
        )
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
