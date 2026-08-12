/**
 * Zod schemas — Construction-LegalOps-DX
 *
 * docs/api_design.md v1.0 と docs/database_design.md 準拠。
 * 全ての型は本ファイルの schema から `z.infer<>` で派生する (frontend/types/api.ts)。
 *
 * 命名規則:
 * - スキーマ: `xxxSchema`
 * - enum: `xxxEnum`
 * - レスポンスエンベロープ: `apiResponse(...)`, `paginatedSchema(...)`
 */

import { z } from "zod";

// ===========================================================================
// 基本型 / 汎用
// ===========================================================================

/** ID は将来の bigint 対応も視野に number | string 両受け */
export const idSchema = z.union([z.number().int(), z.string().min(1)]);

/** ISO 8601 (UTC) datetime */
export const datetimeSchema = z.string().datetime({ offset: true });
/** ISO 8601 date (YYYY-MM-DD) */
export const dateSchema = z.string().regex(/^\d{4}-\d{2}-\d{2}$/);

// ---------------------------------------------------------------------------
// Pagination & response envelopes
// ---------------------------------------------------------------------------

/**
 * Backend returns `{ items, total, page, size }` (FastAPI Page[T]).
 * Frontend normalizes to the same shape — no transform needed.
 */
export function paginatedSchema<T extends z.ZodTypeAny>(item: T) {
  return z
    .object({
      items: z.array(item),
      total: z.number().int().nonnegative(),
      page: z.number().int().positive(),
      size: z.number().int().positive(),
    })
    .transform(
      (raw): { page: number; size: number; total: number; items: z.infer<T>[] } => ({
        page: raw.page,
        size: raw.size,
        total: raw.total,
        items: raw.items as z.infer<T>[],
      }),
    );
}

/** Backend returns T directly (no envelope). Pass-through for type safety. */
export function apiResponse<T extends z.ZodTypeAny>(inner: T) {
  return inner;
}

// ===========================================================================
// Enums
// ===========================================================================

export const roleEnum = z.enum([
  "viewer",
  "drafter",
  "reviewer",
  "approver",
  "admin",
  "auditor",
  "guest",
]);
export type Role = z.infer<typeof roleEnum>;

export const contractStatusEnum = z.enum([
  "draft",
  "in_review",
  "approved",
  "signed",
  "executed",
  "archived",
  "rejected",
  "canceled",
]);
export type ContractStatus = z.infer<typeof contractStatusEnum>;

export const contractTypeEnum = z.enum([
  "工事請負契約",
  "業務委託契約",
  "資材購入契約",
  "下請契約",
  "設計監理契約",
  "賃貸借契約",
  "秘密保持契約",
  "売買契約",
  "覚書",
  "JV",
  "その他",
]);
export type ContractType = z.infer<typeof contractTypeEnum>;

export const confidentialityEnum = z.enum(["public", "normal", "confidential", "strict"]);
export type Confidentiality = z.infer<typeof confidentialityEnum>;

export const riskLevelEnum = z.enum(["low", "medium", "high", "critical"]);
export type RiskLevel = z.infer<typeof riskLevelEnum>;

export const riskStatusEnum = z.enum(["open", "in_progress", "mitigated", "accepted", "closed"]);
export type RiskStatus = z.infer<typeof riskStatusEnum>;

export const reviewStatusEnum = z.enum([
  "queued",
  "running",
  "completed",
  "failed",
  "accepted",
  "rejected",
]);
export type ReviewStatus = z.infer<typeof reviewStatusEnum>;

export const reviewTypeEnum = z.enum(["ai", "human", "hybrid"]);
export type ReviewType = z.infer<typeof reviewTypeEnum>;

export const workflowStepStatusEnum = z.enum([
  "pending",
  "in_progress",
  "approved",
  "rejected",
  "sent_back",
  "delegated",
  "skipped",
]);
export type WorkflowStepStatus = z.infer<typeof workflowStepStatusEnum>;

export const workflowStepTypeEnum = z.enum([
  "draft",
  "legal_review",
  "manager_approval",
  "exec_approval",
  "custom",
]);
export type WorkflowStepType = z.infer<typeof workflowStepTypeEnum>;

export const notificationChannelEnum = z.enum(["in_app", "email", "teams"]);
export type NotificationChannel = z.infer<typeof notificationChannelEnum>;

export const notificationStatusEnum = z.enum(["unread", "read", "archived"]);
export type NotificationStatus = z.infer<typeof notificationStatusEnum>;

export const uploadStorageEnum = z.enum(["sharepoint", "s3", "azure_blob", "local"]);
export type UploadStorage = z.infer<typeof uploadStorageEnum>;

