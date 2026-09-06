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


class ConsultationDirection(StrEnum):
    """労務費価格協議の申出方向（#24 価格協議履歴）."""

    FROM_SUBCONTRACTOR = "from_subcontractor"  # 下請→元請（価格引上げ協議申出）
    TO_SUBCONTRACTOR = "to_subcontractor"  # 元請→下請（価格確認・引下げ要求）


class ConsultationStatus(StrEnum):
    """労務費価格協議の状態（#24）."""

    OPEN = "open"  # 協議申出・回答待ち
    RESPONDED = "responded"  # 回答済み（証跡確定）
    CANCELLED = "cancelled"  # 取下げ


class DumpingSeverity(StrEnum):
    """ダンピング警告の深刻度（#21・乖離率から決定論的に導出）.

    - none: 基準以上（乖離なし）
    - watch: 基準未満だが軽微（不足率 10% 未満）
    - warning: 基準を 10% 以上下回る（要確認）
    - critical: 基準を 20% 以上下回る（著しい低見積り）
    """

    NONE = "none"
    WATCH = "watch"
    WARNING = "warning"
    CRITICAL = "critical"


class AgencyType(StrEnum):
    """発注機関種別（公共工事 #41 発注機関マスタ）."""

    NATIONAL = "national"  # 国の機関
    PREFECTURAL = "prefectural"  # 都道府県
    MUNICIPAL = "municipal"  # 市町村
    PUBLIC_CORP = "public_corp"  # 公社・公団等
    OTHER = "other"


class OwnerNotificationType(StrEnum):
    """発注者通知種別（公共工事 #54 発注者通知期限管理）."""

    DESIGN_CHANGE = "design_change"  # 設計変更の通知
    DELAY = "delay"  # 工期遅延の通知
    SUSPENSION = "suspension"  # 工事中止・再開の通知
    CLAIM = "claim"  # 請求・クレーム通知
    COMPLETION = "completion"  # 完了・引渡し通知
    OTHER = "other"


class OwnerNotificationStatus(StrEnum):
    """発注者通知の状態（#54）."""

    OPEN = "open"  # 通知期限未達成（送付待ち）
    NOTIFIED = "notified"  # 通知済み（証跡確定）
    CANCELLED = "cancelled"


class PublicWorksConsultationType(StrEnum):
    """公共工事における発注者との協議種別（#55 工期延伸・#56 スライド請求・#57 設計変更）."""

    EXTENSION_OF_TIME = "extension_of_time"  # 工期延伸協議（#55）
    DESIGN_CHANGE = "design_change"  # 設計変更協議（#57）
    PRICE_SLIDE = "price_slide"  # スライド請求（#56）
    SUSPENSION = "suspension"  # 一時中止・再開協議（#58 関連）
    OTHER = "other"


class PublicWorksConsultationStatus(StrEnum):
    """発注者との協議の状態."""

    OPEN = "open"  # 協議中・回答待ち
    RESPONDED = "responded"  # 回答受領（結果記録済み）
    CANCELLED = "cancelled"


class JvStatus(StrEnum):
    """JV（共同企業体）の状態（#61 JV 台帳）."""

    PROSPECTING = "prospecting"  # 結成検討中
    ACTIVE = "active"  # 活動中
    COMPLETED = "completed"  # 完了・清算済み
    DISSOLVED = "dissolved"  # 解散


class JvMemberRole(StrEnum):
    """JV 構成員の役割（#63 代表会社・構成員管理）."""

    REPRESENTATIVE = "representative"  # 代表会社
    MEMBER = "member"  # 構成員（幹事以外）


class JvAgreementStatus(StrEnum):
    """JV 協定書の状態（#62 JV 協定書管理）."""

    DRAFT = "draft"  # 起案中
    SIGNED = "signed"  # 締結済み
    TERMINATED = "terminated"  # 終了


class JvDisputeStatus(StrEnum):
    """JV 内紛争・請求の状態（#69）."""

    OPEN = "open"  # 協議中
    RESPONDED = "responded"  # 回答済み
    CANCELLED = "cancelled"


class JvSettlementStatus(StrEnum):
    """JV 終了・清算の状態（#70）."""

    PENDING = "pending"  # 未清算
    SETTLED = "settled"  # 清算済み


class PartnerReviewType(StrEnum):
    """協力会社再審査の種別（#147-#149・#151）."""

    PERIODIC = "periodic"  # 定期再審査（#151）
    INCIDENT = "incident"  # 安全・事故記録（#147/#148）
    VIOLATION = "violation"  # 契約違反記録（#149）


