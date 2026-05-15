"""factory-boy factories for Construction-LegalOps-DX domain models.

The factories generate Japanese-locale dummy data via ``faker``. They are
written defensively: if a model class is not importable yet (early Loops),
a small ``_PlaceholderModel`` is substituted so that the test module can
still be collected. Tests using a placeholder factory must skip themselves
with the ``factories.skip_if_placeholder(...)`` helper.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import factory
from faker import Faker

fake = Faker("ja_JP")
Faker.seed(20260101)


# ---------------------------------------------------------------------------
# Model imports (defensive)
# ---------------------------------------------------------------------------


class _PlaceholderModel:
    """Used when a real ORM model is not importable yet."""

    def __init__(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


def _try_import(modpath: str, name: str) -> Any:
    try:
        mod = __import__(modpath, fromlist=[name])
    except Exception:
        return _PlaceholderModel
    return getattr(mod, name, _PlaceholderModel)


User = _try_import("app.models.user", "User")
Department = _try_import("app.models.department", "Department")
Contract = _try_import("app.models.contract", "Contract")
LegalReview = _try_import("app.models.review", "LegalReview")
if LegalReview is _PlaceholderModel:
    LegalReview = _try_import("app.models.legal_review", "LegalReview")
Workflow = _try_import("app.models.workflow", "Workflow")
AuditLog = _try_import("app.models.audit_log", "AuditLog")


def skip_if_placeholder(*models: Any) -> bool:
    """Return True if any of the given model classes is a placeholder."""
    return any(m is _PlaceholderModel for m in models)


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


class _BaseFactory(factory.Factory):
    class Meta:
        abstract = True


class DepartmentFactory(_BaseFactory):
    class Meta:
        model = Department

    code = factory.Sequence(lambda n: f"DEPT{n:04d}")
    name = factory.LazyFunction(lambda: fake.company_prefix() + "本部")
    parent_id = None
    sort_order = factory.Sequence(lambda n: n)
    is_active = True


class UserFactory(_BaseFactory):
    class Meta:
        model = User

    entra_oid = factory.LazyFunction(uuid.uuid4)
    email = factory.LazyAttribute(lambda o: fake.unique.email())
    display_name = factory.LazyFunction(lambda: fake.name())
    role = "drafter"
    is_active = True
    department_id = None
    attributes = factory.LazyFunction(dict)


class ContractFactory(_BaseFactory):
    class Meta:
        model = Contract

    title = factory.LazyFunction(lambda: fake.bs() + "業務委託契約書")
    contract_type = "請負"
    status = "draft"
    counterparty_name = factory.LazyFunction(lambda: fake.company())
    contract_amount = factory.LazyFunction(
        lambda: Decimal(fake.random_int(min=1_000_000, max=500_000_000))
    )
    start_date = factory.LazyFunction(lambda: date.today())
    end_date = factory.LazyFunction(lambda: date.today() + timedelta(days=365))
    confidentiality = "normal"
    department_id = None
    drafted_by = None
    summary = factory.LazyFunction(lambda: fake.paragraph(nb_sentences=3))


class LegalReviewFactory(_BaseFactory):
    class Meta:
        model = LegalReview

    contract_id = None
    review_type = "ai"
    status = "pending"
    risk_score = 0
    risk_level = "low"
    summary = factory.LazyFunction(lambda: fake.paragraph(nb_sentences=2))
    started_at = factory.LazyFunction(lambda: datetime.now(tz=timezone.utc))
    completed_at = None


class WorkflowFactory(_BaseFactory):
    class Meta:
        model = Workflow

    contract_id = None
    current_step = 0
    status = "in_progress"
    definition = factory.LazyFunction(
        lambda: {
            "steps": [
                {"type": "legal_review", "role": "reviewer"},
                {"type": "manager_approval", "role": "approver"},
            ]
        }
    )


class AuditLogFactory(_BaseFactory):
    class Meta:
        model = AuditLog

    actor_id = None
    action = "contract.create"
    target_type = "contracts"
    target_id = factory.Sequence(lambda n: n + 1)
    occurred_at = factory.LazyFunction(lambda: datetime.now(tz=timezone.utc))
    payload = factory.LazyFunction(
        lambda: {"sample": True, "comment": fake.sentence()}
    )
    prev_hash = "0" * 64
    hash_chain = factory.LazyAttribute(
        lambda o: hashlib.sha256(
            (o.prev_hash + json.dumps(o.payload, sort_keys=True, default=str)).encode()
        ).hexdigest()
    )


__all__ = [
    "AuditLogFactory",
    "ContractFactory",
    "DepartmentFactory",
    "LegalReviewFactory",
    "UserFactory",
    "WorkflowFactory",
    "skip_if_placeholder",
    "fake",
]
