"""Template / clause-library Pydantic schemas.

Mirrors ``docs/api_design.md`` section 16.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, List, Optional

from pydantic import BaseModel, Field

from .common import ORMModel


class TemplateCreate(BaseModel):
    """Body of ``POST /templates``."""

    code: Annotated[str, Field(min_length=1, max_length=64)]
    name: Annotated[str, Field(min_length=1, max_length=256)]
    contract_type: Annotated[str, Field(min_length=1, max_length=64)]
    description: Optional[str] = None
    body: Annotated[str, Field(min_length=1)]
    is_active: bool = True


class TemplateOut(ORMModel):
    """Read schema for templates."""

    id: int
    code: str
    name: str
    contract_type: str
    description: Optional[str] = None
    body: str
    is_active: bool = True
    version: int = 1
    created_at: datetime
    updated_at: datetime


class ClauseLibraryCreate(BaseModel):
    """Body of ``POST /clauses-library``."""

    code: Annotated[str, Field(min_length=1, max_length=64)]
    title: Annotated[str, Field(min_length=1, max_length=256)]
    category: Annotated[str, Field(min_length=1, max_length=64)]
    recommendation: Annotated[
        str, Field(pattern="^(recommended|caution|prohibited|neutral)$")
    ] = "neutral"
    text: Annotated[str, Field(min_length=1)]
    tags: List[str] = Field(default_factory=list)


class ClauseLibraryUpdate(BaseModel):
    """Patch payload for ``PATCH /clauses-library/{id}``."""

    title: Optional[str] = Field(default=None, max_length=256)
    category: Optional[str] = Field(default=None, max_length=64)
    recommendation: Optional[str] = Field(
        default=None, pattern="^(recommended|caution|prohibited|neutral)$"
    )
    text: Optional[str] = None
    tags: Optional[List[str]] = None


class ClauseLibraryOut(ORMModel):
    """Read schema for clause-library entries."""

    id: int
    code: str
    title: str
    category: str
    recommendation: str
    text: str
    tags: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


__all__ = [
    "ClauseLibraryCreate",
    "ClauseLibraryOut",
    "ClauseLibraryUpdate",
    "TemplateCreate",
    "TemplateOut",
]
