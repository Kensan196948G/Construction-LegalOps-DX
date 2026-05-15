"""Notification Pydantic schemas.

Mirrors ``docs/api_design.md`` section 10.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, Field

from .common import ORMModel


class NotificationOut(ORMModel):
    """Read schema for one notification row."""

    id: int
    user_id: int
    channel: Annotated[str, Field(max_length=16)]
    title: str
    body: Optional[str] = None
    status: Annotated[str, Field(pattern="^(unread|read)$")] = "unread"
    related_type: Optional[str] = None
    related_id: Optional[int] = None
    created_at: datetime
    read_at: Optional[datetime] = None


class NotificationReadResult(BaseModel):
    """Response of ``PATCH /notifications/{id}/read`` and read-all."""

    updated: int = Field(default=0, ge=0)


__all__ = ["NotificationOut", "NotificationReadResult"]
