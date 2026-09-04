"""SQLAlchemy ORM models for Construction-LegalOps-DX.

Importing this package registers every model on ``app.db.base.Base.metadata``,
which is required for Alembic autogenerate to discover the schema.
"""

from __future__ import annotations

from .access_control import AccessControlEntry, LegalHold
from .app_settings import AiProviderSetting
from .attachment import Attachment
from .audit_anchor import AuditAnchor
from .audit_export import AuditExportJob
from .audit_log import AuditLog
from .case_access import ContractAccessGrant
from .change_order import ChangeOrder, ChangeOrderEvidence
from .clause import Clause, ClauseLibrary
from .comment import Comment
from .contract import Contract
from .contract_document import ContractDocument
from .contract_template import ContractTemplate
from .department import Department
from .dispute import Dispute, DisputeEvidence, DisputeTimelineEvent
from .document_consistency import DocumentConsistencyResult
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
from .ip_asset import IpAsset
from .ip_document import IpDocument
from .ip_watch import IpWatchEvent, IpWatchTarget
from .knowledge_article import KnowledgeArticle
from .legal_hold import LegalHoldCase
from .legal_review import LegalReview
from .notification import Notification
from .partner import Partner
from .payment_record import PaymentRecord
from .retention import ExternalForwardEvent, RetentionRule
from .risk_item import RiskItem
from .security_settings import SecuritySetting
from .signing import ESignatureEnvelope, ESignatureEvent
from .user import User
from .workflow import Workflow, WorkflowStep, WorkflowTemplate

__all__ = [
    "AccessControlEntry",
    "AiProviderSetting",
    "Attachment",
    "AttachmentStorage",
    "AuditAction",
    "AuditAnchor",
    "AuditExportJob",
    "AuditLog",
    "ChangeOrder",
    "ChangeOrderEvidence",
    "Clause",
    "ClauseLibrary",
    "ClauseRecommendation",
    "Comment",
    "CommentVisibility",
    "Confidentiality",
    "Contract",
    "ContractAccessGrant",
    "ContractDocument",
    "ContractStatus",
    "ContractTemplate",
    "ContractType",
    "Department",
    "Dispute",
    "DisputeEvidence",
    "DisputeTimelineEvent",
    "DocumentConsistencyResult",
    "ESignatureEnvelope",
    "ESignatureEvent",
    "ExternalForwardEvent",
    "IpAsset",
    "IpDocument",
    "IpWatchEvent",
    "IpWatchTarget",
    "KnowledgeArticle",
    "LegalHold",
    "LegalHoldCase",
    "LegalReview",
    "Notification",
    "NotificationChannel",
    "NotificationStatus",
    "Partner",
    "PaymentRecord",
    "RetentionRule",
    "ReviewStatus",
    "ReviewType",
    "RiskImpact",
    "RiskItem",
    "RiskItemStatus",
    "RiskLevel",
    "RiskProbability",
    "SecuritySetting",
    "User",
    "UserRole",
    "Workflow",
    "WorkflowStep",
    "WorkflowStepStatus",
    "WorkflowStepType",
    "WorkflowTemplate",
]
