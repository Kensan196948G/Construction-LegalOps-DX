"""Knowledge-base Pydantic schemas (stub).

Mirrors ``docs/api_design.md`` section 14. The semantic / vector search
integration lands later in Loop 5; the schemas here cover the API
contract so the frontend can wire against stable shapes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, List, Optional

from pydantic import BaseModel, Field

from .common import ORMModel


class KnowledgeArticleCreate(BaseModel):
    """Body of ``POST /knowledge``."""

    title: Annotated[str, Field(min_length=1, max_length=256)]
    body: Annotated[str, Field(min_length=1)]
    tags: List[str] = Field(default_factory=list)
    contract_type: Optional[str] = None
    citations: List[str] = Field(default_factory=list)


class KnowledgeArticleOut(ORMModel):
    """Read schema for ``GET /knowledge/{id}``."""

    id: int
    title: str
    body: str
    tags: List[str] = Field(default_factory=list)
    contract_type: Optional[str] = None
    citations: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class KnowledgeSearchResult(BaseModel):
    """Single hit from ``GET /knowledge/search``."""

    id: int
    title: str
    snippet: str
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    tags: List[str] = Field(default_factory=list)


class SimilarContractOut(BaseModel):
    """Single similar contract returned by ``GET /knowledge/similar/{id}``."""

    id: int
    contract_no: str
    title: str
    similarity: float = Field(default=0.0, ge=0.0, le=1.0)
    counterparty: Optional[str] = None


__all__ = [
    "KnowledgeArticleCreate",
    "KnowledgeArticleOut",
    "KnowledgeSearchResult",
    "SimilarContractOut",
]
