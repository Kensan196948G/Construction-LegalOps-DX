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

    2026-08-12: UI 表示と API 保存値を統一するため、正準値（表示名）を追加した。
    旧値（UKEOI="請負" 等）は後方互換エイリアスとして維持し、
    ``app.services.contract_type.normalize`` で正準値へ正規化する。
    """

    # --- 正準値（UI 表示と一致） ---
    KOUJI_UKEOI = "工事請負契約"
    GYOMU_ITAKU = "業務委託契約"
    SHIZAI_KOUNYUU = "資材購入契約"
    SHITAKE = "下請契約"
    SEKKEI_KANRI = "設計監理契約"
    CHINSHAKU = "賃貸借契約"
    NDA = "秘密保持契約"
    BAIBAI = "売買契約"
    OBOEGAKI = "覚書"
    JV = "JV"
    OTHER = "その他"

    # --- 後方互換エイリアス（新規作成は不可・正規化で正準値へ） ---
    UKEOI = "請負"
    ITAKU = "委託"
    CHINSHAKU_LEGACY = "賃借"
    NDA_LEGACY = "秘密保持"


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


class SigningStatus(StrEnum):
    """電子署名エンベロープの状態（ロードマップ #2 電子署名ステータス管理）.

    遷移規則は ``app.services.signing_service`` の状態機械が唯一の正とする。
    draft → sent → viewed → signed → completed、および draft/sent/viewed → cancelled。
    """

    DRAFT = "draft"
    SENT = "sent"
    VIEWED = "viewed"
    SIGNED = "signed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class SigningMethod(StrEnum):
    """契約締結方法.

    ``electronic`` は建設業法 19 条の電子書面交付に該当し、相手方の承諾
    （電磁的方法による交付の承諾）の証跡を要する（ロードマップ #3）。
    """

    ELECTRONIC = "electronic"
    PAPER = "paper"


class SigningProviderId(StrEnum):
    """外部電子契約サービス（ロードマップ #1 電子契約連携）.

    実資格情報が未設定の場合は ``demo`` ／ ``manual`` のみ利用可能
    （fail-closed）。``app.services.signing_provider`` が唯一の正。
    """

    CLOUDSIGN = "cloudsign"
    DOCUSIGN = "docusign"
    DEMO = "demo"
    MANUAL = "manual"


class ClauseNegotiationStatus(StrEnum):
    """条項の交渉ステータス（ロードマップ #7 条項ステータス）.

    遷移規則は ``app.services.negotiation_service`` が唯一の正。
    原則 accepted / rejected は negotiating 経由を推奨するが、実務上の
    再交渉（accepted→negotiating 等）も許容する。
    """

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    NEGOTIATING = "negotiating"


class ClauseNegotiationAction(StrEnum):
    """条項単位の交渉イベント種別（ロードマップ #5/#6）.

    - ``redline``: 修正提案（proposed_text を伴う）
    - ``demand`` / ``concession``: 要求・譲歩の記録
    - ``comment``: コメント
    - ``status_change`` / ``owner_change``: 状態・担当変更（サービス内部利用）
    """

    DEMAND = "demand"
    CONCESSION = "concession"
    COMMENT = "comment"
    REDLINE = "redline"
    STATUS_CHANGE = "status_change"
    OWNER_CHANGE = "owner_change"


class ClauseOwner(StrEnum):
    """条項オーナー（ロードマップ #8 条項オーナー管理）."""

    LEGAL = "法務"
    ENGINEERING = "工事"
    SALES = "営業"
    PURCHASING = "購買"
    OTHER = "その他"


class ObligationType(StrEnum):
    """契約義務の種別（ロードマップ #9〜#13 / Issue #99）.

    - ``report``: 報告義務（工事進捗・完了等）
    - ``notice``: 通知義務（変更・事故等）
    - ``submit``: 提出義務（書類・実績等）
    - ``insurance``: 保険（証券提出・更新等）
    - ``renewal``: 更新（契約更新手続）
    - ``condition``: 条件成就（発効条件・支払条件等）
    - ``closing``: 契約終了チェック（精算・返却・秘密保持残存等）
    - ``other``: その他
    """

    REPORT = "report"
    NOTICE = "notice"
    SUBMIT = "submit"
    INSURANCE = "insurance"
    RENEWAL = "renewal"
    CONDITION = "condition"
    CLOSING = "closing"
    OTHER = "other"


class ObligationStatus(StrEnum):
    """契約義務の状態."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    WAIVED = "waived"


class MatterType(StrEnum):
    """法務案件（Matter）の類型（ロードマップ #71〜#84 / Issue #101）."""

    CONTRACT = "contract"
    DISPUTE = "dispute"
    COMPLIANCE = "compliance"
    LABOR = "labor"
    REGULATORY = "regulatory"
    OTHER = "other"


class MatterStatus(StrEnum):
    """Matter の状態."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"
    ON_HOLD = "on_hold"
    CLOSED = "closed"


class MatterPriority(StrEnum):
    """Matter の優先度（リスクランクを兼ねる・#75/#76）."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MatterEventType(StrEnum):
    """Matter タイムラインのイベント種別（#78）."""

    CREATED = "created"
    ASSIGNED = "assigned"
    STATUS_CHANGED = "status_changed"
    CONTRACT_LINKED = "contract_linked"
    CONTRACT_UNLINKED = "contract_unlinked"
    LEGAL_HOLD_LINKED = "legal_hold_linked"
    LEGAL_HOLD_UNLINKED = "legal_hold_unlinked"
    NOTE = "note"


class EngagementStatus(StrEnum):
    """顧問弁護士依頼（エンゲージメント）の状態（ロードマップ #85〜#96 / Issue #102）."""

    OPEN = "open"  # 依頼・回答待ち
    ANSWERED = "answered"  # 回答受領
    CONFIRMED = "confirmed"  # 確認完了（確定）
    CANCELLED = "cancelled"


class LaborWorkType(StrEnum):
    """労務費基準の工種（ロードマップ #17 工種別基準値管理・#16〜#20 / Issue #111）.

    国交省『労務費に関する基準』の職種区分に倣った代表値を保持する。
    詳細区分の追加はマスタデータ側（labor_wage_standards.work_type は
    CHECK 制約なしの拡張可能な varchar）で行い、本 enum は UI の代表値。
    """

    DOBOKU = "土木"
    TOBI_DOBOU = "とび・土工"
    HOSOU = "舗装"
    KAITAI = "解体"
    TEKKIN = "鉄筋"
    KONKURIITO = "コンクリート"
    OTHER = "その他"