class PartnerReviewStatus(StrEnum):
    """協力会社再審査の状態."""

    OPEN = "open"  # 審査中
    COMPLETED = "completed"  # 審査完了


class LaborCommitmentType(StrEnum):
    """労務費・賃金関連の表明（コミットメント）種別（#28）."""

    WAGE_PAYMENT = "wage_payment"  # 賃金支払確約
    PROPER_ALLOCATION = "proper_allocation"  # 労務費の適正配分
    NO_LUMP_SUBCONTRACT = "no_lump_subcontract"  # 一括下請負の禁止遵守
    IMPROVEMENT = "improvement"  # 労働環境改善
    OTHER = "other"


class LaborCommitmentStatus(StrEnum):
    """表明の状態（#28）."""

    ACTIVE = "active"  # 表明中
    FULFILLED = "fulfilled"  # 履行確認済み
    VIOLATED = "violated"  # 違反確認


class DisputeDelayCauseCategory(StrEnum):
    """遅延事象の原因分類（ロードマップ #101）."""

    OWNER_CAUSED = "owner_caused"  # 発注者起因
    CONTRACTOR_CAUSED = "contractor_caused"  # 請負者起因
    WEATHER = "weather"  # 天候
    THIRD_PARTY = "third_party"  # 第三者起因
    FORCE_MAJEURE = "force_majeure"  # 不可抗力
    DESIGN_CHANGE = "design_change"  # 設計変更
    OTHER = "other"


class DisputeEotStatus(StrEnum):
    """EOT（工期延長）判定状態（ロードマップ #104）."""

    PENDING = "pending"  # 未判定
    APPROVED = "approved"  # 全部認容
    PARTIAL = "partial"  # 一部認容
    REJECTED = "rejected"  # 却下


class DisputeArgumentParty(StrEnum):
    """主張・反論マトリクスの当事者区分（ロードマップ #109）."""

    OURS = "ours"
    COUNTERPARTY = "counterparty"


class DisputeArgumentStance(StrEnum):
    """主張・反論マトリクスの立場（ロードマップ #109）."""

    CLAIM = "claim"  # 主張
    REBUTTAL = "rebuttal"  # 反論
    COUNTER_REBUTTAL = "counter_rebuttal"  # 再反論


class DisputeSettlementStatus(StrEnum):
    """和解案の状態（ロードマップ #110）."""

    DRAFT = "draft"  # 検討中
    PROPOSED = "proposed"  # 提案済み
    ACCEPTED = "accepted"  # 合意
    REJECTED = "rejected"  # 拒否
    WITHDRAWN = "withdrawn"  # 撤回


class DisputeProceedingStageType(StrEnum):
    """訴訟・ADR ステージ種別（ロードマップ #111）."""

    NEGOTIATION = "negotiation"  # 交渉
    MEDIATION = "mediation"  # 調停
    ARBITRATION_FILED = "arbitration_filed"  # 仲裁申立
    ARBITRATION_HEARING = "arbitration_hearing"  # 仲裁審理
    ARBITRATION_AWARD = "arbitration_award"  # 仲裁判断
    LAWSUIT_FILED = "lawsuit_filed"  # 訴訟提起
    FIRST_INSTANCE = "first_instance"  # 第一審
    APPEAL = "appeal"  # 控訴審
    FINAL_JUDGMENT = "final_judgment"  # 確定判決
    SETTLED = "settled"  # 和解成立


class DisputeProceedingStageStatus(StrEnum):
    """訴訟・ADR ステージの進行状態（ロードマップ #111）."""

    ACTIVE = "active"  # 進行中
    COMPLETED = "completed"  # 完了


class AntitrustCheckType(StrEnum):
    """独禁法・入札談合コンプライアンス — ルールベースチェックの種別（Issue #122）.

    決定論的なルールエンジン（``app.services.antitrust_checker``）が唯一の正で
    あり、AI には最終法的判断をさせない。
    """

    GENERAL = "general"  # #113 独禁法チェック（契約書・取引文面の一般スクリーニング）
    BID_RIGGING = "bid_rigging"  # #114 入札談合リスクチェック
    PRICE_EXCHANGE = "price_exchange"  # #117 価格情報交換禁止チェック
    JV_FORMATION = "jv_formation"  # #118 JV 形成時競争法チェック
    JOINT_RESEARCH = "joint_research"  # #119 競合との共同研究チェック


