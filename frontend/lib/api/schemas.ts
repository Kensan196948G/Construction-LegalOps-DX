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
  "pending",
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
  // backend は Decimal を文字列で返す（例 "3500000.00"）ため数値へ正規化する
  amount: z
    .union([z.number(), z.string()])
    .transform((value) => (typeof value === "string" ? Number(value) : value))
    .nullable()
    .optional(),
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
  title: z.string().optional().nullable(),
  risk_level: riskLevelEnum,
  comment: z.string(),
  suggestion: z.string().optional().nullable(),
  citations: z.array(z.string()).optional(),
  verdict: z.string().optional(),
});
export type ReviewFinding = z.infer<typeof reviewFindingSchema>;

export const legalReviewSchema = z.object({
  id: idSchema,
  contract_id: idSchema,
  review_type: reviewTypeEnum,
  status: reviewStatusEnum,
  ai_model: z.string().optional().nullable(),
  overall_risk: riskLevelEnum.optional().nullable(),
  risk_score: z.number().int().min(0).max(100).optional().nullable(),
  summary: z.string().optional().nullable(),
  scope: z.string().optional(),
  options: z.record(z.string(), z.unknown()).optional().nullable(),
  findings: z.array(reviewFindingSchema).optional(),
  suggested_actions: z
    .array(
      z.object({
        action: z.string(),
        target_clause_seq: z.number().int().optional().nullable(),
        description: z.string(),
        replacement_text: z.string().optional().nullable(),
      }),
    )
    .optional(),
  result: z.record(z.string(), z.unknown()).optional().nullable(),
  disclaimer: z.string().optional(),
  started_at: datetimeSchema.optional().nullable(),
  finished_at: datetimeSchema.optional().nullable(),
  created_at: datetimeSchema.optional(),
});

export const contractDocumentSchema = z.object({
  id: idSchema,
  contract_id: idSchema,
  doc_type: z.string(),
  title: z.string(),
  priority: z.number().int(),
  doc_date: z.string().optional().nullable(),
  amount_jpy: z.number().optional().nullable(),
  start_date: z.string().optional().nullable(),
  end_date: z.string().optional().nullable(),
  content: z.string().optional().nullable(),
  source_attachment_id: idSchema.optional().nullable(),
  version: z.number().int(),
  created_at: datetimeSchema.optional(),
  updated_at: datetimeSchema.optional(),
});
export type ContractDocument = z.infer<typeof contractDocumentSchema>;
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
  // backend は Decimal を文字列で返すため数値へ正規化する
  amount: z
    .union([z.number(), z.string()])
    .transform((value) => (typeof value === "string" ? Number(value) : value))
    .nullable()
    .optional(),
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
  actor: z
    .object({
      id: idSchema,
      display_name: z.string().optional().nullable(),
    })
    .optional()
    .nullable(),
  actor_id: idSchema.optional().nullable(),
  actor_role: z.string().optional().nullable(),
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

export const aiProviderEnum = z.enum(["perplexity", "claude", "deepseek"]);
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

// ===========================================================================
// 知財管理・競合ウォッチ・審査書類 (JPO 特許情報取得API)
// ===========================================================================

export const ipTypeEnum = z.enum(["patent", "design", "trademark"]);
export type IpType = z.infer<typeof ipTypeEnum>;

export const ipDocTypeEnum = z.enum([
  "refusal_reason",
  "opinion_amendment",
  "decision",
  "citation",
]);
export type IpDocType = z.infer<typeof ipDocTypeEnum>;

export const ipAssetSchema = z.object({
  id: idSchema,
  application_number: z.string(),
  ip_type: ipTypeEnum,
  invention_title: z.string().nullable().optional(),
  filing_date: dateSchema.nullable().optional(),
  applicants: z
    .array(
      z.object({
        applicantAttorneyCd: z.string().optional(),
        name: z.string().optional(),
        applicantAttorneyClass: z.string().optional(),
      })
    )
    .default([]),
  publication_number: z.string().nullable().optional(),
  registration_number: z.string().nullable().optional(),
  status: z.string(),
  progress_data: z.record(z.string(), z.unknown()).default({}),
  registration_data: z.record(z.string(), z.unknown()).default({}),
  jplatpat_url: z.string().nullable().optional(),
  last_synced_at: datetimeSchema.nullable().optional(),
  watch_target_id: idSchema.nullable().optional(),
  notes: z.string().nullable().optional(),
  created_at: datetimeSchema,
  updated_at: datetimeSchema,
  deleted_at: datetimeSchema.nullable().optional(),
});
export type IpAsset = z.infer<typeof ipAssetSchema>;

export const ipAssetCreateSchema = z.object({
  application_number: z.string().min(6).max(16),
  ip_type: ipTypeEnum.default("patent"),
  watch_target_id: idSchema.nullable().optional(),
  notes: z.string().max(4000).nullable().optional(),
});
export type IpAssetCreate = z.infer<typeof ipAssetCreateSchema>;

