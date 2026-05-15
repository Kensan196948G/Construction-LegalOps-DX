"""Pydantic v2 schemas for the public REST API surface."""

from __future__ import annotations

from .audit_log import AuditActor, AuditLogRead, AuditLogVerifyResult
from .auth import (
    LoginRequest,
    MeResponse,
    RefreshRequest,
    SSOCallback,
    TokenResponse,
)
from .common import (
    Envelope,
    FilterBase,
    IdResponse,
    Meta,
    ORMModel,
    PageRequest,
    Pagination,
    ProblemDetailError,
    ProblemDetails,
    Sort,
    TimestampsMixin,
)
from .contract import (
    ContractBase,
    ContractCreate,
    ContractDetail,
    ContractList,
    ContractRead,
    ContractSubmitResponse,
    ContractUpdate,
    UserBrief,
)
from .legal_review import (
    AIReviewResult,
    ReviewActionRequest,
    ReviewActionResponse,
    ReviewCreate,
    ReviewDetail,
    ReviewIssue,
    ReviewRead,
    SuggestedAction,
)
from .upload import (
    AttachmentRead,
    UploadCompleteRequest,
    UploadInitRequest,
    UploadInitResponse,
)
from .user import DepartmentBrief, UserCreate, UserMe, UserRead, UserUpdate
from .workflow import (
    WorkflowAction,
    WorkflowActionResult,
    WorkflowCreate,
    WorkflowDefinition,
    WorkflowRead,
    WorkflowStepDefinition,
    WorkflowStepRead,
)

__all__ = [
    # common
    "Envelope",
    "FilterBase",
    "IdResponse",
    "Meta",
    "ORMModel",
    "PageRequest",
    "Pagination",
    "ProblemDetailError",
    "ProblemDetails",
    "Sort",
    "TimestampsMixin",
    # auth
    "LoginRequest",
    "MeResponse",
    "RefreshRequest",
    "SSOCallback",
    "TokenResponse",
    # user
    "DepartmentBrief",
    "UserCreate",
    "UserMe",
    "UserRead",
    "UserUpdate",
    # contract
    "ContractBase",
    "ContractCreate",
    "ContractDetail",
    "ContractList",
    "ContractRead",
    "ContractSubmitResponse",
    "ContractUpdate",
    "UserBrief",
    # legal review
    "AIReviewResult",
    "ReviewActionRequest",
    "ReviewActionResponse",
    "ReviewCreate",
    "ReviewDetail",
    "ReviewIssue",
    "ReviewRead",
    "SuggestedAction",
    # workflow
    "WorkflowAction",
    "WorkflowActionResult",
    "WorkflowCreate",
    "WorkflowDefinition",
    "WorkflowRead",
    "WorkflowStepDefinition",
    "WorkflowStepRead",
    # audit log
    "AuditActor",
    "AuditLogRead",
    "AuditLogVerifyResult",
    # upload
    "AttachmentRead",
    "UploadCompleteRequest",
    "UploadInitRequest",
    "UploadInitResponse",
]
