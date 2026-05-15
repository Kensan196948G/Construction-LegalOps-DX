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
 * Backend は `{ data, meta: { page, page_size, total } }` 形式を返す。
 * フロントは `{ page, size, total, items }` 形式に正規化する。
 */
export const paginationMetaSchema = z.object({
  page: z.number().int().nonnegative(),
  page_size: z.number().int().positive(),
  total: z.number().int().nonnegative(),
  request_id: z.string().optional(),
});
export type PaginationMeta = z.infer<typeof paginationMetaSchema>;

/**
 * ジェネリックなページングレスポンス。
 * - レスポンス受領後に変換して `{ page, size, total, items }` を返す。
 */
export function paginatedSchema<T extends z.ZodTypeAny>(item: T) {
  return z
    .object({
      data: z.array(item),
      meta: paginationMetaSchema,
    })
    .transform((raw) => ({
      page: raw.meta.page,
      size: raw.meta.page_size,
      total: raw.meta.total,
      items: raw.data,
    }));
}

/** 単一オブジェクトレスポンスのエンベロープ。 */
export function apiResponse<T extends z.ZodTypeAny>(inner: T) {
  return z
    .object({
      data: inner,
      meta: z
        .object({ request_id: z.string().optional() })
        .partial()
        .optional(),
    })
    .transform((r) => r.data);
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
  "請負",
  "業務委託",
  "売買",
  "賃貸借",
  "秘密保持",
  "覚書",
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
  due_at: datetimeSchema.optional().nullable(),
});
export type WorkflowStep = z.infer<typeof workflowStepSchema>;

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
  name: z.string(),
  contract_type: contractTypeEnum.or(z.string()).optional().nullable(),
  items: z.array(complianceChecklistItemSchema),
  is_active: z.boolean().default(true),
});
export type ComplianceChecklist = z.infer<typeof complianceChecklistSchema>;

export const complianceRunResultSchema = z.object({
  item_id: idSchema,
  passed: z.boolean(),
  note: z.string().optional(),
});
export const complianceRunSchema = z.object({
  id: idSchema,
  contract_id: idSchema,
  checklist_id: idSchema,
  status: z.enum(["queued", "running", "completed", "failed"]),
  results: z.array(complianceRunResultSchema).optional(),
  started_at: datetimeSchema.optional().nullable(),
  finished_at: datetimeSchema.optional().nullable(),
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
  recommendation: z.enum(["recommended", "neutral", "avoid"]).optional(),
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
// Dashboard
// ---------------------------------------------------------------------------

export const dashboardKpisSchema = z.object({
  total_contracts: z.number().int().nonnegative(),
  in_review: z.number().int().nonnegative(),
  pending_approval: z.number().int().nonnegative(),
  high_risk_open: z.number().int().nonnegative(),
  reviews_this_month: z.number().int().nonnegative(),
  avg_review_minutes: z.number().nonnegative().optional(),
});
export type DashboardKpis = z.infer<typeof dashboardKpisSchema>;

export const dashboardTimeseriesPointSchema = z.object({
  date: dateSchema,
  value: z.number(),
});
export const dashboardTimeseriesSchema = z.object({
  metric: z.string(),
  points: z.array(dashboardTimeseriesPointSchema),
});
export type DashboardTimeseries = z.infer<typeof dashboardTimeseriesSchema>;

// ---------------------------------------------------------------------------
// Health / Meta
// ---------------------------------------------------------------------------

export const healthSchema = z.object({ status: z.literal("ok") });
export const versionSchema = z.object({
  version: z.string(),
  commit: z.string().optional(),
});

// ===========================================================================
// 共通: Paginated 型
// ===========================================================================

export interface Paginated<T> {
  page: number;
  size: number;
  total: number;
  items: T[];
}