export const ipAssetSyncResultSchema = z.object({
  asset_id: z.number().int(),
  application_number: z.string(),
  api_calls: z.number().int(),
  events_created: z.number().int(),
  updated: z.boolean(),
  message: z.string(),
});
export type IpAssetSyncResult = z.infer<typeof ipAssetSyncResultSchema>;

export const ipWatchTargetSchema = z.object({
  id: idSchema,
  name: z.string(),
  applicant_code: z.string().nullable().optional(),
  ip_types: z.array(ipTypeEnum).default(["patent"]),
  status: z.enum(["active", "paused"]),
  notes: z.string().nullable().optional(),
  asset_count: z.number().int().default(0),
  unread_event_count: z.number().int().default(0),
  created_at: datetimeSchema,
  updated_at: datetimeSchema,
  deleted_at: datetimeSchema.nullable().optional(),
});
export type IpWatchTarget = z.infer<typeof ipWatchTargetSchema>;

export const ipWatchTargetCreateSchema = z.object({
  name: z.string().min(1).max(256),
  applicant_code: z.string().max(16).nullable().optional(),
  ip_types: z.array(ipTypeEnum).default(["patent"]),
  status: z.enum(["active", "paused"]).default("active"),
  notes: z.string().max(4000).nullable().optional(),
});
export type IpWatchTargetCreate = z.infer<typeof ipWatchTargetCreateSchema>;

export const ipWatchTargetSyncResultSchema = z.object({
  target_id: z.number().int(),
  name: z.string(),
  api_calls: z.number().int(),
  events_created: z.number().int(),
  scanned_assets: z.number().int(),
  message: z.string(),
});
export type IpWatchTargetSyncResult = z.infer<typeof ipWatchTargetSyncResultSchema>;

export const ipWatchEventSchema = z.object({
  id: idSchema,
  watch_target_id: idSchema,
  ip_asset_id: idSchema.nullable().optional(),
  application_number: z.string().nullable().optional(),
  event_type: z.string(),
  event_code: z.string().nullable().optional(),
  description: z.string().nullable().optional(),
  event_data: z.record(z.string(), z.unknown()).default({}),
  is_read: z.boolean().default(false),
  detected_at: datetimeSchema,
  created_at: datetimeSchema,
  updated_at: datetimeSchema,
  deleted_at: datetimeSchema.nullable().optional(),
});
export type IpWatchEvent = z.infer<typeof ipWatchEventSchema>;

export const ipDocumentSchema = z.object({
  id: idSchema,
  ip_asset_id: idSchema,
  doc_type: ipDocTypeEnum,
  doc_name: z.string().nullable().optional(),
  fetched_at: datetimeSchema,
  content_text: z.string().nullable().optional(),
  ai_summary: z.string().nullable().optional(),
  ai_findings: z
    .object({
      issues: z
        .array(
          z.object({
            severity: z.string().optional(),
            title: z.string().optional(),
            description: z.string().optional(),
            law: z.string().optional(),
          })
        )
        .default([]),
      suggested_actions: z.array(z.string()).default([]),
      deadline: z.string().nullable().optional(),
      disclaimer: z.string().optional(),
    })
    .default({}),
  ai_model: z.string().nullable().optional(),
  analyzed_at: datetimeSchema.nullable().optional(),
  error: z.string().nullable().optional(),
  created_at: datetimeSchema,
  updated_at: datetimeSchema,
  deleted_at: datetimeSchema.nullable().optional(),
});
export type IpDocument = z.infer<typeof ipDocumentSchema>;

export const ipDashboardSchema = z.object({
  total_assets: z.number().int(),
  by_type: z.record(z.string(), z.number().int()).default({}),
  by_status: z.record(z.string(), z.number().int()).default({}),
  total_watch_targets: z.number().int(),
  active_watch_targets: z.number().int(),
  unread_events: z.number().int(),
  recent_events: z.array(ipWatchEventSchema).default([]),
  documents_total: z.number().int(),
  documents_analyzed: z.number().int(),
  api_mode: z.string(),
  api_configured: z.boolean(),
});
export type IpDashboard = z.infer<typeof ipDashboardSchema>;

export const jpoStatusSchema = z.object({
  mode: z.string(),
  configured: z.boolean(),
  base_url: z.string(),
  max_calls_per_minute: z.number().int(),
});
export type JpoStatus = z.infer<typeof jpoStatusSchema>;

// ===========================================================================
// 電子契約・電子署名 (ロードマップ #1-4 / migration 010 / api v1 signing)
// ===========================================================================

export const signingMethodEnum = z.enum(["electronic", "paper"]);
export type SigningMethod = z.infer<typeof signingMethodEnum>;

export const signingProviderEnum = z.enum([
  "cloudsign",
  "docusign",
  "demo",
  "manual",
]);
export type SigningProvider = z.infer<typeof signingProviderEnum>;

