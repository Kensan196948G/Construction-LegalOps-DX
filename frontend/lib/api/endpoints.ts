/**
 * API endpoint functions — Construction-LegalOps-DX
 *
 * 各 router (auth / users / contracts / reviews / workflows / risks / compliance
 *  / templates / knowledge / audit_logs / uploads / notifications / dashboard)
 * を関数として export する。
 *
 * - レスポンスは zod スキーマで parse して型安全に返す。
 * - エラーは client.ts の response interceptor で ApiError に正規化される。
 */

import type { AxiosRequestConfig } from "axios";
import { z } from "zod";

import { apiClient, withIdempotencyKey } from "./client";
import {
  // envelopes
  apiResponse,
  paginatedSchema,
  // schemas
  accessControlEntrySchema,
  aiProviderConfigSchema,
  aiSettingsSchema,
  applicableLawSchema,
  attachmentSchema,
  auditLogSchema,
  auditVerifyResultSchema,
  changeOrderEvidenceSchema,
  changeOrderImpactSchema,
  changeOrderSchema,
  clauseSchema,
  clauseLibrarySchema,
  complianceChecklistSchema,
  complianceCheckResultSchema,
  complianceRunSchema,
  connectionTestSchema,
  contractSchema,
  contractCreateSchema,
  contractUpdateSchema,
  dashboardSummarySchema,
  dashboardTrendsSchema,
  disputeDetailSchema,
  disputeEvidenceSchema,
  disputeExposureSchema,
  disputeSchema,
  disputeTimelineEventSchema,
  evidenceHitSchema,
  healthSchema,
  knowledgeArticleSchema,
  legalHoldSchema,
  legalReviewSchema,
  notificationSchema,
  partnerSchema,
  partnerSummarySchema,
  paymentComplianceSchema,
  retentionRuleSchema,
  reviewCreateSchema,
  riskHeatmapSchema,
  riskItemSchema,
  riskUpdateSchema,
  templateSchema,
  userSchema,
  userSyncJobSchema,
  versionSchema,
  workflowInstanceSchema,
  workflowSchema,
  workflowStepSchema,
  idSchema,
  type AiProvider,
  type AiSettingsUpdate,
  type ChangeOrderCreate,
  type ContractCreate,
  type ContractUpdate,
  type Dispute,
  type DisputeEvidence,
  type Paginated,
  type Partner,
  type PaymentFinding,
  type ReviewCreate,
  type RiskUpdate,
} from "./schemas";

// ---------------------------------------------------------------------------
// Shared types
// ---------------------------------------------------------------------------

export interface ListParams {
  page?: number;
  page_size?: number;
  q?: string;
  sort?: string;
  [key: string]: unknown;
}

function buildParams(params?: ListParams): Record<string, unknown> | undefined {
  if (!params) return undefined;
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    out[k] = v;
  }
  return Object.keys(out).length ? out : undefined;
}

/** schema を parse して返すヘルパ */
async function getParsed<T extends z.ZodTypeAny>(
  schema: T,
  url: string,
  config?: AxiosRequestConfig,
): Promise<z.infer<T>> {
  const res = await apiClient.get(url, config);
  return schema.parse(res.data) as z.infer<T>;
}

async function postParsed<T extends z.ZodTypeAny>(
  schema: T,
  url: string,
  body?: unknown,
  config?: AxiosRequestConfig,
): Promise<z.infer<T>> {
  const res = await apiClient.post(url, body, config);
  return schema.parse(res.data) as z.infer<T>;
}

async function patchParsed<T extends z.ZodTypeAny>(
  schema: T,
  url: string,
  body?: unknown,
  config?: AxiosRequestConfig,
): Promise<z.infer<T>> {
  const res = await apiClient.patch(url, body, config);
  return schema.parse(res.data) as z.infer<T>;
}

async function putParsed<T extends z.ZodTypeAny>(
  schema: T,
  url: string,
  body?: unknown,
  config?: AxiosRequestConfig,
): Promise<z.infer<T>> {
  const res = await apiClient.put(url, body, config);
  return schema.parse(res.data) as z.infer<T>;
}

