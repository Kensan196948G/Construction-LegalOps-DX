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
    AgencyType,
    AttachmentStorage,
    AuditAction,
    ClauseRecommendation,
    CommentVisibility,
    Confidentiality,
    ConsultationDirection,
    ConsultationStatus,
    ContractStatus,
    ContractType,
    DumpingSeverity,
    JvAgreementStatus,
    JvDisputeStatus,
    JvMemberRole,
    JvSettlementStatus,
    JvStatus,
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
from .joint_venture import JointVenture, JvAgreement, JvDispute, JvMember, JvSettlement
from .knowledge_article import KnowledgeArticle
from .labor_commitment import LaborCommitment
from .labor_wage import LaborWageStandard
from .legal_hold import LegalHoldCase
from .legal_review import LegalReview
from .matter import LegalMatter, MatterEvent
from .negotiation import ClauseNegotiationEvent
from .notification import Notification
from .obligation import ContractObligation
from .outside_counsel import CounselLawyer, LawFirm, LegalEngagement
from .partner import Partner
from .partner_review import PartnerReview
from .payment_record import PaymentRecord
from .price_consultation import PriceConsultationLog
from .public_works import ContractingAgency, OwnerNotification, PublicWorksConsultation
from .retention import ExternalForwardEvent, RetentionRule
from .risk_item import RiskItem
from .security_settings import SecuritySetting
from .signing import ESignatureEnvelope, ESignatureEvent
from .standard_duration import StandardWorkDuration
from .user import User
from .workflow import Workflow, WorkflowStep, WorkflowTemplate

__all__ = [
    "AccessControlEntry",
    "AgencyType",
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
    "ClauseNegotiationEvent",
    "ClauseRecommendation",
    "Comment",
    "CommentVisibility",
    "Confidentiality",
    "ConsultationDirection",
    "ConsultationStatus",
    "Contract",
    "ContractAccessGrant",
    "ContractDocument",
    "ContractObligation",
    "ContractStatus",
    "ContractTemplate",
    "ContractType",
    "ContractingAgency",
    "CounselLawyer",
    "Department",
    "Dispute",
    "DisputeEvidence",
    "DisputeTimelineEvent",
    "DocumentConsistencyResult",
    "DumpingSeverity",
    "ESignatureEnvelope",
    "ESignatureEvent",
    "ExternalForwardEvent",
    "IpAsset",
    "IpDocument",
    "IpWatchEvent",
    "IpWatchTarget",
    "JointVenture",
    "JvAgreement",
    "JvAgreementStatus",
    "JvDispute",
    "JvDisputeStatus",
    "JvMember",
    "JvMemberRole",
    "JvSettlement",
    "JvSettlementStatus",
    "JvStatus",
    "KnowledgeArticle",
    "LaborCommitment",
    "LaborCommitmentStatus",
    "LaborCommitmentType",
    "LaborWageStandard",
    "LawFirm",
    "LegalEngagement",
    "LegalHold",
    "LegalHoldCase",
    "LegalMatter",
    "LegalReview",
    "MatterEvent",
    "Notification",
    "NotificationChannel",
    "NotificationStatus",
    "OwnerNotification",
    "Partner",
    "PartnerReview",
    "PartnerReviewStatus",
    "PartnerReviewType",
    "PaymentRecord",
    "PriceConsultationLog",
    "PublicWorksConsultation",
    "RetentionRule",
    "ReviewStatus",
    "ReviewType",
    "RiskImpact",
    "RiskItem",
    "RiskItemStatus",
    "RiskLevel",
    "RiskProbability",
    "SecuritySetting",
    "StandardWorkDuration",
    "User",
    "UserRole",
    "Workflow",
    "WorkflowStep",
    "WorkflowStepStatus",
    "WorkflowStepType",
    "WorkflowTemplate",
]