export const signingStatusEnum = z.enum([
  "draft",
  "sent",
  "viewed",
  "signed",
  "completed",
  "cancelled",
]);
export type SigningStatus = z.infer<typeof signingStatusEnum>;

/** 署名エンベロープ（作成/一覧/詳細・状態遷移後の共通レスポンス） */
export const signingEnvelopeSchema = z.object({
  id: idSchema,
  envelope_no: z.string(),
  contract_id: idSchema,
  status: signingStatusEnum.or(z.string()),
  method: signingMethodEnum.or(z.string()).optional(),
  provider: signingProviderEnum.or(z.string()).optional(),
  provider_envelope_id: z.string().nullable().optional(),
  counterparty_name: z.string().nullable().optional(),
  counterparty_email: z.string().nullable().optional(),
  note: z.string().nullable().optional(),
  consent_confirmed_at: datetimeSchema.nullable().optional(),
  consentor_name: z.string().nullable().optional(),
  consentor_email: z.string().nullable().optional(),
  consent_note: z.string().nullable().optional(),
  sent_at: datetimeSchema.nullable().optional(),
  viewed_at: datetimeSchema.nullable().optional(),
  signed_at: datetimeSchema.nullable().optional(),
  completed_at: datetimeSchema.nullable().optional(),
  signer_name: z.string().nullable().optional(),
  signer_email: z.string().nullable().optional(),
  signed_attachment_id: idSchema.nullable().optional(),
  signed_document_id: idSchema.nullable().optional(),
  created_by: idSchema.nullable().optional(),
  created_at: datetimeSchema,
  updated_at: datetimeSchema,
  version: z.number().int().optional(),
});
export type SigningEnvelope = z.infer<typeof signingEnvelopeSchema>;

export const signingEventSchema = z.object({
  id: idSchema,
  envelope_id: idSchema,
  event_type: z.string(),
  actor_id: idSchema.nullable().optional(),
  payload: z.record(z.string(), z.unknown()).nullable().optional(),
  created_at: datetimeSchema,
});
export type SigningEvent = z.infer<typeof signingEventSchema>;

export const signingEnvelopeCreateSchema = z.object({
  contract_id: idSchema,
  method: signingMethodEnum.default("electronic"),
  provider: signingProviderEnum.default("demo"),
  counterparty_name: z.string().max(255).nullish(),
  counterparty_email: z.string().max(255).nullish(),
  note: z.string().nullish(),
});
export type SigningEnvelopeCreate = z.infer<typeof signingEnvelopeCreateSchema>;

// ===========================================================================
// 契約交渉・Redline (ロードマップ #5-8 / migration 011 / api v1 negotiations)
// ===========================================================================

export const clauseNegotiationStatusEnum = z.enum([
  "accepted",
  "rejected",
  "negotiating",
]);
export type ClauseNegotiationStatus = z.infer<typeof clauseNegotiationStatusEnum>;

export const clauseOwnerEnum = z.enum(["法務", "工事", "営業", "購買", "その他"]);
export type ClauseOwner = z.infer<typeof clauseOwnerEnum>;

export const negotiationActionEnum = z.enum([
  "redline",
  "demand",
  "concession",
  "comment",
]);
export type NegotiationAction = z.infer<typeof negotiationActionEnum>;

/** 交渉イベント 1 件（証跡・読み取りのみ） */
export const negotiationEventSchema = z.object({
  id: idSchema,
  contract_id: idSchema,
  clause_id: idSchema.nullable().optional(),
  round_no: z.number().int().nullable().optional(),
  action: z.string(),
  status_from: z.string().nullable().optional(),
  status_to: z.string().nullable().optional(),
  owner_from: z.string().nullable().optional(),
  owner_to: z.string().nullable().optional(),
  note: z.string().nullable().optional(),
  proposed_text: z.string().nullable().optional(),
  actor_id: idSchema.nullable().optional(),
  created_at: datetimeSchema,
});
export type NegotiationEvent = z.infer<typeof negotiationEventSchema>;

export const negotiationEventCreateSchema = z.object({
  action: negotiationActionEnum,
  clause_id: idSchema.nullish(),
  round_no: z.number().int().min(1).nullish(),
  note: z.string().max(2000).nullish(),
  proposed_text: z.string().max(20000).nullish(),
});
export type NegotiationEventCreate = z.infer<typeof negotiationEventCreateSchema>;

/** 更新後の条項（negotiation_status / clause_owner / negotiated_text を含む） */
export const clauseNegotiationStateSchema = z.object({
  id: idSchema,
  contract_id: idSchema,
  seq: z.number().int(),
  title: z.string().nullable().optional(),
  body: z.string(),
  risk_level: z.string().nullable().optional(),
  negotiation_status: clauseNegotiationStatusEnum.or(z.string()).nullable().optional(),
  clause_owner: clauseOwnerEnum.or(z.string()).nullable().optional(),
  negotiated_text: z.string().nullable().optional(),
});
export type ClauseNegotiationState = z.infer<typeof clauseNegotiationStateSchema>;