// ===========================================================================
// 1. Auth
// ===========================================================================

export const authApi = {
  /** 現在のログインユーザー */
  me: () => getParsed(apiResponse(userSchema), "/auth/me"),

  /** サインアウト (Cookie 破棄 + Entra ID end_session) */
  logout: () => apiClient.post<void>("/auth/sso/logout").then(() => undefined),
};

// ===========================================================================
// 2. Users
// ===========================================================================

export interface UserListParams extends ListParams {
  role?: string;
  department_id?: number | string;
  is_active?: boolean;
}

export const usersApi = {
  list: (params?: UserListParams) =>
    getParsed(paginatedSchema(userSchema), "/users", { params: buildParams(params) }),

  get: (id: number | string) => getParsed(apiResponse(userSchema), `/users/${id}`),

  update: (
    id: number | string,
    data: Partial<{
      role: string;
      department_id: number | string;
      is_active: boolean;
      version: number;
    }>,
  ) => patchParsed(apiResponse(userSchema), `/users/${id}`, data),

  /** Microsoft Graph 同期 (202 Accepted) */
  sync: () =>
    postParsed(apiResponse(userSyncJobSchema), "/users/sync"),
};

// ===========================================================================
// 3. Contracts
// ===========================================================================

export interface ContractListParams extends ListParams {
  status?: string;
  contract_type?: string;
  department_id?: number | string;
  from?: string;
  to?: string;
  confidentiality?: string;
}

export const contractsApi = {
  list: (params?: ContractListParams) =>
    getParsed(paginatedSchema(contractSchema), "/contracts", {
      params: buildParams(params),
    }),

  get: (id: number | string) => getParsed(apiResponse(contractSchema), `/contracts/${id}`),

  create: (data: ContractCreate, opts?: { idempotencyKey?: string }) =>
    postParsed(
      apiResponse(contractSchema),
      "/contracts",
      contractCreateSchema.parse(data),
      withIdempotencyKey({}, opts?.idempotencyKey),
    ),

  update: (id: number | string, data: ContractUpdate) =>
    patchParsed(
      apiResponse(contractSchema),
      `/contracts/${id}`,
      contractUpdateSchema.parse(data),
    ),

  delete: (id: number | string) =>
    apiClient.delete(`/contracts/${id}`).then(() => undefined),

  submit: (id: number | string) =>
    postParsed(apiResponse(contractSchema), `/contracts/${id}/submit`),

  clauses: (id: number | string) =>
    getParsed(z.array(clauseSchema), `/contracts/${id}/clauses`),

  auditTrail: (id: number | string, params?: { page?: number; size?: number }) =>
    getParsed(paginatedSchema(auditLogSchema), `/contracts/${id}/audit-trail`, {
      params: buildParams(params),
    }),

  workflowSteps: (instanceId: number | string) =>
    getParsed(z.array(workflowStepSchema), `/workflows/${instanceId}/steps`),
};

// ===========================================================================
// 4. Reviews
// ===========================================================================

export interface ReviewListParams extends ListParams {
  contract_id?: number | string;
  status?: string;
}

export const reviewsApi = {
  list: (params?: ReviewListParams) =>
    getParsed(paginatedSchema(legalReviewSchema), "/reviews", {
      params: buildParams(params),
    }),

  get: (id: number | string) =>
    getParsed(apiResponse(legalReviewSchema), `/reviews/${id}`),

  /** AI レビューを起動 (202 Accepted) */
  startForContract: (
    contractId: number | string,
    data: ReviewCreate,
    opts?: { idempotencyKey?: string },
  ) =>
    postParsed(
      apiResponse(legalReviewSchema),
      `/contracts/${contractId}/reviews`,
      reviewCreateSchema.parse(data),
      withIdempotencyKey({}, opts?.idempotencyKey),
    ),

  accept: (id: number | string) =>
    postParsed(apiResponse(legalReviewSchema), `/reviews/${id}/accept`),

  reject: (id: number | string, reason: string) =>
    postParsed(apiResponse(legalReviewSchema), `/reviews/${id}/reject`, { reason }),
};

