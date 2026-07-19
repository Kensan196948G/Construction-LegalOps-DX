"""SQLAlchemy ORM models for Construction-LegalOps-DX.

Importing this package registers every model on ``app.db.base.Base.metadata``,
which is required for Alembic autogenerate to discover the schema.
"""

from __future__ import annotations

from .app_settings import AiProviderSetting
from .attachment import Attachment
from .audit_log import AuditLog
from .clause import Clause, ClauseLibrary
from .comment import Comment
from .contract import Contract
from .contract_template import ContractTemplate
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
from .knowledge_article import KnowledgeArticle
from .legal_review import LegalReview
from .notification import Notification
from .risk_item import RiskItem
from .user import User
from .workflow import Workflow, WorkflowStep, WorkflowTemplate

__all__ = [
    # Models
    "AiProviderSetting",
    "Attachment",
    # Enums
    "AttachmentStorage",
    "AuditAction",
    "AuditLog",
    "Clause",
    "ClauseLibrary",
    "ClauseRecommendation",
    "Comment",
    "CommentVisibility",
    "Confidentiality",
    "Contract",
    "ContractStatus",
    "ContractTemplate",
    "ContractType",
    "Department",
    "KnowledgeArticle",
    "LegalReview",
    "Notification",
    "NotificationChannel",
    "NotificationStatus",
    "ReviewStatus",
    "ReviewType",
    "RiskImpact",
    "RiskItem",
    "RiskItemStatus",
    "RiskLevel",
    "RiskProbability",
    "User",
    "UserRole",
    "Workflow",
    "WorkflowStep",
    "WorkflowStepStatus",
    "WorkflowStepType",
    "WorkflowTemplate",
]