// ===========================================================================
// 契約義務・Obligations Calendar (ロードマップ #9-13 / migration 012 / api v1 obligations)
// ===========================================================================

export const obligationStatusEnum = z.enum([
  "open",
  "in_progress",
  "completed",
  "waived",
]);
export type ObligationStatus = z.infer<typeof obligationStatusEnum>;

export const obligationTypeEnum = z.enum([
  "report",
  "notice",
  "submit",
  "insurance",
  "renewal",
  "condition",
  "closing",
  "other",
]);
export type ObligationType = z.infer<typeof obligationTypeEnum>;

export const obligationSchema = z.object({
  id: idSchema,
  contract_id: idSchema,
  obligation_type: obligationTypeEnum.or(z.string()),
  title: z.string(),
  description: z.string().nullable().optional(),
  due_date: dateSchema.nullable().optional(),
  status: obligationStatusEnum.or(z.string()),
  assignee_id: idSchema.nullable().optional(),
  completed_at: datetimeSchema.nullable().optional(),
  created_by: idSchema.nullable().optional(),
  created_at: datetimeSchema,
  updated_at: datetimeSchema,
});
export type Obligation = z.infer<typeof obligationSchema>;

export const obligationCreateSchema = z.object({
  obligation_type: obligationTypeEnum,
  title: z.string().min(1).max(256),
  description: z.string().max(4000).nullish(),
  due_date: dateSchema.nullish(),
  assignee_id: idSchema.nullish(),
  status: obligationStatusEnum.default("open"),
});
export type ObligationCreate = z.infer<typeof obligationCreateSchema>;

/** 自動更新判定結果（#12） */
export const renewalCheckSchema = z.object({
  contract_id: idSchema,
  contract_no: z.string().nullable().optional(),
  title: z.string(),
  end_date: dateSchema.nullable().optional(),
  auto_renewal: z.boolean(),
  renewal_notice_days: z.number().int(),
  notice_deadline: dateSchema.nullable().optional(),
  days_left: z.number().int().nullable().optional(),
  state: z.string(),
});
export type RenewalCheck = z.infer<typeof renewalCheckSchema>;

// ===========================================================================
// 契約書全文検索 (ロードマップ #5下位 / api v1 contract_search)
// ===========================================================================

export const contractSearchHitSchema = z.object({
  kind: z.enum(["contract", "clause", "document"]).or(z.string()),
  record_id: idSchema,
  contract_id: idSchema,
  contract_no: z.string().nullable().optional(),
  title: z.string().nullable().optional(),
  snippet: z.string().nullable().optional(),
  matched_fields: z.array(z.string()).default([]),
  score: z.number(),
});
export type ContractSearchHit = z.infer<typeof contractSearchHitSchema>;

// ===========================================================================
// Legal Matter Management (ロードマップ #71-84 / migration 013 / api v1 matters)
// ===========================================================================

export const matterStatusEnum = z.enum([
  "open",
  "in_progress",
  "waiting",
  "on_hold",
  "closed",
]);
export type MatterStatus = z.infer<typeof matterStatusEnum>;

export const matterPriorityEnum = z.enum(["low", "medium", "high", "critical"]);
export type MatterPriority = z.infer<typeof matterPriorityEnum>;

export const matterTypeEnum = z.enum([
  "contract",
  "dispute",
  "compliance",
  "labor",
  "regulatory",
  "other",
]);
export type MatterType = z.infer<typeof matterTypeEnum>;

export const matterSchema = z.object({
  id: idSchema,
  matter_no: z.string(),
  title: z.string(),
  description: z.string().nullable().optional(),
  matter_type: matterTypeEnum.or(z.string()),
  status: matterStatusEnum.or(z.string()),
  priority: matterPriorityEnum.or(z.string()),
  assignee_id: idSchema.nullable().optional(),
  source_type: z.string().nullable().optional(),
  source_id: idSchema.nullable().optional(),
  legal_hold_case_id: idSchema.nullable().optional(),
  opened_at: datetimeSchema,
  closed_at: datetimeSchema.nullable().optional(),
  close_note: z.string().nullable().optional(),
  created_by: idSchema.nullable().optional(),
  created_at: datetimeSchema,
  updated_at: datetimeSchema,
});
export type Matter = z.infer<typeof matterSchema>;

export const matterCreateSchema = z.object({
  title: z.string().min(1).max(256),
  matter_type: matterTypeEnum,
  description: z.string().max(8000).nullish(),
  priority: matterPriorityEnum.default("medium"),
  assignee_id: idSchema.nullish(),
  source_type: z.string().nullish(),
  source_id: idSchema.nullish(),
  contract_ids: z.array(idSchema).default([]),
  legal_hold_case_id: idSchema.nullish(),
});
export type MatterCreate = z.infer<typeof matterCreateSchema>;

export const matterUpdateSchema = z.object({
  title: z.string().min(1).max(256).nullish(),
  description: z.string().max(8000).nullish(),
  priority: matterPriorityEnum.nullish(),
});
export type MatterUpdate = z.infer<typeof matterUpdateSchema>;

