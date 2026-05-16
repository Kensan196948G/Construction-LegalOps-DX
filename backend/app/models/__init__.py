"""SQLAlchemy ORM models for Construction-LegalOps-DX.

Importing this package registers every model on ``app.db.base.Base.metadata``,
which is required for Alembic autogenerate to discover the schema.
"""

from __future__ import annotations

from .attachment import Attachment
from .audit_log import AuditLog
from .clause import Clause, ClauseLibrary
from .comment import Comment
from .contract import Contract
from .department import Department
from .enums import (
    AttachmentStorage,
    AuditAction,
    ClauseRecommendation,
    CommentVisibility,
    Confidentiality,
    ContractStatus,
    ContractType,
    NotificationChannel,
    NotificationStatus,
    ReviewStatus,
    ReviewType,
    RiskImpact,
    RiskItemStatus,
    RiskLevel,
    RiskProbability,
    UserRole,
    WorkflowStepStatus,
    WorkflowStepType,
)
from .legal_review import LegalReview
from .notification import Notification
from .risk_item import RiskItem
from .user import User
from .workflow import Workflow, WorkflowStep, WorkflowTemplate

__all__ = [  # noqa: RUF022
    # Models
    "Attachment",
    "AuditLog",
    "Clause",
    "ClauseLibrary",
    "Comment",
    "Contract",
    "Department",
    "LegalReview",
    "Notification",
    "RiskItem",
    "User",
    "Workflow",
    "WorkflowStep",
    "WorkflowTemplate",
    # Enums
    "AttachmentStorage",
    "AuditAction",
    "ClauseRecommendation",
    "CommentVisibility",
    "Confidentiality",
    "ContractStatus",
    "ContractType",
    "NotificationChannel",
    "NotificationStatus",
    "ReviewStatus",
    "ReviewType",
    "RiskImpact",
    "RiskItemStatus",
    "RiskLevel",
    "RiskProbability",
    "UserRole",
    "WorkflowStepStatus",
    "WorkflowStepType",
]