class AntitrustCheckSeverity(StrEnum):
    """チェック結果の重大度（``ComplianceSeverity`` と同義の 3 段階）."""

    INFO = "info"
    WARN = "warn"
    BLOCK = "block"


class AntitrustApplicationType(StrEnum):
    """事前申請 → 承認 → 記録ワークフローの種別（Issue #122）."""

    COMPETITOR_CONTACT = "competitor_contact"  # #115 競合他社接触記録
    MEETING_SOCIAL = "meeting_social"  # #116 会合・懇親会事前申請
    ENTERTAINMENT_GIFT = "entertainment_gift"  # #121 贈収賄・接待管理
    PUBLIC_OFFICIAL_CONTACT = "public_official_contact"  # #122 公務員接触記録
    DONATION_SPONSORSHIP = "donation_sponsorship"  # #123 寄付・協賛審査
    # 備考: #120（競争法 AI 相談）は AntitrustConsultation、
    # #124（コンプライアンス研修履歴）は ComplianceTraining が別テーブルで担当する。


class AntitrustApplicationStatus(StrEnum):
    """事前申請の状態遷移."""

    SUBMITTED = "submitted"  # 申請中（承認待ち）
    APPROVED = "approved"  # 承認済み（実施可）
    REJECTED = "rejected"  # 却下
    COMPLETED = "completed"  # 実施済み（記録済み）
    CANCELLED = "cancelled"  # 取下げ


class WhistleblowerCategory(StrEnum):
    """内部通報のカテゴリ（Phase3 §5.10 / Issue #123・#125-135）."""

    HARASSMENT = "harassment"  # ハラスメント
    COMPLIANCE = "compliance"  # コンプライアンス違反全般
    SAFETY = "safety"  # 安全衛生
    LABOR = "labor"  # 労務（賃金不払い等）
    CORRUPTION = "corruption"  # 汚職・贈収賄・談合
    FRAUD = "fraud"  # 不正経理・横領
    OTHER = "other"


class WhistleblowerReportStatus(StrEnum):
    """内部通報案件の状態."""

    RECEIVED = "received"  # 受付
    TRIAGE = "triage"  # 一次評価中
    INVESTIGATING = "investigating"  # 調査中
    CORRECTIVE_ACTION = "corrective_action"  # 是正措置中
    CLOSED = "closed"  # 完了
    DISMISSED = "dismissed"  # 却下（対象外・事実不確認）


class WhistleblowerSeverity(StrEnum):
    """内部通報の重大度（Matter の priority と同じ 4 段階）."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class WhistleblowerCaseRole(StrEnum):
    """調査担当者 ACL 上の役割（#127 調査担当者限定 ACL）."""

    LEAD_INVESTIGATOR = "lead_investigator"  # 主任調査担当
    INVESTIGATOR = "investigator"  # 調査担当
    OBSERVER = "observer"  # 陪席・監督者（識別情報は原則不可）


class WhistleblowerEvidenceType(StrEnum):
    """証拠の種別（#129 証拠保全）."""

    DOCUMENT = "document"
    EMAIL = "email"
    PHOTO = "photo"
    RECORDING = "recording"
    TESTIMONY = "testimony"
    SYSTEM_LOG = "system_log"
    OTHER = "other"


class WhistleblowerIntervieweeType(StrEnum):
    """ヒアリング対象の種別（#130 ヒアリング記録）."""

    REPORTER = "reporter"  # 通報者本人
    WITNESS = "witness"  # 参考人
    SUBJECT = "subject"  # 被通報者
    OTHER = "other"


class WhistleblowerTimelineEventType(StrEnum):
    """調査タイムラインのイベント種別（#131）."""

    RECEIVED = "received"
    TRIAGED = "triaged"
    ASSIGNED = "assigned"
    STATUS_CHANGED = "status_changed"
    EVIDENCE_ADDED = "evidence_added"
    INTERVIEW_CONDUCTED = "interview_conducted"
    MATTER_LINKED = "matter_linked"
    ACTION_ADDED = "action_added"
    ACCESS_GRANTED = "access_granted"
    ACCESS_REVOKED = "access_revoked"
    NOTE = "note"
    CLOSED = "closed"


class WhistleblowerActionCategory(StrEnum):
    """措置の区分（#132 是正措置管理・#133 再発防止管理）."""

    CORRECTIVE = "corrective"  # 是正措置
    PREVENTIVE = "preventive"  # 再発防止策


class WhistleblowerActionStatus(StrEnum):
    """措置の状態."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    VERIFIED = "verified"
    OVERDUE = "overdue"