export const auditActionEnum = z.string().min(1); // 例: "contract.update"

// ===========================================================================
// 高優先業務機能（変更契約・協力会社・紛争・支払コンプライアンス）
// backend/app/schemas/business.py と契約を合わせる
// ===========================================================================

// ---------------------------------------------------------------------------
// 変更契約・クレーム
// ---------------------------------------------------------------------------

export const changeOrderTypeEnum = z.enum([
  "design_change",
  "additional_work",
  "verbal_direction",
  "schedule_extension",
  "price_slide",
  "claim",
  "other",
]);
export type ChangeOrderType = z.infer<typeof changeOrderTypeEnum>;

export const changeOrderStatusEnum = z.enum([
  "registered",
  "notice_sent",
  "in_consultation",
  "approved",
  "rejected",
  "forfeited",
]);
export type ChangeOrderStatus = z.infer<typeof changeOrderStatusEnum>;

export const changeOrderSchema = z.object({
  id: idSchema,
  contract_id: idSchema,
  change_no: z.string(),
  change_type: changeOrderTypeEnum,
  title: z.string(),
  description: z.string().nullable().optional(),
  requested_by: z.string().nullable().optional(),
  requested_at: dateSchema.nullable().optional(),
  response_deadline: dateSchema.nullable().optional(),
  status: changeOrderStatusEnum,
  amount_jpy: z.number().int().nullable().optional(),
  schedule_impact_days: z.number().int().nullable().optional(),
  forfeiture_warning: z.string().nullable().optional(),
  evidence_summary: z.record(z.string(), z.unknown()).default({}),
  original_amount_jpy: z.number().int().nullable().optional(),
  cumulative_after_jpy: z.number().int().nullable().optional(),
  created_at: datetimeSchema,
  updated_at: datetimeSchema,
  deleted_at: datetimeSchema.nullable().optional(),
});
export type ChangeOrder = z.infer<typeof changeOrderSchema>;

export const changeOrderCreateSchema = changeOrderSchema
  .omit({
    id: true,
    contract_id: true,
    change_no: true,
    created_at: true,
    updated_at: true,
    deleted_at: true,
  })
  .extend({
    change_type: changeOrderTypeEnum,
    title: z.string().min(1),
    status: changeOrderStatusEnum.optional(),
  });
export type ChangeOrderCreate = z.infer<typeof changeOrderCreateSchema>;

export const changeOrderEvidenceTypeEnum = z.enum([
  "daily_report",
  "photo",
  "email",
  "minutes",
  "instruction",
  "other",
]);

export const changeOrderEvidenceSchema = z.object({
  id: idSchema,
  change_order_id: idSchema,
  evidence_type: changeOrderEvidenceTypeEnum,
  description: z.string().nullable().optional(),
  occurred_at: dateSchema.nullable().optional(),
  attachment_id: idSchema.nullable().optional(),
  created_at: datetimeSchema,
  updated_at: datetimeSchema,
});
export type ChangeOrderEvidence = z.infer<typeof changeOrderEvidenceSchema>;

export const changeOrderImpactSchema = z.object({
  contract_id: idSchema,
  original_amount_jpy: z.number().int().nullable(),
  approved_delta_jpy: z.number().int(),
  cumulative_after_jpy: z.number().int().nullable(),
  order_count: z.number().int(),
  approved_count: z.number().int(),
  schedule_impact_days_total: z.number().int(),
  forfeiture_risks: z.number().int(),
});
export type ChangeOrderImpact = z.infer<typeof changeOrderImpactSchema>;

// ---------------------------------------------------------------------------
// 協力会社コンプライアンス台帳
// ---------------------------------------------------------------------------

export const partnerTypeEnum = z.enum(["元請", "下請", "専門工事", "材料", "輸送", "その他"]);
export type PartnerType = z.infer<typeof partnerTypeEnum>;

export const antiSocialCheckEnum = z.enum(["confirmed", "unconfirmed", "pending"]);
export const bankruptcyRiskEnum = z.enum(["low", "medium", "high", "unknown"]);