// ===========================================================================
// 5. Workflows
// ===========================================================================

export const workflowsApi = {
  list: (params?: ListParams) =>
    getParsed(paginatedSchema(workflowSchema), "/workflows", {
      params: buildParams(params),
    }),

  /** ワークフロー定義を取得 (GET /workflows/{id}) */
  get: (id: number | string) =>
    getParsed(apiResponse(workflowSchema), `/workflows/${id}`),

  /** ワークフロー実行インスタンスを取得。instance_id = contract_id */
  getInstance: (instanceId: number | string) =>
    getParsed(apiResponse(workflowInstanceSchema), `/workflows/${instanceId}`),

  create: (data: {
    code: string;
    name: string;
    contract_type?: string;
    definition: { steps: unknown[] };
  }) => postParsed(apiResponse(workflowSchema), "/workflows", data),

  update: (id: number | string, data: Partial<{ name: string; is_active: boolean }>) =>
    patchParsed(apiResponse(workflowSchema), `/workflows/${id}`, data),

  delete: (id: number | string) =>
    apiClient.delete(`/workflows/${id}`).then(() => undefined),

  // --- step actions ---
  approveStep: (stepId: number | string, comment?: string) =>
    postParsed(apiResponse(workflowStepSchema), `/workflow-steps/${stepId}/approve`, {
      comment,
    }),

  rejectStep: (stepId: number | string, comment: string) =>
    postParsed(apiResponse(workflowStepSchema), `/workflow-steps/${stepId}/reject`, {
      comment,
    }),

  sendBackStep: (stepId: number | string, toSeq: number, comment?: string) =>
    postParsed(apiResponse(workflowStepSchema), `/workflow-steps/${stepId}/send-back`, {
      to_seq: toSeq,
      comment,
    }),

  delegateStep: (stepId: number | string, toUserId: number | string, comment?: string) =>
    postParsed(apiResponse(workflowStepSchema), `/workflow-steps/${stepId}/delegate`, {
      to_user_id: toUserId,
      comment,
    }),
};

// ===========================================================================
// 6. Risks
// ===========================================================================

export interface RiskListParams extends ListParams {
  severity?: string;
  status?: string;
  contract_id?: number | string;
  owner_id?: number | string;
}

export const risksApi = {
  list: (params?: RiskListParams) =>
    getParsed(paginatedSchema(riskItemSchema), "/risks", { params: buildParams(params) }),

  get: (id: number | string) => getParsed(apiResponse(riskItemSchema), `/risks/${id}`),

  update: (id: number | string, data: RiskUpdate) =>
    patchParsed(apiResponse(riskItemSchema), `/risks/${id}`, riskUpdateSchema.parse(data)),

  heatmap: () => getParsed(apiResponse(riskHeatmapSchema), "/risks/heatmap"),
};

// ===========================================================================
// 7. Compliance
// ===========================================================================

export const complianceApi = {
  checklists: (params?: ListParams) =>
    getParsed(z.array(complianceChecklistSchema), "/compliance/checklists", {
      params: buildParams(params),
    }),

  /** 契約に対するチェックリスト適用 (202 Accepted; inline completed job handle) */
  runForContract: (contractId: number | string, checklistCodes?: string[]) =>
    postParsed(
      apiResponse(complianceRunSchema),
      `/compliance/checks/${contractId}/run`,
      undefined,
      { params: checklistCodes?.length ? { checklist_codes: checklistCodes } : undefined },
    ),

  getResult: (contractId: number | string, checklistCodes?: string[]) =>
    getParsed(apiResponse(complianceCheckResultSchema), `/compliance/checks/${contractId}`, {
      params: checklistCodes?.length ? { checklist_codes: checklistCodes } : undefined,
    }),
};

// ===========================================================================
// 8. Templates / Clause library
// ===========================================================================