export const matterStatusInSchema = z.object({
  status: matterStatusEnum,
  note: z.string().max(2000).nullish(),
});
export type MatterStatusIn = z.infer<typeof matterStatusInSchema>;

export const matterAssignInSchema = z.object({
  assignee_id: idSchema.nullable(),
  note: z.string().max(2000).nullish(),
});
export type MatterAssignIn = z.infer<typeof matterAssignInSchema>;

export const matterNoteInSchema = z.object({
  note: z.string().min(1).max(4000),
});
export type MatterNoteIn = z.infer<typeof matterNoteInSchema>;

export const matterEventSchema = z.object({
  id: idSchema,
  matter_id: idSchema,
  event_type: z.string(),
  note: z.string().nullable().optional(),
  payload: z.record(z.string(), z.unknown()).nullable().optional(),
  actor_id: idSchema.nullable().optional(),
  created_at: datetimeSchema,
});
export type MatterEvent = z.infer<typeof matterEventSchema>;

export const matterContractSchema = z.object({
  contract_id: idSchema,
  contract_no: z.string().nullable().optional(),
  title: z.string(),
});
export type MatterContract = z.infer<typeof matterContractSchema>;

// ===========================================================================
// 顧問弁護士・外部法律事務所 (ロードマップ #85-96 / migration 014 / api v1 outside_counsel)
// ===========================================================================

export const lawFirmSchema = z.object({
  id: idSchema,
  firm_name: z.string(),
  contact_email: z.string().nullable().optional(),
  phone: z.string().nullable().optional(),
  address: z.string().nullable().optional(),
  notes: z.string().nullable().optional(),
  is_active: z.boolean(),
});
export type LawFirm = z.infer<typeof lawFirmSchema>;

export const lawFirmCreateSchema = z.object({
  firm_name: z.string().min(1).max(256),
  contact_email: z.string().max(256).nullish(),
  phone: z.string().max(64).nullish(),
  address: z.string().max(512).nullish(),
  notes: z.string().max(4000).nullish(),
});
export type LawFirmCreate = z.infer<typeof lawFirmCreateSchema>;

export const counselLawyerSchema = z.object({
  id: idSchema,
  firm_id: idSchema,
  lawyer_name: z.string(),
  email: z.string().nullable().optional(),
  bar_number: z.string().nullable().optional(),
  specialties: z.string().nullable().optional(),
  is_active: z.boolean(),
});
export type CounselLawyer = z.infer<typeof counselLawyerSchema>;

export const counselLawyerCreateSchema = z.object({
  firm_id: idSchema,
  lawyer_name: z.string().min(1).max(128),
  email: z.string().max(256).nullish(),
  bar_number: z.string().max(64).nullish(),
  specialties: z.string().max(512).nullish(),
});
export type CounselLawyerCreate = z.infer<typeof counselLawyerCreateSchema>;

export const engagementStatusEnum = z.enum([
  "open",
  "answered",
  "confirmed",
  "cancelled",
]);
export type EngagementStatus = z.infer<typeof engagementStatusEnum>;

export const engagementSchema = z.object({
  id: idSchema,
  engagement_no: z.string(),
  firm_id: idSchema,
  lawyer_id: idSchema.nullable().optional(),
  matter_id: idSchema.nullable().optional(),
  title: z.string(),
  question: z.string(),
  answer: z.string().nullable().optional(),
  status: engagementStatusEnum.or(z.string()),
  due_date: dateSchema.nullable().optional(),
  answered_at: datetimeSchema.nullable().optional(),
  answered_by: idSchema.nullable().optional(),
  conflict_of_interest: z.boolean(),
  conflict_note: z.string().nullable().optional(),
  confidential: z.boolean(),
  fee_estimate_jpy: z.number().int().nullable().optional(),
  notes: z.string().nullable().optional(),
  created_by: idSchema.nullable().optional(),
  created_at: datetimeSchema,
  updated_at: datetimeSchema,
});
export type Engagement = z.infer<typeof engagementSchema>;

export const engagementCreateSchema = z.object({
  firm_id: idSchema,
  lawyer_id: idSchema.nullish(),
  matter_id: idSchema.nullish(),
  title: z.string().min(1).max(256),
  question: z.string().min(1).max(20000),
  due_date: dateSchema.nullish(),
  conflict_of_interest: z.boolean().default(false),
  conflict_note: z.string().max(2000).nullish(),
  confidential: z.boolean().default(false),
  fee_estimate_jpy: z.number().int().min(0).nullish(),
});
export type EngagementCreate = z.infer<typeof engagementCreateSchema>;

// ===========================================================================
// 労務費基準マスタ・乖離率判定 (ロードマップ #16-20 / migration 015 / api v1 labor_wage)
// ===========================================================================