export const partnerSchema = z.object({
  id: idSchema,
  name: z.string(),
  partner_type: partnerTypeEnum,
  permit_number: z.string().nullable().optional(),
  permit_types: z.array(z.string()).default([]),
  permit_specific: z.boolean().nullable().optional(),
  permit_expiry: dateSchema.nullable().optional(),
  social_insurance_joined: z.boolean().nullable().optional(),
  ccus_registered: z.boolean().nullable().optional(),
  ccus_expiry: dateSchema.nullable().optional(),
  supervisor_qualifications: z.array(z.string()).default([]),
  business_evaluation: z.record(z.string(), z.unknown()).default({}),
  anti_social_check: antiSocialCheckEnum,
  anti_social_checked_at: dateSchema.nullable().optional(),
  bankruptcy_risk: bankruptcyRiskEnum,
  insurance_joined: z.boolean().nullable().optional(),
  re_subcontract: z.boolean().nullable().optional(),
  last_transaction: dateSchema.nullable().optional(),
  risk_level: z.enum(["low", "medium", "high", "critical"]),
  risk_reasons: z.array(z.record(z.string(), z.string())).default([]),
  notes: z.string().nullable().optional(),
  created_at: datetimeSchema,
  updated_at: datetimeSchema,
  deleted_at: datetimeSchema.nullable().optional(),
});
export type Partner = z.infer<typeof partnerSchema>;

export const partnerSummarySchema = z.object({
  total: z.number().int(),
  by_risk_level: z.record(z.string(), z.number().int()).default({}),
  antisocial_unconfirmed: z.number().int(),
  permit_expiring_within_90d: z.number().int(),
});
export type PartnerSummary = z.infer<typeof partnerSummarySchema>;

// ---------------------------------------------------------------------------
// 紛争・事故・債権管理
// ---------------------------------------------------------------------------

export const disputeTypeEnum = z.enum([
  "claim",
  "defect",
  "delay",
  "payment",
  "labor",
  "accident",
  "other",
]);
export type DisputeType = z.infer<typeof disputeTypeEnum>;

export const disputeStatusEnum = z.enum([
  "open",
  "investigating",
  "escalated",
  "resolved",
  "closed",
]);
export type DisputeStatus = z.infer<typeof disputeStatusEnum>;

export const disputePriorityEnum = z.enum(["高", "中", "低"]);
export const resolutionMethodEnum = z.enum([
  "negotiation",
  "mediation",
  "arbitration",
  "lawsuit",
  "construction_dispute_review",
  "other",
]);

export const disputeSchema = z.object({
  id: idSchema,
  dispute_no: z.string(),
  contract_id: idSchema.nullable().optional(),
  dispute_type: disputeTypeEnum,
  title: z.string(),
  description: z.string().nullable().optional(),
  status: disputeStatusEnum,
  priority: disputePriorityEnum,
  counterparty: z.string().nullable().optional(),
  amount_claimed_jpy: z.number().int().nullable().optional(),
  reserve_amount_jpy: z.number().int().nullable().optional(),
  assignee_id: idSchema.nullable().optional(),
  statute_limitations_date: dateSchema.nullable().optional(),
  notice_deadline: dateSchema.nullable().optional(),
  resolution_method: resolutionMethodEnum,
  legal_hold_id: idSchema.nullable().optional(),
  exposure: z.record(z.string(), z.unknown()).default({}),
  resolved_at: datetimeSchema.nullable().optional(),
  created_at: datetimeSchema,
  updated_at: datetimeSchema,
  deleted_at: datetimeSchema.nullable().optional(),
});
export type Dispute = z.infer<typeof disputeSchema>;

export const disputeTimelineEventSchema = z.object({
  id: idSchema,
  dispute_id: idSchema,
  occurred_at: datetimeSchema,
  event_type: z.enum(["fact", "notice", "hearing", "evidence", "settlement", "escalation", "other"]),
  description: z.string().nullable().optional(),
  created_at: datetimeSchema,
  updated_at: datetimeSchema,
});
export type DisputeTimelineEvent = z.infer<typeof disputeTimelineEventSchema>;

export const disputeEvidenceSchema = z.object({
  id: idSchema,
  dispute_id: idSchema,
  evidence_type: z.enum(["contract", "email", "photo", "daily_report", "minutes", "other"]),
  description: z.string().nullable().optional(),
  occurred_at: dateSchema.nullable().optional(),
  attachment_id: idSchema.nullable().optional(),
  preserved: z.boolean(),
  created_at: datetimeSchema,
  updated_at: datetimeSchema,
});
export type DisputeEvidence = z.infer<typeof disputeEvidenceSchema>;

export const disputeDetailSchema = disputeSchema.extend({
  timeline: z.array(disputeTimelineEventSchema).default([]),
  evidence: z.array(disputeEvidenceSchema).default([]),
});
export type DisputeDetail = z.infer<typeof disputeDetailSchema>;

export const disputeExposureSchema = z.object({
  by_status: z.record(z.string(), z.record(z.string(), z.number().int())).default({}),
  total_claimed_jpy: z.number().int(),
  total_reserve_jpy: z.number().int(),
  deadlines_within_180d: z.number().int(),
});
export type DisputeExposure = z.infer<typeof disputeExposureSchema>;