export const templatesApi = {
  list: (params?: ListParams) =>
    getParsed(paginatedSchema(templateSchema), "/templates", {
      params: buildParams(params),
    }),

  get: (id: number | string) =>
    getParsed(apiResponse(templateSchema), `/templates/${id}`),

  create: (data: { code: string; name: string; contract_type?: string; body?: string }) =>
    postParsed(apiResponse(templateSchema), "/templates", data),

  update: (id: number | string, data: Partial<{ name: string; body: string; is_active: boolean }>) =>
    patchParsed(apiResponse(templateSchema), `/templates/${id}`, data),

  delete: (id: number | string) =>
    apiClient.delete(`/templates/${id}`).then(() => undefined),

  // Clause library is part of templates domain
  clauseLibraryList: (params?: ListParams & { category?: string; tag?: string; recommendation?: string }) =>
    getParsed(paginatedSchema(clauseLibrarySchema), "/clauses-library", {
      params: buildParams(params),
    }),

  clauseLibraryCreate: (data: { title: string; body: string; category?: string }) =>
    postParsed(apiResponse(clauseLibrarySchema), "/clauses-library", data),
};

// ===========================================================================
// 9. Knowledge
// ===========================================================================

export const knowledgeApi = {
  list: (params?: ListParams & { tag?: string }) =>
    getParsed(paginatedSchema(knowledgeArticleSchema), "/knowledge", {
      params: buildParams(params),
    }),

  get: (id: number | string) =>
    getParsed(apiResponse(knowledgeArticleSchema), `/knowledge/${id}`),

  create: (data: { title: string; body: string; tags?: string[] }) =>
    postParsed(apiResponse(knowledgeArticleSchema), "/knowledge", data),

  update: (id: number | string, data: Partial<{ title: string; body: string; tags: string[] }>) =>
    patchParsed(apiResponse(knowledgeArticleSchema), `/knowledge/${id}`, data),

  delete: (id: number | string) =>
    apiClient.delete(`/knowledge/${id}`).then(() => undefined),
};

// ===========================================================================
// 10. Audit logs
// ===========================================================================

export interface AuditLogListParams extends ListParams {
  target_type?: string;
  target_id?: number | string;
  action?: string;
  actor_id?: number | string;
  from?: string;
  to?: string;
}

export const auditLogsApi = {
  list: (params?: AuditLogListParams) =>
    getParsed(paginatedSchema(auditLogSchema), "/audit-logs", {
      params: buildParams(params),
    }),

  verify: () => postParsed(apiResponse(auditVerifyResultSchema), "/audit-logs/verify"),

  /** CSV エクスポート — Blob で返す */
  exportCsv: async (params?: AuditLogListParams): Promise<Blob> => {
    const res = await apiClient.get("/audit-logs/export", {
      params: buildParams(params),
      responseType: "blob",
    });
    return res.data as Blob;
  },
};

// ===========================================================================
// 11. Uploads
// ===========================================================================

export interface UploadFileParams {
  file: File | Blob;
  filename?: string;
  contract_id?: number | string;
  is_primary?: boolean;
}

export const uploadsApi = {
  upload: async (params: UploadFileParams, opts?: { idempotencyKey?: string }) => {
    const form = new FormData();
    form.append(
      "file",
      params.file,
      params.filename ?? (params.file instanceof File ? params.file.name : "upload.bin"),
    );
    if (params.contract_id !== undefined) {
      form.append("contract_id", String(params.contract_id));
    }
    if (params.is_primary !== undefined) {
      form.append("is_primary", String(params.is_primary));
    }
    const res = await apiClient.post("/uploads", form, {
      ...withIdempotencyKey({}, opts?.idempotencyKey),
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });
    return apiResponse(attachmentSchema).parse(res.data);
  },

  /** ダウンロード用 302 URL を取得 (axios の追従を許容) */
  downloadUrl: (id: number | string) => `/uploads/${id}/download`,

  delete: (id: number | string) =>
    apiClient.delete(`/uploads/${id}`).then(() => undefined),
};

// ===========================================================================
// 12. Notifications
// ===========================================================================

export interface NotificationListParams extends ListParams {
  status?: string;
  channel?: string;
}

