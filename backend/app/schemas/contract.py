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

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

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
    # ---- 法令適用・支払コンプライアンス正本カラム（P0-1 / 支払コンプライアンス） ----
    order_date: date | None = None
    receipt_date: date | None = None
    inspection_date: date | None = None
    payment_date: date | None = None
    transaction_kind: Annotated[
        str | None,
        Field(
            pattern="^(manufacturing|repair|information|service|transport|construction)$",
        ),
    ] = None
    is_public_work: bool = False
    handles_personal_data: bool = False
    our_capital_jpy: int | None = Field(default=None, ge=0)
    counterparty_capital_jpy: int | None = Field(default=None, ge=0)
    our_employees: int | None = Field(default=None, ge=0)
    counterparty_employees: int | None = Field(default=None, ge=0)
    case_category: Annotated[
        str | None,
        Field(pattern="^(normal|hr|bid_rigging|whistleblowing|legal)$"),
    ] = None
    ethical_wall: bool = False

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("contract_type")
    @classmethod
    def _normalize_contract_type(cls, value: str) -> str:
        from app.services.contract_type import normalize_contract_type

        normalized = normalize_contract_type(value)
        assert normalized is not None
        return normalized

    @model_validator(mode="after")
    def _check_date_order(self) -> ContractBase:
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date < self.start_date
        ):
            raise ValueError("end_date must be on or after start_date")
        dates = [
            ("order_date", self.order_date),
            ("receipt_date", self.receipt_date),
            ("inspection_date", self.inspection_date),
            ("payment_date", self.payment_date),
        ]
        previous: date | None = None
        previous_name: str | None = None
        for name, value in dates:
            if value is None:
                continue
            if previous is not None and value < previous:
                raise ValueError(f"{name} must be on or after {previous_name}")
            previous, previous_name = value, name
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
    order_date: date | None = None
    receipt_date: date | None = None
    inspection_date: date | None = None
    payment_date: date | None = None
    transaction_kind: Annotated[
        str | None,
        Field(pattern="^(manufacturing|repair|information|service|transport|construction)$"),
    ] = None
    is_public_work: bool | None = None
    handles_personal_data: bool | None = None
    our_capital_jpy: int | None = Field(default=None, ge=0)
    counterparty_capital_jpy: int | None = Field(default=None, ge=0)
    our_employees: int | None = Field(default=None, ge=0)
    counterparty_employees: int | None = Field(default=None, ge=0)
    case_category: Annotated[
        str | None,
        Field(pattern="^(normal|hr|bid_rigging|whistleblowing|legal)$"),
    ] = None
    ethical_wall: bool | None = None
    version: int = Field(..., description="Optimistic-lock token (current row version)")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("contract_type")
    @classmethod
    def _normalize_contract_type(cls, value: str | None) -> str | None:
        from app.services.contract_type import normalize_contract_type

        return normalize_contract_type(value)

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
    order_date: date | None = None
    receipt_date: date | None = None
    inspection_date: date | None = None
    payment_date: date | None = None
    transaction_kind: str | None = None
    is_public_work: bool = False
    handles_personal_data: bool = False
    our_capital_jpy: int | None = None
    counterparty_capital_jpy: int | None = None
    our_employees: int | None = None
    counterparty_employees: int | None = None
    case_category: str | None = None
    ethical_wall: bool = False


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