// ---------------------------------------------------------------------------
// 支払・出来高・検収コンプライアンス
// ---------------------------------------------------------------------------

export const paymentFindingSchema = z.object({
  code: z.string(),
  title: z.string(),
  severity: z.enum(["block", "warn", "info"]),
  description: z.string(),
  citation: z.string(),
});
export type PaymentFinding = z.infer<typeof paymentFindingSchema>;

export const paymentComplianceSchema = z.object({
  contract_id: idSchema,
  order_date: dateSchema.nullable().optional(),
  receipt_date: dateSchema.nullable().optional(),
  inspection_date: dateSchema.nullable().optional(),
  payment_date: dateSchema.nullable().optional(),
  transaction_kind: z.string().nullable().optional(),
  is_public_work: z.boolean().default(false),
  law_version: z.string(),
  applicable_threshold_days: z.number().int(),
  days_receipt_to_payment: z.number().int().nullable().optional(),
  days_inspection_to_payment: z.number().int().nullable().optional(),
  late_interest_jpy: z.string(),
  overall_status: z.enum(["pass", "warn", "block"]),
  findings: z.array(paymentFindingSchema).default([]),
});
export type PaymentCompliance = z.infer<typeof paymentComplianceSchema>;

// ---------------------------------------------------------------------------
// P0-6 ガバナンス・法務 AI（管理画面・法務画面用）
// ---------------------------------------------------------------------------

export const accessControlEntrySchema = z.object({
  id: idSchema,
  contract_id: idSchema,
  principal_type: z.enum(["user", "department", "role", "external_counsel"]),
  principal_id: z.string(),
  access_level: z.enum(["read", "write", "approve", "admin"]),
  granted_by: idSchema.nullable().optional(),
  expires_at: datetimeSchema.nullable().optional(),
  created_at: datetimeSchema,
  updated_at: datetimeSchema,
});

export const legalHoldSchema = z.object({
  id: idSchema,
  target_type: z.string(),
  target_id: idSchema,
  reason: z.string(),
  status: z.string(),
  started_by: idSchema.nullable().optional(),
  started_at: datetimeSchema,
  released_at: datetimeSchema.nullable().optional(),
  released_by: idSchema.nullable().optional(),
  release_reason: z.string().nullable().optional(),
  evidence_ids: z.array(z.unknown()).default([]),
  ethical_wall: z.boolean().default(false),
  created_at: datetimeSchema,
  updated_at: datetimeSchema,
});

export const retentionRuleSchema = z.object({
  id: idSchema,
  data_type: z.string(),
  retention_days: z.number().int(),
  action: z.string(),
  enabled: z.boolean(),
  updated_by: idSchema.nullable().optional(),
  note: z.string().nullable().optional(),
  created_at: datetimeSchema,
  updated_at: datetimeSchema,
});

export const applicableLawSchema = z.object({
  law_code: z.string(),
  law_name: z.string(),
  applies: z.boolean(),
  confidence: z.number(),
  reason: z.string(),
  citation_url: z.string().nullable().optional(),
});

export const evidenceHitSchema = z.object({
  article_id: z.number().int(),
  title: z.string(),
  source_url: z.string().nullable().optional(),
  excerpt: z.string(),
  law_tags: z.array(z.string()).default([]),
  score: z.number(),
  source_verified: z.boolean(),
});

// ===========================================================================
// 基底スキーマ
// ===========================================================================

export const departmentSchema = z.object({
  id: idSchema,
  name: z.string(),
  code: z.string().optional(),
});
export type Department = z.infer<typeof departmentSchema>;

/** ユーザーの軽量参照 (一覧の埋め込み用) */
export const userRefSchema = z.object({
  id: idSchema,
  display_name: z.string(),
  email: z.string().email().optional(),
});
export type UserRef = z.infer<typeof userRefSchema>;

// ---------------------------------------------------------------------------
// User
// ---------------------------------------------------------------------------

export const userSchema = z.object({
  id: idSchema,
  entra_oid: z.string().optional().nullable(),
  email: z.string().email(),
  display_name: z.string(),
  role: roleEnum,
  department: departmentSchema.optional().nullable(),
  department_id: idSchema.optional().nullable(),
  is_active: z.boolean().default(true),
  created_at: datetimeSchema.optional(),
  updated_at: datetimeSchema.optional(),
  version: z.number().int().optional(),
});
export type User = z.infer<typeof userSchema>;

export const userSyncJobSchema = z.object({
  job_id: z.string().min(1),
  status: z.enum(["queued", "running", "completed", "failed"]),
  triggered_by: idSchema.optional().nullable(),
  queued_at: datetimeSchema,
  note: z.string().optional().nullable(),
});
export type UserSyncJob = z.infer<typeof userSyncJobSchema>;

