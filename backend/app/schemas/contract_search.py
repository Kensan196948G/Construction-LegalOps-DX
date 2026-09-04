"""契約書全文検索 API スキーマ（Issue #100）."""

from __future__ import annotations

from pydantic import BaseModel


class ContractSearchHit(BaseModel):
    """検索ヒット 1 件（スコア降順）."""

    kind: str  # contract / clause / document
    record_id: int
    contract_id: int
    contract_no: str | None
    title: str | None
    snippet: str | None
    matched_fields: list[str]
    score: float
