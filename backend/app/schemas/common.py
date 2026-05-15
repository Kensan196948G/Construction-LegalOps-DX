"""Common Pydantic v2 schema primitives.

Provides pagination, sort, filter, RFC 7807 problem details, and a
``TimestampsMixin`` used by read schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ORMModel(BaseModel):
    """Base for read-side schemas that load from SQLAlchemy ORM rows."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class TimestampsMixin(BaseModel):
    """``created_at`` / ``updated_at`` / ``deleted_at`` for read schemas."""

    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

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

    q: Optional[str] = None


class Meta(BaseModel):
    """Response ``meta`` block per ``docs/api_design.md`` section 2.2."""

    request_id: Optional[str] = None
    page: Optional[int] = None
    page_size: Optional[int] = None
    total: Optional[int] = None


class Envelope(BaseModel, Generic[T]):
    """Generic ``{ data, meta }`` envelope used by all API responses."""

    data: T
    meta: Optional[Meta] = None


class ProblemDetailError(BaseModel):
    """Single field-level error inside :class:`ProblemDetails.errors`."""

    field: str
    message: str


class ProblemDetails(BaseModel):
    """RFC 7807 error response body."""

    type: str = "about:blank"
    title: str
    status: int
    detail: Optional[str] = None
    instance: Optional[str] = None
    errors: Optional[List[ProblemDetailError]] = None
    request_id: Optional[str] = None


class IdResponse(BaseModel):
    """Convenience response when only an ``id`` is returned (e.g. async jobs)."""

    id: int
    extra: Optional[dict[str, Any]] = None


class Page(BaseModel, Generic[T]):
    """Generic paginated list payload used across the v1 API.

    Routers populate ``items`` with their concrete read schema and report
    pagination metadata side-by-side; this avoids the per-endpoint
    boilerplate of redeclaring ``items / total / page / size`` everywhere.
    """

    items: List[T] = Field(default_factory=list)
    total: Annotated[int, Field(ge=0)] = 0
    page: Annotated[int, Field(ge=1)] = 1
    size: Annotated[int, Field(ge=1, le=500)] = 20