// ---------------------------------------------------------------------------
// Attachment
// ---------------------------------------------------------------------------

export const attachmentSchema = z.object({
  id: idSchema,
  contract_id: idSchema.optional().nullable(),
  filename: z.string(),
  mime_type: z.string(),
  size_bytes: z.number().int().nonnegative(),
  checksum_sha256: z.string().optional(),
  storage: uploadStorageEnum,
  sharepoint_item_id: z.string().optional().nullable(),
  is_primary: z.boolean().optional(),
  uploaded_by: userRefSchema.optional().nullable(),
  created_at: datetimeSchema.optional(),
});
export type Attachment = z.infer<typeof attachmentSchema>;

// ---------------------------------------------------------------------------
// Comment
// ---------------------------------------------------------------------------

export const commentSchema = z.object({
  id: idSchema,
  target_type: z.string(), // "contracts" | "clauses" | "reviews" 等
  target_id: idSchema,
  author: userRefSchema,
  body: z.string(),
  created_at: datetimeSchema,
  updated_at: datetimeSchema.optional(),
});
export type Comment = z.infer<typeof commentSchema>;

// ---------------------------------------------------------------------------
// Clause
// ---------------------------------------------------------------------------

export const clauseSchema = z.object({
  id: idSchema,
  contract_id: idSchema,
  seq: z.number().int().nonnegative(),
  title: z.string().optional().nullable(),
  text: z.string(),
  category: z.string().optional().nullable(),
  risk_level: riskLevelEnum.optional().nullable(),
  tags: z.array(z.string()).optional(),
  created_at: datetimeSchema.optional(),
  updated_at: datetimeSchema.optional(),
});
export type Clause = z.infer<typeof clauseSchema>;

// ---------------------------------------------------------------------------
// Contract
// ---------------------------------------------------------------------------

export const contractSchema = z.object({
  id: idSchema,
  contract_no: z.string().optional().nullable(),
  title: z.string(),
  counterparty: z.string().optional().nullable(),
  contract_type: contractTypeEnum.or(z.string()),
  amount: z.number().nullable().optional(),
  currency: z.string().length(3).default("JPY").optional(),
  status: contractStatusEnum,
  confidentiality: confidentialityEnum.optional(),
  department: departmentSchema.optional().nullable(),
  department_id: idSchema.optional().nullable(),
  drafter: userRefSchema.optional().nullable(),
  start_date: dateSchema.optional().nullable(),
  end_date: dateSchema.optional().nullable(),
  metadata: z.record(z.string(), z.unknown()).optional().nullable(),
  version: z.number().int().optional(),
  created_at: datetimeSchema.optional(),
  updated_at: datetimeSchema.optional(),
  deleted_at: datetimeSchema.optional().nullable(),
});
export type Contract = z.infer<typeof contractSchema>;

export const contractCreateSchema = z.object({
  title: z.string().min(1),
  counterparty: z.string().optional(),
  contract_type: contractTypeEnum.or(z.string()),
  amount: z.number().optional(),
  currency: z.string().length(3).default("JPY").optional(),
  start_date: dateSchema.optional(),
  end_date: dateSchema.optional(),
  department_id: idSchema.optional(),
  confidentiality: confidentialityEnum.optional(),
  metadata: z.record(z.string(), z.unknown()).optional(),
});
export type ContractCreate = z.infer<typeof contractCreateSchema>;

export const contractUpdateSchema = contractCreateSchema
  .partial()
  .extend({
    status: contractStatusEnum.optional(),
    version: z.number().int(), // 楽観ロック必須
  });
export type ContractUpdate = z.infer<typeof contractUpdateSchema>;

// ---------------------------------------------------------------------------
// Review / Findings
// ---------------------------------------------------------------------------

export const reviewFindingSchema = z.object({
  clause_seq: z.number().int().nonnegative().optional(),
  title: z.string(),
  risk_level: riskLevelEnum,
  comment: z.string(),
  suggestion: z.string().optional().nullable(),
  citations: z.array(z.string()).optional(),
});
export type ReviewFinding = z.infer<typeof reviewFindingSchema>;

export const legalReviewSchema = z.object({
  id: idSchema,
  contract_id: idSchema,
  review_type: reviewTypeEnum,
  status: reviewStatusEnum,
  ai_model: z.string().optional().nullable(),
  overall_risk: riskLevelEnum.optional().nullable(),
  summary: z.string().optional().nullable(),
  scope: z.string().optional(),
  options: z.record(z.string(), z.unknown()).optional().nullable(),
  findings: z.array(reviewFindingSchema).optional(),
  disclaimer: z.string().optional(),
  started_at: datetimeSchema.optional().nullable(),
  finished_at: datetimeSchema.optional().nullable(),
  created_at: datetimeSchema.optional(),
});
export type LegalReview = z.infer<typeof legalReviewSchema>;

