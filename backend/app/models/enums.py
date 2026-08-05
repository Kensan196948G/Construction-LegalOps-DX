"""Enum definitions shared across models and schemas.

Construction-LegalOps-DX backend uses Python ``str`` Enums so that values
serialize cleanly to JSON / PostgreSQL ``VARCHAR`` columns and remain stable
across Alembic migrations. The values mirror the ``CHECK`` constraints defined
in ``docs/database_design.md``.
"""

from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    """Application role granted to a user.

    The role is stored as a VARCHAR(32) column in ``users.role`` and is the
    primary driver of authorization across the API. The roles match the
    matrix in ``docs/api_design.md`` section 17.
    """

    VIEWER = "viewer"
    DRAFTER = "drafter"
    REVIEWER = "reviewer"
    APPROVER = "approver"
    ADMIN = "admin"
    AUDITOR = "auditor"
    GUEST = "guest"


class ContractType(StrEnum):
    """Common Japanese construction-industry contract types.

    The DB column is open VARCHAR(64) since organisations may add bespoke
    types, but the values below cover the canonical taxonomy.
    """

    UKEOI = "請負"
    ITAKU = "委託"
    JV = "JV"
    CHINSHAKU = "賃借"
    NDA = "秘密保持"
    BAIBAI = "売買"
    OTHER = "その他"


class ContractStatus(StrEnum):
    """Lifecycle state of a ``contracts`` row."""

    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    SIGNED = "signed"
    ARCHIVED = "archived"
    REJECTED = "rejected"


class Confidentiality(StrEnum):
    """Confidentiality classification for contracts and attachments."""

    PUBLIC = "public"
    NORMAL = "normal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class RiskLevel(StrEnum):
    """Discrete risk levels for clauses and overall reviews."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReviewType(StrEnum):
    AI = "ai"
    HUMAN = "human"
    HYBRID = "hybrid"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
    ACCEPTED = "accepted"


class ClauseRecommendation(StrEnum):
    REQUIRED = "required"
    RECOMMENDED = "recommended"
    OPTIONAL = "optional"
    PROHIBITED = "prohibited"


class RiskProbability(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskImpact(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskItemStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    ACCEPTED = "accepted"
    TRANSFERRED = "transferred"
    MITIGATED = "mitigated"
    AVOIDED = "avoided"
    CLOSED = "closed"


class WorkflowStepType(StrEnum):
    DRAFT = "draft"
    LEGAL_REVIEW = "legal_review"
    MANAGER_APPROVAL = "manager_approval"
    EXEC_APPROVAL = "exec_approval"
    SIGN = "sign"
    CUSTOM = "custom"


class WorkflowStepStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    APPROVED = "approved"
    REJECTED = "rejected"
    SKIPPED = "skipped"
    SENT_BACK = "sent_back"


class CommentVisibility(StrEnum):
    INTERNAL = "internal"
    REVIEWER_ONLY = "reviewer_only"
    PUBLIC = "public"


class AttachmentStorage(StrEnum):
    SHAREPOINT = "sharepoint"
    DIRECTCLOUD = "directcloud"
    LOCAL = "local"


class NotificationChannel(StrEnum):
    MAIL = "mail"
    TEAMS = "teams"
    IN_APP = "in_app"
    DESKNETS = "desknets"


class NotificationStatus(StrEnum):
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"
    READ = "read"


class AuditAction(StrEnum):
    """Audit log action codes.

    Stored as VARCHAR(64) in ``audit_logs.action``. The list is intentionally
    open; new values may be added without a migration.
    """

    CONTRACT_CREATE = "contract.create"
    CONTRACT_UPDATE = "contract.update"
    CONTRACT_DELETE = "contract.delete"
    CONTRACT_SUBMIT = "contract.submit"
    CONTRACT_APPROVE = "contract.approve"
    CONTRACT_REJECT = "contract.reject"
    REVIEW_START = "review.start"
    REVIEW_COMPLETE = "review.complete"
    REVIEW_ACCEPT = "review.accept"
    REVIEW_REJECT = "review.reject"
    WORKFLOW_STEP_APPROVE = "workflow_step.approve"
    WORKFLOW_STEP_REJECT = "workflow_step.reject"
    WORKFLOW_STEP_SEND_BACK = "workflow_step.send_back"
    WORKFLOW_STEP_DELEGATE = "workflow_step.delegate"
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    USER_UPDATE = "user.update"
    ATTACHMENT_UPLOAD = "attachment.upload"
    ATTACHMENT_DELETE = "attachment.delete"
    # --- P0-6: ACL / Legal Hold / Retention / 外部転送 ---
    ACCESS_GRANT = "access.grant"
    ACCESS_REVOKE = "access.revoke"
    LEGAL_HOLD_CREATE = "legal_hold.create"
    LEGAL_HOLD_RELEASE = "legal_hold.release"
    RETENTION_DELETE = "retention.delete"
    RETENTION_BLOCKED = "retention.blocked"
    AUDIT_ANCHOR_CREATE = "audit.anchor.create"
    SENTINEL_FORWARD = "sentinel.forward"
    SENTINEL_BLOCKED = "sentinel.blocked"
    DLP_BLOCK = "dlp.block"
    # --- 高優先業務機能 ---
    CHANGE_ORDER_CREATE = "change_order.create"
    CHANGE_ORDER_UPDATE = "change_order.update"
    CHANGE_ORDER_DELETE = "change_order.delete"
    DISPUTE_CREATE = "dispute.create"
    DISPUTE_UPDATE = "dispute.update"
    DISPUTE_DELETE = "dispute.delete"
    DISPUTE_TIMELINE_ADD = "dispute.timeline.add"
    DISPUTE_EVIDENCE_ADD = "dispute.evidence.add"
    PARTNER_CREATE = "partner.create"
    PARTNER_UPDATE = "partner.update"
    PARTNER_DELETE = "partner.delete"
    DOCUMENT_CREATE = "document.create"
    DOCUMENT_UPDATE = "document.update"
    DOCUMENT_DELETE = "document.delete"
    PAYMENT_COMPLIANCE_RUN = "payment_compliance.run"
