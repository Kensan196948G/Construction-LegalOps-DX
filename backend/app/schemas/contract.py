"""Contract Pydantic schemas.

Mirrors ``docs/api_design.md`` section 5. Date / amount validation uses
Pydantic v2 ``Field`` constraints; cross-field constraints (e.g. end_date >=
start_date) are enforced both at the DB layer (CHECK constraint) and in the
``model_validator`` below for early failure with field-level errors.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

from app.models.enums import Confidentiality, ContractStatus

from .common import ORMModel, TimestampsMixin
from .user import DepartmentBrief


class UserBrief(ORMModel):
    id: int
    display_name: str


class ContractBase(BaseModel):
    """Fields common to create / update / read."""

    title: Annotated[str, Field(min_length=1, max_length=256)]
    counterparty: Annotated[str, Field(min_length=1, max_length=256)]
    contract_type: Annotated[str, Field(min_length=1, max_length=64)]
    amount: Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2)] | None = None
    currency: Annotated[str, Field(min_length=3, max_length=3)] = "JPY"
    start_date: date | None = None
    end_date: date | None = None
    department_id: int
    confidentiality: Confidentiality = Confidentiality.NORMAL
    extra_metadata: dict[str, Any] = Field(default_factory=dict, alias="metadata")

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def _check_date_order(self) -> ContractBase:
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date < self.start_date
        ):
            raise ValueError("end_date must be on or after start_date")
        return self


class ContractCreate(ContractBase):
    """Body of ``POST /contracts``. ``contract_no`` is assigned server-side."""


class ContractUpdate(BaseModel):
    """Patch payload for ``PATCH /contracts/{id}``."""

    title: str | None = Field(default=None, max_length=256)
    counterparty: str | None = Field(default=None, max_length=256)
    contract_type: str | None = Field(default=None, max_length=64)
    amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    start_date: date | None = None
    end_date: date | None = None
    department_id: int | None = None
    confidentiality: Confidentiality | None = None
    status: ContractStatus | None = None
    extra_metadata: dict[str, Any] | None = Field(default=None, alias="metadata")
    version: int = Field(..., description="Optimistic-lock token (current row version)")

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def _check_date_order(self) -> ContractUpdate:
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date < self.start_date
        ):
            raise ValueError("end_date must be on or after start_date")
        return self


class ContractRead(ORMModel, TimestampsMixin):
    """Read schema for ``GET /contracts`` list items."""

    id: int
    contract_no: str
    title: str
    counterparty: str
    contract_type: str
    amount: Decimal | None = None
    currency: str
    start_date: date | None = None
    end_date: date | None = None
    status: ContractStatus
    confidentiality: Confidentiality
    version: int
    department: DepartmentBrief | None = None
    drafter: UserBrief | None = None


class ContractDetail(ContractRead):
    """Detailed read schema for ``GET /contracts/{id}``."""

    sharepoint_item_id: str | None = None
    extra_metadata: dict[str, Any] = Field(
        default_factory=dict,
        # When loading from ORM objects, try 'extra_metadata' first to avoid
        # collision with SQLAlchemy's inherited MetaData() on all Base models.
        validation_alias=AliasChoices("extra_metadata", "metadata"),
        serialization_alias="metadata",
    )
    drafter_id: int | None = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ContractList(BaseModel):
    """Bare list payload (without envelope) for handlers that compose them."""

    items: list[ContractRead]
    total: int
    page: int
    page_size: int


class ContractSubmitResponse(ORMModel):
    """Returned by ``POST /contracts/{id}/submit``."""

    id: int
    status: ContractStatus
    submitted_at: datetime


# ---------------------------------------------------------------------------
# v1 public-API aliases (see ``docs/api_design.md`` section 5)
# ---------------------------------------------------------------------------


class ContractOut(ContractDetail):
    """``GET /contracts/{id}`` and list-row schema."""


class ContractVersionOut(ORMModel):
    """One historical version row for ``GET /contracts/{id}/versions``."""

    id: int
    contract_id: int
    version: int
    title: str | None = None
    status: ContractStatus | None = None
    sharepoint_item_id: str | None = None
    created_at: datetime
    created_by: int | None = None


__all__ = [
    "ContractBase",
    "ContractCreate",
    "ContractDetail",
    "ContractList",
    "ContractOut",
    "ContractRead",
    "ContractSubmitResponse",
    "ContractUpdate",
    "ContractVersionOut",
    "UserBrief",
]