export const reviewCreateSchema = z.object({
  review_type: reviewTypeEnum.default("ai"),
  ai_model: z.string().optional(),
  scope: z.enum(["full", "diff", "clauses"]).optional(),
  options: z.record(z.string(), z.unknown()).optional(),
});
export type ReviewCreate = z.infer<typeof reviewCreateSchema>;

// ---------------------------------------------------------------------------
// Risk
// ---------------------------------------------------------------------------

export const riskItemSchema = z.object({
  id: idSchema,
  contract_id: idSchema.optional().nullable(),
  clause_id: idSchema.optional().nullable(),
  title: z.string(),
  description: z.string().optional().nullable(),
  severity: riskLevelEnum,
  probability: riskLevelEnum.optional(),
  impact: riskLevelEnum.optional(),
  status: riskStatusEnum,
  mitigation: z.string().optional().nullable(),
  owner: userRefSchema.optional().nullable(),
  category: z.string().optional().nullable(),
  created_at: datetimeSchema.optional(),
  updated_at: datetimeSchema.optional(),
});
export type RiskItem = z.infer<typeof riskItemSchema>;

export const riskUpdateSchema = z.object({
  status: riskStatusEnum.optional(),
  mitigation: z.string().optional(),
  owner_id: idSchema.optional(),
  severity: riskLevelEnum.optional(),
});
export type RiskUpdate = z.infer<typeof riskUpdateSchema>;

export const riskHeatmapCellSchema = z.object({
  probability: riskLevelEnum,
  impact: riskLevelEnum,
  count: z.number().int().nonnegative(),
});
export const riskHeatmapSchema = z.object({
  matrix: z.array(riskHeatmapCellSchema),
});
export type RiskHeatmap = z.infer<typeof riskHeatmapSchema>;

// ---------------------------------------------------------------------------
// Workflow
// ---------------------------------------------------------------------------

export const workflowStepDefinitionSchema = z.object({
  seq: z.number().int().positive(),
  name: z.string(),
  step_type: workflowStepTypeEnum,
  assignee_role: roleEnum.optional(),
  required: z.boolean().optional(),
});
export type WorkflowStepDefinition = z.infer<typeof workflowStepDefinitionSchema>;

export const workflowDefinitionSchema = z.object({
  steps: z.array(workflowStepDefinitionSchema),
});

export const workflowSchema = z.object({
  id: idSchema,
  code: z.string(),
  name: z.string(),
  contract_type: contractTypeEnum.or(z.string()).optional().nullable(),
  is_active: z.boolean().default(true),
  definition: workflowDefinitionSchema,
  created_at: datetimeSchema.optional(),
  updated_at: datetimeSchema.optional(),
});
export type Workflow = z.infer<typeof workflowSchema>;

export const workflowStepSchema = z.object({
  id: idSchema,
  contract_id: idSchema,
  workflow_id: idSchema.optional().nullable(),
  seq: z.number().int().positive(),
  name: z.string(),
  step_type: workflowStepTypeEnum,
  status: workflowStepStatusEnum,
  assignee: userRefSchema.optional().nullable(),
  assignee_role: roleEnum.optional().nullable(),
  comment: z.string().optional().nullable(),
  started_at: datetimeSchema.optional().nullable(),
  finished_at: datetimeSchema.optional().nullable(),
  decided_at: datetimeSchema.optional().nullable(),
  due_at: datetimeSchema.optional().nullable(),
});
export type WorkflowStep = z.infer<typeof workflowStepSchema>;

/** WorkflowInstanceOut — GET /workflows/{instance_id} のレスポンス。
 *  instance_id は contract_id と同一（workflow_service.py の設計による）。
 */
export const workflowInstanceSchema = z.object({
  id: idSchema,
  workflow_id: idSchema,
  contract_id: idSchema,
  status: z.string(),
  current_seq: z.number().int().nullable().optional(),
  started_at: datetimeSchema.optional().nullable(),
  completed_at: datetimeSchema.optional().nullable(),
});
export type WorkflowInstance = z.infer<typeof workflowInstanceSchema>;