export const laborWorkTypeEnum = z.enum([
  "土木",
  "とび・土工",
  "舗装",
  "解体",
  "鉄筋",
  "コンクリート",
  "その他",
]);
export type LaborWorkType = z.infer<typeof laborWorkTypeEnum>;

export const laborWageStandardSchema = z.object({
  id: idSchema,
  work_type: laborWorkTypeEnum.or(z.string()),
  prefecture: z.string().nullable().optional(),
  amount_jpy: z.number().int(),
  amount_unit: z.string(),
  effective_from: dateSchema,
  effective_to: dateSchema.nullable().optional(),
  source_ref: z.string().nullable().optional(),
});
export type LaborWageStandard = z.infer<typeof laborWageStandardSchema>;

export const laborWageStandardCreateSchema = z.object({
  work_type: laborWorkTypeEnum,
  amount_jpy: z.number().int().min(0),
  prefecture: z.string().max(16).nullish(),
  effective_from: dateSchema,
  effective_to: dateSchema.nullish(),
  amount_unit: z.string().max(16).default("日"),
  source_ref: z.string().max(512).nullish(),
});
export type LaborWageStandardCreate = z.infer<typeof laborWageStandardCreateSchema>;

/** #20 乖離率判定結果（#21 ダンピング深刻度を含む） */
export const laborWageDiscrepancySchema = z.object({
  work_type: laborWorkTypeEnum.or(z.string()),
  prefecture: z.string().nullable().optional(),
  standard_day_jpy: z.number().int(),
  amount_unit: z.string(),
  effective_from: dateSchema,
  source_ref: z.string().nullable().optional(),
  quote_day_jpy: z.number().int(),
  ratio: z.number(),
  shortage_rate: z.number(),
  status: z.enum(["ok", "below"]).or(z.string()),
  severity: z.enum(["none", "watch", "warning", "critical"]).or(z.string()).default("none"),
  dumping: z.boolean().default(false),
});
export type LaborWageDiscrepancy = z.infer<typeof laborWageDiscrepancySchema>;

// ===========================================================================
// 労務費価格協議・乖離確認 (ロードマップ #21/#23/#24 / migration 016)
// ===========================================================================

export const consultationDirectionEnum = z.enum([
  "from_subcontractor",
  "to_subcontractor",
]);
export type ConsultationDirection = z.infer<typeof consultationDirectionEnum>;

export const consultationStatusEnum = z.enum(["open", "responded", "cancelled"]);
export type ConsultationStatus = z.infer<typeof consultationStatusEnum>;

export const dumpingSeverityEnum = z.enum([
  "none",
  "watch",
  "warning",
  "critical",
]);
export type DumpingSeverity = z.infer<typeof dumpingSeverityEnum>;

/** 価格協議ログ 1 件（#24） */
export const priceConsultationLogSchema = z.object({
  id: idSchema,
  log_no: z.string(),
  direction: consultationDirectionEnum.or(z.string()),
  status: consultationStatusEnum.or(z.string()),
  contract_id: idSchema.nullable().optional(),
  work_type: laborWorkTypeEnum.or(z.string()),
  prefecture: z.string().nullable().optional(),
  quote_day_jpy: z.number().int().nullable().optional(),
  summary: z.string(),
  request_detail: z.string().nullable().optional(),
  requested_at: dateSchema.nullable().optional(),
  standard_day_jpy: z.number().int().nullable().optional(),
  ratio: z.number().nullable().optional(),
  shortage_rate: z.number().nullable().optional(),
  severity: dumpingSeverityEnum.or(z.string()).nullable().optional(),
  effective_from: dateSchema.nullable().optional(),
  source_ref: z.string().nullable().optional(),
  responded_at: datetimeSchema.nullable().optional(),
  response_summary: z.string().nullable().optional(),
  responded_by: idSchema.nullable().optional(),
  cancel_reason: z.string().nullable().optional(),
  created_by: idSchema.nullable().optional(),
  created_at: datetimeSchema,
  updated_at: datetimeSchema,
});
export type PriceConsultationLog = z.infer<typeof priceConsultationLogSchema>;

export const priceConsultationCreateSchema = z.object({
  direction: consultationDirectionEnum,
  contract_id: idSchema.nullish(),
  work_type: z.string().min(1).max(64),
  prefecture: z.string().max(16).nullish(),
  quote_day_jpy: z.number().int().min(0).nullish(),
  summary: z.string().min(1).max(256),
  request_detail: z.string().max(8000).nullish(),
  requested_at: dateSchema.nullish(),
});
export type PriceConsultationCreate = z.infer<typeof priceConsultationCreateSchema>;

// ===========================================================================
// 標準工期マスタ・短工期判定 (ロードマップ #22 / migration 017)
// ===========================================================================