export const notificationsApi = {
  list: (params?: NotificationListParams) =>
    getParsed(paginatedSchema(notificationSchema), "/notifications", {
      params: buildParams(params),
    }),

  markAsRead: (id: number | string) =>
    apiClient.post(`/notifications/${id}/read`).then(() => undefined),

  /** バッジ用カウント取得 */
  unreadCount: async (): Promise<number> => {
    const result = await notificationsApi.list({ status: "unread", page: 1, page_size: 1 });
    return (result as Paginated<unknown>).total;
  },
};

// ===========================================================================
// 13. Dashboard
// ===========================================================================

export const dashboardApi = {
  summary: (params?: { department_id?: number | string }) =>
    getParsed(dashboardSummarySchema, "/dashboard/summary", {
      params: buildParams(params),
    }),

  trends: (params?: { interval?: "week" | "month"; weeks?: number; department_id?: number | string }) =>
    getParsed(dashboardTrendsSchema, "/dashboard/trends", {
      params: buildParams(params),
    }),
};

// ===========================================================================
// AI 設定（管理者専用・ハイブリッド AI レビュー基盤・Issue #28）
// ===========================================================================

export const settingsApi = {
  /** 両プロバイダのマスク済み設定を取得（平文キーは返らない） */
  getAiSettings: () => getParsed(aiSettingsSchema, "/admin/ai-settings"),

  /** APIキー・モデル・有効化を保存（「保存・設定」）。冪等キーは interceptor が自動付与 */
  updateAiProvider: (provider: AiProvider, body: AiSettingsUpdate) =>
    putParsed(aiProviderConfigSchema, `/admin/ai-settings/${provider}`, body),

  /** 保存済みキーで疎通確認（「設定テスト」）。機密本文は送信しない */
  testAiProvider: (provider: AiProvider) =>
    postParsed(connectionTestSchema, `/admin/ai-settings/${provider}/test`),
};

// ===========================================================================
// 14. 変更契約・クレーム管理
// ===========================================================================

export interface ChangeOrderListParams extends ListParams {
  contract_id?: number | string;
  status?: string;
}

export const changeOrdersApi = {
  list: (params?: ChangeOrderListParams) =>
    getParsed(paginatedSchema(changeOrderSchema), "/change-orders", {
      params: buildParams(params),
    }),

  create: (contractId: number | string, data: Partial<ChangeOrderCreate>) =>
    postParsed(changeOrderSchema, "/change-orders", data, {
      params: { contract_id: contractId },
    }),

  update: (id: number | string, data: Partial<ChangeOrderCreate>) =>
    patchParsed(changeOrderSchema, `/change-orders/${id}`, data),

  evidence: (id: number | string) =>
    getParsed(z.array(changeOrderEvidenceSchema), `/change-orders/${id}/evidence`),

  addEvidence: (
    id: number | string,
    data: Partial<{
      evidence_type: string;
      description?: string;
      occurred_at?: string;
      attachment_id?: number | string;
    }>,
  ) => postParsed(changeOrderEvidenceSchema, `/change-orders/${id}/evidence`, data),

  impact: (contractId: number | string) =>
    getParsed(changeOrderImpactSchema, `/change-orders/impact/${contractId}`),
};

// ===========================================================================
// 15. 協力会社コンプライアンス台帳
// ===========================================================================

export interface PartnerListParams extends ListParams {
  partner_type?: string;
  risk_level?: string;
}

export const partnersApi = {
  list: (params?: PartnerListParams) =>
    getParsed(paginatedSchema(partnerSchema), "/partners", {
      params: buildParams(params),
    }),

  summary: () => getParsed(partnerSummarySchema, "/partners/summary"),

  create: (data: Partial<Partner>) => postParsed(partnerSchema, "/partners", data),

  update: (id: number | string, data: Partial<Partner>) =>
    patchParsed(partnerSchema, `/partners/${id}`, data),
};

// ===========================================================================
// 16. 紛争・事故・債権管理
// ===========================================================================

export interface DisputeListParams extends ListParams {
  status?: string;
  dispute_type?: string;
}

