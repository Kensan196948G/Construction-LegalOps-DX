"""Common Pydantic v2 schema primitives.

Provides pagination, sort, filter, RFC 7807 problem details, and a
``TimestampsMixin`` used by read schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    """Base for read-side schemas that load from SQLAlchemy ORM rows."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class TimestampsMixin(BaseModel):
    """``created_at`` / ``updated_at`` / ``deleted_at`` for read schemas."""

    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class Pagination(BaseModel):
    """Pagination metadata returned alongside list responses."""

    page: Annotated[int, Field(ge=1)] = 1
    page_size: Annotated[int, Field(ge=1, le=200)] = 20
    total: Annotated[int, Field(ge=0)] = 0


class PageRequest(BaseModel):
    """Query parameters for paginated list endpoints."""

    page: Annotated[int, Field(ge=1)] = 1
    page_size: Annotated[int, Field(ge=1, le=200)] = 20


class Sort(BaseModel):
    """Sort descriptor: ``field`` (asc) or ``-field`` (desc)."""

    field: str
    direction: Annotated[str, Field(pattern="^(asc|desc)$")] = "asc"


class FilterBase(BaseModel):
    """Base class for endpoint-specific filter parameters."""

    q: str | None = None


class Meta(BaseModel):
    """Response ``meta`` block per ``docs/api_design.md`` section 2.2."""

    request_id: str | None = None
    page: int | None = None
    page_size: int | None = None
    total: int | None = None


class Envelope[T](BaseModel):
    """Generic ``{ data, meta }`` envelope used by all API responses."""

    data: T
    meta: Meta | None = None


class ProblemDetailError(BaseModel):
    """Single field-level error inside :class:`ProblemDetails.errors`."""

    field: str
    message: str


class ProblemDetails(BaseModel):
    """RFC 7807 error response body."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
    errors: list[ProblemDetailError] | None = None
    request_id: str | None = None


class IdResponse(BaseModel):
    """Convenience response when only an ``id`` is returned (e.g. async jobs)."""

    id: int
    extra: dict[str, Any] | None = None


class Page[T](BaseModel):
    """Generic paginated list payload used across the v1 API.

    Routers populate ``items`` with their concrete read schema and report
    pagination metadata side-by-side; this avoids the per-endpoint
    boilerplate of redeclaring ``items / total / page / size`` everywhere.
    """

    items: list[T] = Field(default_factory=list)
    total: Annotated[int, Field(ge=0)] = 0
    page: Annotated[int, Field(ge=1)] = 1
    size: Annotated[int, Field(ge=1, le=500)] = 20