/** 標準工期マスタ 1 行（工種 × 請負金額帯 × 適用期間） */
export const standardWorkDurationSchema = z.object({
  id: idSchema,
  work_type: laborWorkTypeEnum.or(z.string()),
  prefecture: z.string().nullable().optional(),
  amount_min_jpy: z.number().int().min(0),
  amount_max_jpy: z.number().int().nullable().optional(),
  standard_days: z.number().int().min(1),
  effective_from: dateSchema,
  effective_to: dateSchema.nullable().optional(),
  source_ref: z.string().nullable().optional(),
});
export type StandardWorkDuration = z.infer<typeof standardWorkDurationSchema>;

export const standardWorkDurationCreateSchema = z.object({
  work_type: z.string().min(1).max(64),
  prefecture: z.string().max(16).nullish(),
  amount_min_jpy: z.number().int().min(0),
  amount_max_jpy: z.number().int().min(0).nullish(),
  standard_days: z.number().int().min(1),
  effective_from: dateSchema,
  effective_to: dateSchema.nullish(),
  source_ref: z.string().max(512).nullish(),
});
export type StandardWorkDurationCreate = z.infer<typeof standardWorkDurationCreateSchema>;

/** #22 短工期判定結果 */
export const shortDurationCheckSchema = z.object({
  work_type: laborWorkTypeEnum.or(z.string()),
  prefecture: z.string().nullable().optional(),
  amount_min_jpy: z.number().int(),
  amount_max_jpy: z.number().int().nullable().optional(),
  standard_days: z.number().int(),
  planned_days: z.number().int(),
  ratio: z.number(),
  shorten_rate: z.number(),
  status: z.enum(["ok", "short"]).or(z.string()),
  severity: dumpingSeverityEnum.or(z.string()),
  effective_from: dateSchema,
  source_ref: z.string().nullable().optional(),
});
export type ShortDurationCheck = z.infer<typeof shortDurationCheckSchema>;

// ===========================================================================
// 価格転嫁シミュレータ (ロードマップ #25/#26)
// ===========================================================================

export const priceSimulatorInSchema = z.object({
  contract_amount_jpy: z.number().int().min(0),
  labor_cost_jpy: z.number().int().min(0),
  material_cost_jpy: z.number().int().min(0),
  labor_change_rate: z.number().min(-1),
  material_change_rate: z.number().min(-1),
  pass_through_rate: z.number().min(0).max(1),
});
export type PriceSimulatorIn = z.infer<typeof priceSimulatorInSchema>;

export const priceSimulatorOutSchema = z.object({
  contract_amount_jpy: z.number().int(),
  labor_cost_jpy: z.number().int(),
  material_cost_jpy: z.number().int(),
  labor_change_rate: z.number(),
  material_change_rate: z.number(),
  pass_through_rate: z.number(),
  labor_delta_jpy: z.number().int(),
  material_delta_jpy: z.number().int(),
  total_delta_jpy: z.number().int(),
  pass_through_amount_jpy: z.number().int(),
  adjusted_amount_jpy: z.number().int(),
  direction: z.enum(["up", "down", "flat"]).or(z.string()),
});
export type PriceSimulatorOut = z.infer<typeof priceSimulatorOutSchema>;

// ===========================================================================
// 公共工事特化 (ロードマップ #41-#43・#54-#57・#60 / migration 018)
// ===========================================================================

export const agencyTypeEnum = z.enum([
  "national",
  "prefectural",
  "municipal",
  "public_corp",
  "other",
]);
export type AgencyType = z.infer<typeof agencyTypeEnum>;

export const ownerNotificationTypeEnum = z.enum([
  "design_change",
  "delay",
  "suspension",
  "claim",
  "completion",
  "other",
]);
export type OwnerNotificationType = z.infer<typeof ownerNotificationTypeEnum>;

export const ownerNotificationStatusEnum = z.enum([
  "open",
  "notified",
  "cancelled",
]);
export type OwnerNotificationStatus = z.infer<typeof ownerNotificationStatusEnum>;

export const publicWorksConsultationTypeEnum = z.enum([
  "extension_of_time",
  "design_change",
  "price_slide",
  "suspension",
  "other",
]);
export type PublicWorksConsultationType = z.infer<
  typeof publicWorksConsultationTypeEnum
>;

export const publicWorksConsultationStatusEnum = z.enum([
  "open",
  "responded",
  "cancelled",
]);
export type PublicWorksConsultationStatus = z.infer<
  typeof publicWorksConsultationStatusEnum
>;

/** #41/#42 発注機関マスタ＋機関別契約条件 */
export const contractingAgencySchema = z.object({
  id: idSchema,
  code: z.string(),
  name: z.string(),
  agency_type: agencyTypeEnum.or(z.string()),
  prefecture: z.string().nullable().optional(),
  contact_email: z.string().nullable().optional(),
  phone: z.string().nullable().optional(),
  payment_deadline_days: z.number().int().nullable().optional(),
  advance_payment_ratio: z.number().nullable().optional(),
  warranty_period_months: z.number().int().nullable().optional(),
  requires_slide_clause: z.boolean(),
  notes: z.string().nullable().optional(),
  is_active: z.boolean(),
  created_at: datetimeSchema,
  updated_at: datetimeSchema,
});
export type ContractingAgency = z.infer<typeof contractingAgencySchema>;