export const workflowApplicationSchema = z.object({
  step_id: idSchema,
  contract_id: idSchema,
  contract_no: z.string().nullable().optional(),
  title: z.string(),
  contract_type: z.string(),
  counterparty: z.string().nullable().optional(),
  amount: z.number().nullable().optional(),
  applicant: z.string().nullable().optional(),
  step_name: z.string(),
  step_type: z.string(),
  status: workflowStepStatusEnum.or(z.string()),
  due_at: datetimeSchema.nullable().optional(),
  submitted_at: datetimeSchema,
});
export type WorkflowApplication = z.infer<typeof workflowApplicationSchema>;

// ---------------------------------------------------------------------------
// Compliance
// ---------------------------------------------------------------------------

export const complianceChecklistItemSchema = z.object({
  id: idSchema,
  code: z.string(),
  title: z.string(),
  description: z.string().optional(),
  category: z.string().optional(),
  severity: riskLevelEnum.optional(),
});
export const complianceChecklistSchema = z.object({
  id: idSchema,
  code: z.string(),
  name: z.string(),
  category: z.string(),
  contract_type: contractTypeEnum.or(z.string()).optional().nullable(),
  description: z.string().optional().nullable(),
  is_active: z.boolean().default(true),
});
export type ComplianceChecklist = z.infer<typeof complianceChecklistSchema>;

export const complianceRunResultSchema = z.object({
  item_id: idSchema,
  passed: z.boolean(),
  note: z.string().optional(),
});
export const complianceFindingSchema = z.object({
  rule_id: z.string(),
  rule_name: z.string(),
  severity: z.enum(["info", "low", "medium", "high", "critical"]),
  status: z.enum(["pass", "fail", "warning", "skipped"]),
  message: z.string(),
  clause_seq: z.number().int().optional().nullable(),
  citations: z.array(z.string()).default([]),
});
export const complianceCheckResultSchema = z.object({
  contract_id: idSchema,
  checked_at: datetimeSchema,
  overall_status: z.enum(["pass", "fail", "warning", "skipped"]),
  findings: z.array(complianceFindingSchema).default([]),
  disclaimer: z.string(),
});
export type ComplianceCheckResult = z.infer<typeof complianceCheckResultSchema>;
export const complianceRunSchema = z.object({
  job_id: z.string().min(1),
  contract_id: idSchema,
  accepted_at: datetimeSchema,
  status: z.enum(["queued", "running", "done", "failed"]),
  disclaimer: z.string(),
});
export type ComplianceRun = z.infer<typeof complianceRunSchema>;

// ---------------------------------------------------------------------------
// Template / Clause Library
// ---------------------------------------------------------------------------

export const clauseLibrarySchema = z.object({
  id: idSchema,
  title: z.string(),
  body: z.string(),
  category: z.string().optional(),
  recommendation: z.enum(["required", "recommended", "optional", "prohibited"]).optional(),
  tags: z.array(z.string()).optional(),
  created_at: datetimeSchema.optional(),
});
export type ClauseLibraryEntry = z.infer<typeof clauseLibrarySchema>;

export const templateSchema = z.object({
  id: idSchema,
  code: z.string(),
  name: z.string(),
  contract_type: contractTypeEnum.or(z.string()).optional().nullable(),
  description: z.string().optional().nullable(),
  body: z.string().optional(),
  tags: z.array(z.string()).optional(),
  is_active: z.boolean().default(true),
  created_at: datetimeSchema.optional(),
  updated_at: datetimeSchema.optional(),
});
export type Template = z.infer<typeof templateSchema>;

// ---------------------------------------------------------------------------
// Knowledge
// ---------------------------------------------------------------------------

export const knowledgeArticleSchema = z.object({
  id: idSchema,
  title: z.string(),
  body: z.string(),
  tags: z.array(z.string()).optional(),
  author: userRefSchema.optional().nullable(),
  created_at: datetimeSchema.optional(),
  updated_at: datetimeSchema.optional(),
});
export type KnowledgeArticle = z.infer<typeof knowledgeArticleSchema>;

// ---------------------------------------------------------------------------
// Audit log
// ---------------------------------------------------------------------------

export const auditLogSchema = z.object({
  id: idSchema,
  occurred_at: datetimeSchema,
  actor: userRefSchema.optional().nullable(),
  action: auditActionEnum,
  target_type: z.string(),
  target_id: idSchema.optional().nullable(),
  request_id: z.string().optional().nullable(),
  payload: z.record(z.string(), z.unknown()).optional().nullable(),
  previous_hash: z.string().optional().nullable(),
  hash_chain: z.string().optional().nullable(),
});
export type AuditLog = z.infer<typeof auditLogSchema>;

export const auditVerifyResultSchema = z.object({
  verified: z.boolean(),
  total: z.number().int().nonnegative(),
  broken_at: z.union([idSchema, z.null()]),
});
export type AuditVerifyResult = z.infer<typeof auditVerifyResultSchema>;