export const disputesApi = {
  list: (params?: DisputeListParams) =>
    getParsed(paginatedSchema(disputeSchema), "/disputes", {
      params: buildParams(params),
    }),

  exposure: () => getParsed(disputeExposureSchema, "/disputes/exposure"),

  get: (id: number | string) => getParsed(disputeDetailSchema, `/disputes/${id}`),

  create: (data: Partial<Dispute>) => postParsed(disputeSchema, "/disputes", data),

  update: (id: number | string, data: Partial<Dispute>) =>
    patchParsed(disputeSchema, `/disputes/${id}`, data),

  addTimeline: (
    id: number | string,
    data: Partial<{
      event_type: string;
      occurred_at?: string;
      description?: string;
    }>,
  ) => postParsed(disputeTimelineEventSchema, `/disputes/${id}/timeline`, data),

  addEvidence: (
    id: number | string,
    data: Partial<DisputeEvidence>,
  ) => postParsed(disputeEvidenceSchema, `/disputes/${id}/evidence`, data),
};

// ===========================================================================
// 17. 支払・出来高・検収コンプライアンス
// ===========================================================================

export const paymentComplianceApi = {
  check: (contractId: number | string) =>
    getParsed(paymentComplianceSchema, `/contracts/${contractId}/payment-compliance`),

  findings: (contractId: number | string) =>
    getParsed(paymentComplianceSchema, `/contracts/${contractId}/payment-compliance`).then(
      (r) => r.findings as PaymentFinding[],
    ),
};

// ===========================================================================
// 18. ガバナンス（P0-6）・法務 AI（一次情報検索）
// ===========================================================================

export const governanceApi = {
  /** 案件単位 ACL */
  acl: (contractId: number | string) =>
    getParsed(z.array(accessControlEntrySchema), `/contracts/${contractId}/access-control`),

  grant: (contractId: number | string, data: Record<string, unknown>) =>
    postParsed(accessControlEntrySchema, `/contracts/${contractId}/access-control`, data),

  revoke: (contractId: number | string, entryId: number | string) =>
    apiClient.delete(`/contracts/${contractId}/access-control/${entryId}`).then(() => undefined),

  /** リーガルホールド */
  legalHolds: (params?: { active?: boolean }) =>
    getParsed(z.array(legalHoldSchema), "/legal-holds", {
      params: buildParams(params),
    }),

  /** 保持期間 */
  retentionRules: () => getParsed(z.array(retentionRuleSchema), "/retention"),
};

export const legalAiApi = {
  /** 適用法令自動判定（POST /compliance/applicable-laws） */
  applicableLaws: (data: Record<string, unknown>) =>
    postParsed(
      z.object({
        contract_id: idSchema.nullable().optional(),
        contract_type: z.string(),
        laws: z.array(applicableLawSchema).default([]),
        applied: z.array(applicableLawSchema).default([]),
      }),
      "/compliance/applicable-laws",
      data,
    ),

  /** 一次情報限定根拠検索（POST /ai/evidence） */
  evidence: (data: { query: string; max_results?: number }) =>
    postParsed(
      z.object({
        query: z.string(),
        hits: z.array(evidenceHitSchema).default([]),
        citation_verification: z.record(z.string(), z.unknown()).default({}),
      }),
      "/ai/evidence",
      data,
    ),
};

// ===========================================================================
// Meta / Health
// ===========================================================================

export const metaApi = {
  health: () => getParsed(healthSchema, "/healthz"),
  ready: () => getParsed(healthSchema, "/readyz"),
  version: () => getParsed(versionSchema, "/version"),
};

// ===========================================================================
// 単一エクスポート — まとめて参照したい場合
// ===========================================================================

export const api = {
  auth: authApi,
  users: usersApi,
  contracts: contractsApi,
  reviews: reviewsApi,
  workflows: workflowsApi,
  risks: risksApi,
  compliance: complianceApi,
  templates: templatesApi,
  knowledge: knowledgeApi,
  auditLogs: auditLogsApi,
  uploads: uploadsApi,
  notifications: notificationsApi,
  dashboard: dashboardApi,
  settings: settingsApi,
  changeOrders: changeOrdersApi,
  partners: partnersApi,
  disputes: disputesApi,
  payments: paymentComplianceApi,
  governance: governanceApi,
  legalAi: legalAiApi,
  meta: metaApi,
} as const;