export const contractingAgencyCreateSchema = z.object({
  code: z.string().min(1).max(64),
  name: z.string().min(1).max(256),
  agency_type: agencyTypeEnum,
  prefecture: z.string().max(16).nullish(),
  contact_email: z.string().max(256).nullish(),
  phone: z.string().max(64).nullish(),
  payment_deadline_days: z.number().int().min(1).nullish(),
  advance_payment_ratio: z.number().min(0).max(1).nullish(),
  warranty_period_months: z.number().int().min(0).nullish(),
  requires_slide_clause: z.boolean().default(false),
  notes: z.string().max(4000).nullish(),
});
export type ContractingAgencyCreate = z.infer<typeof contractingAgencyCreateSchema>;

/** #54 発注者通知 */
export const ownerNotificationSchema = z.object({
  id: idSchema,
  notification_no: z.string(),
  contract_id: idSchema.nullable().optional(),
  agency_id: idSchema.nullable().optional(),
  notification_type: ownerNotificationTypeEnum.or(z.string()),
  status: ownerNotificationStatusEnum.or(z.string()),
  title: z.string(),
  detail: z.string().nullable().optional(),
  due_date: dateSchema.nullable().optional(),
  notified_at: datetimeSchema.nullable().optional(),
  notified_by: idSchema.nullable().optional(),
  cancel_reason: z.string().nullable().optional(),
  created_by: idSchema.nullable().optional(),
  created_at: datetimeSchema,
  updated_at: datetimeSchema,
});
export type OwnerNotification = z.infer<typeof ownerNotificationSchema>;

export const ownerNotificationCreateSchema = z.object({
  notification_type: z.string().min(1).max(32),
  title: z.string().min(1).max(256),
  contract_id: idSchema.nullish(),
  agency_id: idSchema.nullish(),
  detail: z.string().max(8000).nullish(),
  due_date: dateSchema.nullish(),
});
export type OwnerNotificationCreate = z.infer<typeof ownerNotificationCreateSchema>;

/** #55/#56/#57 発注者との協議 */
export const publicWorksConsultationSchema = z.object({
  id: idSchema,
  consultation_no: z.string(),
  contract_id: idSchema.nullable().optional(),
  agency_id: idSchema.nullable().optional(),
  consultation_type: publicWorksConsultationTypeEnum.or(z.string()),
  status: publicWorksConsultationStatusEnum.or(z.string()),
  title: z.string(),
  detail: z.string().nullable().optional(),
  requested_at: dateSchema.nullable().optional(),
  due_date: dateSchema.nullable().optional(),
  claimed_days: z.number().int().nullable().optional(),
  claimed_amount_jpy: z.number().int().nullable().optional(),
  resolved_days: z.number().int().nullable().optional(),
  resolved_amount_jpy: z.number().int().nullable().optional(),
  responded_at: datetimeSchema.nullable().optional(),
  response_note: z.string().nullable().optional(),
  cancel_reason: z.string().nullable().optional(),
  created_by: idSchema.nullable().optional(),
  created_at: datetimeSchema,
  updated_at: datetimeSchema,
});
export type PublicWorksConsultation = z.infer<typeof publicWorksConsultationSchema>;

export const publicWorksConsultationCreateSchema = z.object({
  consultation_type: z.string().min(1).max(32),
  title: z.string().min(1).max(256),
  contract_id: idSchema.nullish(),
  agency_id: idSchema.nullish(),
  detail: z.string().max(8000).nullish(),
  requested_at: dateSchema.nullish(),
  due_date: dateSchema.nullish(),
  claimed_days: z.number().int().min(1).nullish(),
  claimed_amount_jpy: z.number().int().min(0).nullish(),
});
export type PublicWorksConsultationCreate = z.infer<
  typeof publicWorksConsultationCreateSchema
>;

/** #43 標準請負約款差分チェック結果 */
export const standardClauseCheckSchema = z.object({
  contract_id: idSchema,
  contract_no: z.string().nullable().optional(),
  title: z.string().nullable().optional(),
  total_categories: z.number().int(),
  covered_categories: z.number().int(),
  missing_categories: z.number().int(),
  categories: z
    .array(
      z.object({
        category: z.string(),
        covered: z.boolean(),
        matched_clause_seqs: z.array(z.number().int()).default([]),
      })
    )
    .default([]),
});
export type StandardClauseCheck = z.infer<typeof standardClauseCheckSchema>;

/** #60 公共工事ダッシュボード */
export const publicWorksDashboardSchema = z.object({
  agencies_active: z.number().int(),
  notifications_open: z.number().int(),
  notifications_overdue: z.number().int(),
  consultations_open: z.number().int(),
  consultations_by_type: z.record(z.string(), z.number().int()).default({}),
});
export type PublicWorksDashboard = z.infer<typeof publicWorksDashboardSchema>;