// ---------------------------------------------------------------------------
// Notification
// ---------------------------------------------------------------------------

export const notificationSchema = z.object({
  id: idSchema,
  user_id: idSchema,
  channel: notificationChannelEnum,
  status: notificationStatusEnum,
  title: z.string(),
  body: z.string().optional(),
  link: z.string().optional().nullable(),
  meta: z.record(z.string(), z.unknown()).optional().nullable(),
  created_at: datetimeSchema,
  read_at: datetimeSchema.optional().nullable(),
});
export type Notification = z.infer<typeof notificationSchema>;

// ---------------------------------------------------------------------------
// Dashboard — matches backend DashboardSummary / DashboardTrends
// ---------------------------------------------------------------------------

export const dashboardSummarySchema = z.object({
  pending_review: z.number().int().nonnegative(),
  pending_approval: z.number().int().nonnegative(),
  overdue: z.number().int().nonnegative(),
  high_risk: z.number().int().nonnegative(),
  recent_completed: z.number().int().nonnegative(),
  my_tasks: z.number().int().nonnegative(),
  avg_risk_score: z.number().nonnegative(),
  contracts_by_status: z.record(z.string(), z.number().int().nonnegative()),
  pending_reviews: z.number().int().nonnegative(),
  generated_at: z.string().datetime({ offset: true }).nullable().optional(),
});
export type DashboardSummary = z.infer<typeof dashboardSummarySchema>;

export const dashboardTrendPointSchema = z.object({
  bucket: dateSchema,
  value: z.number().int().nonnegative(),
});
export const dashboardTrendsSchema = z.object({
  granularity: z.enum(["week", "month"]),
  series: z.record(z.string(), z.array(dashboardTrendPointSchema)),
});
export type DashboardTrends = z.infer<typeof dashboardTrendsSchema>;

// ---------------------------------------------------------------------------
// Health / Meta
// ---------------------------------------------------------------------------

export const healthSchema = z.object({ status: z.literal("ok") });
export const versionSchema = z.object({
  version: z.string(),
  commit: z.string().optional(),
});

// ---------------------------------------------------------------------------
// AI 設定（ハイブリッド AI レビュー基盤・Issue #28）
//
// backend/app/schemas/settings.py の Pydantic 契約を 1:1 でミラーする。
// レスポンス側は平文 API キーを一切含めない（has_key / key_masked のみ）。
// 表示用タイムスタンプは SQLite の naive datetime でも壊れないよう緩く受ける。
// ---------------------------------------------------------------------------

export const aiProviderEnum = z.enum(["perplexity", "claude"]);
export type AiProvider = z.infer<typeof aiProviderEnum>;

/** ok=疎通+認証成功 / failed=到達したがエラー / unavailable=意図的に休眠 */
export const connectionTestStatusEnum = z.enum(["ok", "failed", "unavailable"]);
export type ConnectionTestStatus = z.infer<typeof connectionTestStatusEnum>;

export const aiProviderConfigSchema = z.object({
  provider: aiProviderEnum,
  has_key: z.boolean(),
  key_masked: z.string().nullable().optional(),
  model: z.string().nullable().optional(),
  is_active: z.boolean(),
  last_test_status: connectionTestStatusEnum.nullable().optional(),
  last_test_message: z.string().nullable().optional(),
  // 表示専用: タイムゾーン有無を問わず受ける（strict datetime にしない）
  last_tested_at: z.string().nullable().optional(),
  updated_at: z.string().nullable().optional(),
});
export type AiProviderConfig = z.infer<typeof aiProviderConfigSchema>;

export const aiSettingsSchema = z.object({
  providers: z.array(aiProviderConfigSchema),
});
export type AiSettings = z.infer<typeof aiSettingsSchema>;

export const connectionTestSchema = z.object({
  provider: aiProviderEnum,
  status: connectionTestStatusEnum,
  message: z.string(),
  tested_at: z.string().nullable().optional(),
});
export type ConnectionTest = z.infer<typeof connectionTestSchema>;

/** 「保存・設定」リクエスト本文。api_key 省略=既存維持 / 空文字=クリア / 値=暗号化保存 */
export const aiSettingsUpdateSchema = z.object({
  api_key: z.string().optional(),
  model: z.string().max(64).optional(),
  is_active: z.boolean(),
});
export type AiSettingsUpdate = z.infer<typeof aiSettingsUpdateSchema>;

// ===========================================================================
// 共通: Paginated 型
// ===========================================================================

export interface Paginated<T> {
  page: number;
  size: number;
  total: number;
  items: T[];
}
