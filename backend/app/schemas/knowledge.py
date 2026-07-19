"""Knowledge-base Pydantic schemas.

Mirrors ``docs/api_design.md`` section 11. The service is DB-backed today;
future vector indexes can reuse these stable response shapes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

from .common import ORMModel


class KnowledgeArticleCreate(BaseModel):
    """Body of ``POST /knowledge``."""

    title: Annotated[str, Field(min_length=1, max_length=256)]
    body: Annotated[str, Field(min_length=1)]
    tags: list[str] = Field(default_factory=list)
    contract_type: str | None = None
    citations: list[str] = Field(default_factory=list)


class KnowledgeArticleOut(ORMModel):
    """Read schema for ``GET /knowledge/{id}``."""

    id: int
    title: str
    body: str
    tags: list[str] = Field(default_factory=list)
    contract_type: str | None = None
    citations: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class KnowledgeSearchResult(BaseModel):
    """Single hit from ``GET /knowledge/search``."""

    id: int
    title: str
    snippet: str
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)


class SimilarContractOut(BaseModel):
    """Single similar contract returned by ``GET /knowledge/similar/{id}``."""

    id: int
    contract_no: str
    title: str
    similarity: float = Field(default=0.0, ge=0.0, le=1.0)
    counterparty: str | None = None


__all__ = [
    "KnowledgeArticleCreate",
    "KnowledgeArticleOut",
    "KnowledgeSearchResult",
    "SimilarContractOut",
]
