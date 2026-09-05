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
  clauseNegotiationStateSchema,
  complianceChecklistSchema,
  complianceCheckResultSchema,
  complianceRunSchema,
  connectionTestSchema,
  contractSchema,
  contractDocumentSchema,
  contractCreateSchema,
  contractSearchHitSchema,
  contractUpdateSchema,
  counselLawyerCreateSchema,
  counselLawyerSchema,
  dashboardSummarySchema,
  dashboardTrendsSchema,
  disputeDetailSchema,
  disputeEvidenceSchema,
  disputeExposureSchema,
  disputeSchema,
  disputeTimelineEventSchema,
  engagementSchema,
  evidenceHitSchema,
  healthSchema,
  knowledgeArticleSchema,
  laborWageDiscrepancySchema,
  laborWageStandardCreateSchema,
  laborWageStandardSchema,
  lawFirmCreateSchema,
  lawFirmSchema,
  legalHoldSchema,
  legalReviewSchema,
  matterContractSchema,
  matterEventSchema,
  matterSchema,
  negotiationEventCreateSchema,
  negotiationEventSchema,
  notificationSchema,
  obligationCreateSchema,
  obligationSchema,
  partnerSchema,
  partnerSummarySchema,
  paymentComplianceSchema,
  priceConsultationCreateSchema,
  priceConsultationLogSchema,
  contractingAgencyCreateSchema,
  contractingAgencySchema,
  ownerNotificationCreateSchema,
  ownerNotificationSchema,
  publicWorksConsultationCreateSchema,
  publicWorksConsultationSchema,
  publicWorksDashboardSchema,
  standardClauseCheckSchema,
  jvAgreementSchema,
  jvCreateSchema,
  jvDashboardSchema,
  jvDisputeSchema,
  jvMemberCreateSchema,
  jvMemberSchema,
  jvSchema,
  jvSettlementSchema,
  partnerExpiryFlagsSchema,
  partnerReviewCreateSchema,
  partnerReviewSchema,
  partnerRiskScoreSchema,
  priceSimulatorInSchema,
  priceSimulatorOutSchema,
  renewalCheckSchema,
  shortDurationCheckSchema,
  standardWorkDurationCreateSchema,
  standardWorkDurationSchema,
  retentionRuleSchema,
  reviewCreateSchema,
  riskHeatmapSchema,
  riskItemSchema,
  riskUpdateSchema,
  signingEnvelopeCreateSchema,
  signingEnvelopeSchema,
  signingEventSchema,
  templateSchema,
  userSchema,
  userSyncJobSchema,
  versionSchema,
  workflowInstanceSchema,
  workflowApplicationSchema,
  workflowSchema,
  workflowStepSchema,
  idSchema,
  ipAssetCreateSchema,
  ipAssetSchema,
  ipAssetSyncResultSchema,
  ipDashboardSchema,
  ipDocumentSchema,
  ipWatchEventSchema,
  ipWatchTargetCreateSchema,
  ipWatchTargetSchema,
  ipWatchTargetSyncResultSchema,
  jpoStatusSchema,
  type AiProvider,
  type AiSettingsUpdate,
  type ChangeOrderCreate,
  type ContractCreate,
  type ContractUpdate,
  type Dispute,
  type DisputeEvidence,
  type IpAssetCreate,
  type IpWatchTargetCreate,
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

  documents: (id: number | string) =>
    getParsed(z.array(contractDocumentSchema), `/contracts/${id}/documents`),

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

  /** 稟議一覧（承認ワークフロー結合ビュー） */
  applications: (params?: ListParams & { status?: string }) =>
    getParsed(paginatedSchema(workflowApplicationSchema), "/workflows/applications", {
      params: buildParams(params),
    }),

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

  /** 全件既読（POST /notifications/read-all） */
  markAllAsRead: () =>
    apiClient
      .post("/notifications/read-all")
      .then((res) => res.data as { updated: number }),

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

  /** 一次情報限定根拠検索（GET /ai/evidence?q=...&limit=...） */
  evidence: (data: { query: string; limit?: number }) =>
    apiClient
      .get("/ai/evidence", {
        params: {
          q: data.query,
          limit: data.limit ?? 8,
        },
      })
      .then((res) =>
        z
          .object({
            query: z.string(),
            hits: z.array(evidenceHitSchema).default([]),
            citation_verification: z.record(z.string(), z.unknown()).default({}),
          })
          .parse(res.data),
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
// ===========================================================================
// 知財管理・競合ウォッチ・審査書類 (JPO 特許情報取得API)
// ===========================================================================

export interface IpAssetListParams extends ListParams {
  ip_type?: string;
  status?: string;
  watch_target_id?: number | string;
}

export const ipAssetsApi = {
  list: (params?: IpAssetListParams) =>
    getParsed(paginatedSchema(ipAssetSchema), "/ip-assets", {
      params: buildParams(params),
    }),

  get: (id: number | string) =>
    getParsed(apiResponse(ipAssetSchema), `/ip-assets/${id}`),

  create: (data: IpAssetCreate) =>
    postParsed(apiResponse(ipAssetSchema), "/ip-assets", ipAssetCreateSchema.parse(data)),

  update: (id: number | string, data: { notes?: string | null }) =>
    patchParsed(apiResponse(ipAssetSchema), `/ip-assets/${id}`, data),

  delete: (id: number | string) =>
    apiClient.delete(`/ip-assets/${id}`).then(() => undefined),

  sync: (id: number | string) =>
    postParsed(
      apiResponse(ipAssetSyncResultSchema),
      `/ip-assets/${id}/sync`
    ),

  documents: (id: number | string) =>
    getParsed(z.array(ipDocumentSchema), `/ip-assets/${id}/documents`),

  fetchDocuments: (
    id: number | string,
    docTypes: Array<"refusal_reason" | "opinion_amendment" | "decision" | "citation">
  ) =>
    postParsed(
      apiResponse(
        z.object({
          asset_id: z.number().int(),
          application_number: z.string(),
          fetched: z.array(z.record(z.string(), z.string())).default([]),
          errors: z.array(z.record(z.string(), z.string())).default([]),
        })
      ),
      `/ip-assets/${id}/documents/fetch`,
      { doc_types: docTypes }
    ),
};

export const ipWatchTargetsApi = {
  list: (params?: ListParams) =>
    getParsed(paginatedSchema(ipWatchTargetSchema), "/ip-watch-targets", {
      params: buildParams(params),
    }),

  create: (data: IpWatchTargetCreate) =>
    postParsed(
      apiResponse(ipWatchTargetSchema),
      "/ip-watch-targets",
      ipWatchTargetCreateSchema.parse(data)
    ),

  update: (id: number | string, data: Partial<IpWatchTargetCreate>) =>
    patchParsed(apiResponse(ipWatchTargetSchema), `/ip-watch-targets/${id}`, data),

  delete: (id: number | string) =>
    apiClient.delete(`/ip-watch-targets/${id}`).then(() => undefined),

  sync: (id: number | string) =>
    postParsed(
      apiResponse(ipWatchTargetSyncResultSchema),
      `/ip-watch-targets/${id}/sync`
    ),
};

export const ipWatchEventsApi = {
  list: (params?: { watch_target_id?: number | string; unread_only?: boolean; page?: number; size?: number }) =>
    getParsed(paginatedSchema(ipWatchEventSchema), "/ip-watch-events", {
      params: buildParams(params),
    }),

  markRead: (id: number | string) =>
    patchParsed(apiResponse(ipWatchEventSchema), `/ip-watch-events/${id}/read`, {}),
};

export const ipDocumentsApi = {
  get: (id: number | string) =>
    getParsed(apiResponse(ipDocumentSchema), `/ip-documents/${id}`),

  analyze: (id: number | string) =>
    postParsed(
      apiResponse(
        z.object({
          document_id: z.number().int(),
          doc_type: z.string(),
          ai_model: z.string(),
          summary: z.string(),
          findings: z.record(z.string(), z.unknown()),
          analyzed_at: z.string(),
        })
      ),
      `/ip-documents/${id}/analyze`
    ),
};

export const ipDashboardApi = {
  get: () => getParsed(apiResponse(ipDashboardSchema), "/ip-dashboard"),
};

export const ipMetaApi = {
  jpoStatus: () => getParsed(apiResponse(jpoStatusSchema), "/ip/jpo-status"),
};

// ===========================================================================
// 19. 電子契約・電子署名 (ロードマップ #1-4 / /signing)
// ===========================================================================

export interface SigningListParams extends ListParams {
  contract_id?: number | string;
  status?: string;
}

export const signingApi = {
  list: (params?: SigningListParams) =>
    getParsed(paginatedSchema(signingEnvelopeSchema), "/signing", {
      params: buildParams(params),
    }),

  get: (id: number | string) =>
    getParsed(apiResponse(signingEnvelopeSchema), `/signing/${id}`),

  create: (
    data: {
      contract_id: number | string;
      method?: string;
      provider?: string;
      counterparty_name?: string | null;
      counterparty_email?: string | null;
      note?: string | null;
    },
    opts?: { idempotencyKey?: string },
  ) =>
    postParsed(
      signingEnvelopeSchema,
      "/signing",
      signingEnvelopeCreateSchema.parse(data),
      withIdempotencyKey({}, opts?.idempotencyKey),
    ),

  /** 証跡イベント一覧（追記専用・読み取りのみ） */
  events: (id: number | string) =>
    getParsed(z.array(signingEventSchema), `/signing/${id}/events`),

  send: (id: number | string) =>
    postParsed(apiResponse(signingEnvelopeSchema), `/signing/${id}/send`, {}),

  /** 相手方の承諾証跡を記録（建設業法 19 条・電磁的方法） */
  consent: (
    id: number | string,
    data: { consentor_name?: string | null; consentor_email?: string | null; note?: string | null },
  ) => postParsed(apiResponse(signingEnvelopeSchema), `/signing/${id}/consent`, data),

  view: (id: number | string) =>
    postParsed(apiResponse(signingEnvelopeSchema), `/signing/${id}/view`, {}),

  sign: (
    id: number | string,
    data: { signer_name?: string | null; signer_email?: string | null },
  ) => postParsed(apiResponse(signingEnvelopeSchema), `/signing/${id}/sign`, data),

  /** 締結完了（signed → completed・attachment_id 任意） */
  complete: (id: number | string, data: { attachment_id?: number | string | null } = {}) =>
    postParsed(apiResponse(signingEnvelopeSchema), `/signing/${id}/complete`, data),

  cancel: (id: number | string, data: { reason?: string | null } = {}) =>
    postParsed(apiResponse(signingEnvelopeSchema), `/signing/${id}/cancel`, data),
};

// ===========================================================================
// 20. 契約交渉・Redline (ロードマップ #5-8 / /contracts/{id}/negotiations 等)
// ===========================================================================

export interface NegotiationListParams extends ListParams {
  clause_id?: number | string;
}

export const negotiationsApi = {
  /** 交渉履歴タイムライン（新しい順） */
  list: (contractId: number | string, params?: NegotiationListParams) =>
    getParsed(paginatedSchema(negotiationEventSchema), `/contracts/${contractId}/negotiations`, {
      params: buildParams(params),
    }),

  /** 交渉イベント記録（redline / demand / concession / comment） */
  add: (
    contractId: number | string,
    data: {
      action: string;
      clause_id?: number | string | null;
      round_no?: number | null;
      note?: string | null;
      proposed_text?: string | null;
    },
    opts?: { idempotencyKey?: string },
  ) =>
    postParsed(
      negotiationEventSchema,
      `/contracts/${contractId}/negotiations`,
      negotiationEventCreateSchema.parse(data),
      withIdempotencyKey({}, opts?.idempotencyKey),
    ),

  /** 条項ステータス更新（accepted / rejected / negotiating） */
  setClauseStatus: (
    contractId: number | string,
    clauseId: number | string,
    data: { status: string; note?: string | null },
  ) =>
    postParsed(
      apiResponse(clauseNegotiationStateSchema),
      `/contracts/${contractId}/clauses/${clauseId}/status`,
      data,
    ),

  /** 条項オーナー割当（法務・工事・営業・購買・その他） */
  setClauseOwner: (
    contractId: number | string,
    clauseId: number | string,
    data: { owner: string; note?: string | null },
  ) =>
    postParsed(
      apiResponse(clauseNegotiationStateSchema),
      `/contracts/${contractId}/clauses/${clauseId}/owner`,
      data,
    ),
};

// ===========================================================================
// 21. 契約義務・Obligations Calendar (ロードマップ #9-13 / /obligations)
// ===========================================================================

export interface ObligationListParams extends ListParams {
  contract_id?: number | string;
  type?: string;
  status?: string;
  /** overdue / within_30 / within_60 / future */
  bucket?: string;
  from?: string;
  to?: string;
}

export const obligationsApi = {
  list: (params?: ObligationListParams) =>
    getParsed(paginatedSchema(obligationSchema), "/obligations", {
      params: buildParams(params),
    }),

  /** 自動更新・解約通知期限チェック（#12） */
  renewalCheck: (params?: { contract_id?: number | string }) =>
    getParsed(z.array(renewalCheckSchema), "/obligations/renewal-check", {
      params: buildParams(params),
    }),

  update: (
    id: number | string,
    data: {
      title?: string;
      description?: string | null;
      due_date?: string | null;
      assignee_id?: number | string | null;
      status?: string | null;
    },
  ) => patchParsed(apiResponse(obligationSchema), `/obligations/${id}`, data),

  complete: (id: number | string) =>
    postParsed(apiResponse(obligationSchema), `/obligations/${id}/complete`, {}),

  waive: (id: number | string) =>
    postParsed(apiResponse(obligationSchema), `/obligations/${id}/waive`, {}),

  /** 契約へ義務を登録 */
  createForContract: (
    contractId: number | string,
    data: {
      obligation_type: string;
      title: string;
      description?: string | null;
      due_date?: string | null;
      assignee_id?: number | string | null;
      status?: string;
    },
    opts?: { idempotencyKey?: string },
  ) =>
    postParsed(
      obligationSchema,
      `/contracts/${contractId}/obligations`,
      obligationCreateSchema.parse(data),
      withIdempotencyKey({}, opts?.idempotencyKey),
    ),
};

// ===========================================================================
// 22. 契約書全文検索 (ロードマップ #5下位 / /search)
// ===========================================================================

export interface ContractSearchParams extends ListParams {
  q: string;
  scope?: string;
  contract_id?: number | string;
  limit?: number;
}

export const contractSearchApi = {
  search: (params: ContractSearchParams) =>
    getParsed(z.array(contractSearchHitSchema), "/search", { params: buildParams(params) }),
};

// ===========================================================================
// 23. Legal Matter Management (ロードマップ #71-84 / /matters)
// ===========================================================================

export interface MatterListParams extends ListParams {
  status?: string;
  type?: string;
  assignee_id?: number | string;
}

export const mattersApi = {
  list: (params?: MatterListParams) =>
    getParsed(paginatedSchema(matterSchema), "/matters", {
      params: buildParams(params),
    }),

  get: (id: number | string) =>
    getParsed(apiResponse(matterSchema), `/matters/${id}`),

  create: (
    data: {
      title: string;
      matter_type: string;
      description?: string | null;
      priority?: string;
      assignee_id?: number | string | null;
      source_type?: string | null;
      source_id?: number | string | null;
      contract_ids?: Array<number | string>;
      legal_hold_case_id?: number | string | null;
    },
    opts?: { idempotencyKey?: string },
  ) => postParsed(matterSchema, "/matters", data, withIdempotencyKey({}, opts?.idempotencyKey)),

  update: (id: number | string, data: { title?: string; description?: string | null; priority?: string }) =>
    patchParsed(apiResponse(matterSchema), `/matters/${id}`, data),

  /** 状態遷移（open/in_progress/waiting/on_hold/closed） */
  setStatus: (
    id: number | string,
    data: { status: string; note?: string | null },
  ) => postParsed(apiResponse(matterSchema), `/matters/${id}/status`, data),

  /** 担当法務アサイン（assignee_id null で解除） */
  assign: (
    id: number | string,
    data: { assignee_id?: number | string | null; note?: string | null },
  ) => postParsed(apiResponse(matterSchema), `/matters/${id}/assign`, data),

  /** 関係契約リンク（#79） */
  linkContract: (id: number | string, data: { contract_id: number | string }) =>
    postParsed(apiResponse(matterSchema), `/matters/${id}/contracts`, data),

  unlinkContract: (id: number | string, contractId: number | string) =>
    apiClient.delete(`/matters/${id}/contracts/${contractId}`).then(() => undefined),

  /** 関係契約一覧 */
  contracts: (id: number | string) =>
    getParsed(z.array(matterContractSchema), `/matters/${id}/contracts`),

  /** Legal Hold 連動（#82・null で解除） */
  setLegalHold: (id: number | string, data: { legal_hold_case_id?: number | string | null }) =>
    postParsed(apiResponse(matterSchema), `/matters/${id}/legal-hold`, data),

  /** タイムライン（追記専用） */
  events: (id: number | string) =>
    getParsed(z.array(matterEventSchema), `/matters/${id}/events`),

  /** タイムラインへメモ追記 */
  addNote: (id: number | string, data: { note: string }) =>
    postParsed(matterEventSchema, `/matters/${id}/notes`, data),
};

// ===========================================================================
// 24. 顧問弁護士・外部法律事務所 (ロードマップ #85-96 / /outside-counsel)
// ===========================================================================

export interface LawFirmListParams extends ListParams {
  is_active?: boolean;
}

export const lawFirmsApi = {
  list: (params?: LawFirmListParams) =>
    getParsed(paginatedSchema(lawFirmSchema), "/outside-counsel/firms", {
      params: buildParams(params),
    }),

  create: (
    data: {
      firm_name: string;
      contact_email?: string | null;
      phone?: string | null;
      address?: string | null;
      notes?: string | null;
    },
    opts?: { idempotencyKey?: string },
  ) =>
    postParsed(
      lawFirmSchema,
      "/outside-counsel/firms",
      lawFirmCreateSchema.parse(data),
      withIdempotencyKey({}, opts?.idempotencyKey),
    ),

  /** 事務所の弁護士一覧（#87） */
  lawyers: (firmId: number | string, params?: LawFirmListParams) =>
    getParsed(paginatedSchema(counselLawyerSchema), `/outside-counsel/firms/${firmId}/lawyers`, {
      params: buildParams(params),
    }),

  /** 弁護士登録 */
  createLawyer: (
    firmId: number | string,
    data: {
      firm_id: number | string;
      lawyer_name: string;
      email?: string | null;
      bar_number?: string | null;
      specialties?: string | null;
    },
    opts?: { idempotencyKey?: string },
  ) =>
    postParsed(
      counselLawyerSchema,
      `/outside-counsel/firms/${firmId}/lawyers`,
      counselLawyerCreateSchema.parse(data),
      withIdempotencyKey({}, opts?.idempotencyKey),
    ),
};

export interface EngagementListParams extends ListParams {
  status?: string;
  firm_id?: number | string;
  matter_id?: number | string;
}

export const engagementsApi = {
  list: (params?: EngagementListParams) =>
    getParsed(paginatedSchema(engagementSchema), "/outside-counsel/engagements", {
      params: buildParams(params),
    }),

  get: (id: number | string) =>
    getParsed(apiResponse(engagementSchema), `/outside-counsel/engagements/${id}`),

  /** 依頼起票（#85） */
  create: (
    data: {
      firm_id: number | string;
      lawyer_id?: number | string | null;
      matter_id?: number | string | null;
      title: string;
      question: string;
      due_date?: string | null;
      conflict_of_interest?: boolean;
      conflict_note?: string | null;
      confidential?: boolean;
      fee_estimate_jpy?: number | null;
    },
    opts?: { idempotencyKey?: string },
  ) =>
    postParsed(
      engagementSchema,
      "/outside-counsel/engagements",
      data,
      withIdempotencyKey({}, opts?.idempotencyKey),
    ),

  /** 回答登録（#89・open→answered） */
  answer: (id: number | string, data: { answer: string }) =>
    postParsed(apiResponse(engagementSchema), `/outside-counsel/engagements/${id}/answer`, data),

  /** 回答確認（answered→confirmed） */
  confirm: (id: number | string) =>
    postParsed(apiResponse(engagementSchema), `/outside-counsel/engagements/${id}/confirm`, {}),

  cancel: (id: number | string, data: { reason?: string | null } = {}) =>
    postParsed(apiResponse(engagementSchema), `/outside-counsel/engagements/${id}/cancel`, data),
};

// ===========================================================================
// 25. 労務費基準マスタ・乖離率判定 (ロードマップ #16-20 / /labor-wage)
// ===========================================================================

export interface LaborWageListParams extends ListParams {
  work_type?: string;
  prefecture?: string;
  as_of?: string;
}

export const laborWageApi = {
  standards: (params?: LaborWageListParams) =>
    getParsed(paginatedSchema(laborWageStandardSchema), "/labor-wage/standards", {
      params: buildParams(params),
    }),

  /** 基準登録（#16 データ更新・履歴蓄積） */
  createStandard: (
    data: {
      work_type: string;
      amount_jpy: number;
      prefecture?: string | null;
      effective_from: string;
      effective_to?: string | null;
      amount_unit?: string;
      source_ref?: string | null;
    },
    opts?: { idempotencyKey?: string },
  ) =>
    postParsed(
      laborWageStandardSchema,
      "/labor-wage/standards",
      laborWageStandardCreateSchema.parse(data),
      withIdempotencyKey({}, opts?.idempotencyKey),
    ),

  /** as-of 日時点の最新基準値（#16/#17/#18） */
  latest: (params: { work_type: string; prefecture?: string | null; as_of?: string | null }) =>
    getParsed(apiResponse(laborWageStandardSchema), "/labor-wage/standards/latest", {
      params: buildParams(params),
    }),

  /** 労務費乖離率判定（#20・基準未満を below で検出・#21 深刻度付き） */
  discrepancy: (params: {
    work_type: string;
    quote_day_jpy: number;
    prefecture?: string | null;
    as_of?: string | null;
  }) =>
    getParsed(apiResponse(laborWageDiscrepancySchema), "/labor-wage/discrepancy", {
      params: buildParams(params),
    }),

  // --- #22 標準工期マスタ・短工期判定 ---
  standardDurations: (params?: {
    work_type?: string;
    prefecture?: string;
    as_of?: string;
    page?: number;
    size?: number;
  }) =>
    getParsed(paginatedSchema(standardWorkDurationSchema), "/labor-wage/standard-durations", {
      params: buildParams(params),
    }),

  createStandardDuration: (
    data: {
      work_type: string;
      prefecture?: string | null;
      amount_min_jpy: number;
      amount_max_jpy?: number | null;
      standard_days: number;
      effective_from: string;
      effective_to?: string | null;
      source_ref?: string | null;
    },
    opts?: { idempotencyKey?: string },
  ) =>
    postParsed(
      standardWorkDurationSchema,
      "/labor-wage/standard-durations",
      standardWorkDurationCreateSchema.parse(data),
      withIdempotencyKey({}, opts?.idempotencyKey),
    ),

  /** 短工期判定（#22・標準工期との短縮率から深刻度を導出） */
  shortDurationCheck: (params: {
    work_type: string;
    amount_jpy: number;
    planned_days: number;
    prefecture?: string | null;
    as_of?: string | null;
  }) =>
    getParsed(apiResponse(shortDurationCheckSchema), "/labor-wage/short-duration-check", {
      params: buildParams(params),
    }),

  // --- #25/#26 価格転嫁シミュレータ ---
  priceSimulator: (data: {
    contract_amount_jpy: number;
    labor_cost_jpy: number;
    material_cost_jpy: number;
    labor_change_rate: number;
    material_change_rate: number;
    pass_through_rate: number;
  }) =>
    postParsed(
      priceSimulatorOutSchema,
      "/labor-wage/price-simulator",
      priceSimulatorInSchema.parse(data),
    ),
};

// ===========================================================================
// 26. 労務費価格協議・乖離確認 (ロードマップ #21/#23/#24 / /price-consultations)
// ===========================================================================

export interface PriceConsultationListParams extends ListParams {
  status?: string;
  direction?: string;
  severity?: string;
  contract_id?: number | string;
}

export const priceConsultationApi = {
  /** 価格協議ログ一覧（#24/#23） */
  list: (params?: PriceConsultationListParams) =>
    getParsed(paginatedSchema(priceConsultationLogSchema), "/price-consultations", {
      params: buildParams(params),
    }),

  /** 協議申出を記録（#24・乖離スナップショット付き） */
  create: (
    data: {
      direction: string;
      work_type: string;
      contract_id?: number | string | null;
      prefecture?: string | null;
      quote_day_jpy?: number | null;
      summary: string;
      request_detail?: string | null;
      requested_at?: string | null;
    },
    opts?: { idempotencyKey?: string },
  ) =>
    postParsed(
      priceConsultationLogSchema,
      "/price-consultations",
      priceConsultationCreateSchema.parse(data),
      withIdempotencyKey({}, opts?.idempotencyKey),
    ),

  get: (id: number | string) =>
    getParsed(apiResponse(priceConsultationLogSchema), `/price-consultations/${id}`),

  /** 回答（#24・open → responded） */
  respond: (id: number | string, data: { response_summary: string }) =>
    postParsed(
      apiResponse(priceConsultationLogSchema),
      `/price-consultations/${id}/respond`,
      data,
    ),

  /** 取下げ（#24・open → cancelled） */
  cancel: (id: number | string, data: { reason: string }) =>
    postParsed(
      apiResponse(priceConsultationLogSchema),
      `/price-consultations/${id}/cancel`,
      data,
    ),

  /** #23 見積変更要求監視（未回答の協議のみ） */
  monitorQuoteChanges: (params?: { severity?: string; page?: number; size?: number }) =>
    getParsed(paginatedSchema(priceConsultationLogSchema), "/price-consultations/monitor/quote-changes", {
      params: buildParams(params),
    }),
};

// ===========================================================================
// 27. 公共工事特化 (ロードマップ #41-#43・#54-#57・#60 / /public-works)
// ===========================================================================

export interface AgencyListParams extends ListParams {
  agency_type?: string;
  is_active?: boolean;
}

export const contractingAgenciesApi = {
  list: (params?: AgencyListParams) =>
    getParsed(paginatedSchema(contractingAgencySchema), "/public-works/contracting-agencies", {
      params: buildParams(params),
    }),

  create: (
    data: {
      code: string;
      name: string;
      agency_type: string;
      prefecture?: string | null;
      contact_email?: string | null;
      phone?: string | null;
      payment_deadline_days?: number | null;
      advance_payment_ratio?: number | null;
      warranty_period_months?: number | null;
      requires_slide_clause?: boolean;
      notes?: string | null;
    },
    opts?: { idempotencyKey?: string },
  ) =>
    postParsed(
      contractingAgencySchema,
      "/public-works/contracting-agencies",
      contractingAgencyCreateSchema.parse(data),
      withIdempotencyKey({}, opts?.idempotencyKey),
    ),
};

export interface OwnerNotificationListParams extends ListParams {
  status?: string;
  type?: string;
  contract_id?: number | string;
}

export const ownerNotificationsApi = {
  list: (params?: OwnerNotificationListParams) =>
    getParsed(paginatedSchema(ownerNotificationSchema), "/public-works/notifications", {
      params: buildParams(params),
    }),

  create: (
    data: {
      notification_type: string;
      title: string;
      contract_id?: number | string | null;
      agency_id?: number | string | null;
      detail?: string | null;
      due_date?: string | null;
    },
    opts?: { idempotencyKey?: string },
  ) =>
    postParsed(
      ownerNotificationSchema,
      "/public-works/notifications",
      ownerNotificationCreateSchema.parse(data),
      withIdempotencyKey({}, opts?.idempotencyKey),
    ),

  notify: (id: number | string) =>
    postParsed(
      ownerNotificationSchema,
      `/public-works/notifications/${id}/notify`,
      {},
    ),

  cancel: (id: number | string, data: { reason: string }) =>
    postParsed(ownerNotificationSchema, `/public-works/notifications/${id}/cancel`, data),
};

export interface PublicWorksConsultationListParams extends ListParams {
  status?: string;
  type?: string;
  contract_id?: number | string;
}

export const publicWorksConsultationsApi = {
  list: (params?: PublicWorksConsultationListParams) =>
    getParsed(
      paginatedSchema(publicWorksConsultationSchema),
      "/public-works/consultations",
      { params: buildParams(params) },
    ),

  create: (
    data: {
      consultation_type: string;
      title: string;
      contract_id?: number | string | null;
      agency_id?: number | string | null;
      detail?: string | null;
      requested_at?: string | null;
      due_date?: string | null;
      claimed_days?: number | null;
      claimed_amount_jpy?: number | null;
    },
    opts?: { idempotencyKey?: string },
  ) =>
    postParsed(
      publicWorksConsultationSchema,
      "/public-works/consultations",
      publicWorksConsultationCreateSchema.parse(data),
      withIdempotencyKey({}, opts?.idempotencyKey),
    ),

  respond: (
    id: number | string,
    data: {
      response_note: string;
      resolved_days?: number | null;
      resolved_amount_jpy?: number | null;
    },
  ) =>
    postParsed(
      publicWorksConsultationSchema,
      `/public-works/consultations/${id}/respond`,
      data,
    ),

  cancel: (id: number | string, data: { reason: string }) =>
    postParsed(publicWorksConsultationSchema, `/public-works/consultations/${id}/cancel`, data),
};

export const publicWorksApi = {
  /** #43 標準請負約款差分チェック */
  standardClauseCheck: (contractId: number | string) =>
    getParsed(apiResponse(standardClauseCheckSchema), "/public-works/standard-clause-check", {
      params: buildParams({ contract_id: contractId }),
    }),

  /** #60 ダッシュボード */
  dashboard: () =>
    getParsed(apiResponse(publicWorksDashboardSchema), "/public-works/dashboard"),
};

// ===========================================================================
// 28. JV（共同企業体）管理 (ロードマップ #61-#70 / /joint-ventures)
// ===========================================================================

export const jvApi = {
  list: (params?: { status?: string; page?: number; size?: number }) =>
    getParsed(paginatedSchema(jvSchema), "/joint-ventures", {
      params: buildParams(params),
    }),

  create: (
    data: {
      name: string;
      representative_name?: string | null;
      works_title?: string | null;
      contract_id?: number | string | null;
      start_date?: string | null;
      end_date?: string | null;
      notes?: string | null;
    },
    opts?: { idempotencyKey?: string },
  ) =>
    postParsed(jvSchema, "/joint-ventures", jvCreateSchema.parse(data), withIdempotencyKey({}, opts?.idempotencyKey)),

  get: (id: number | string) =>
    getParsed(apiResponse(jvSchema), `/joint-ventures/${id}`),

  setStatus: (id: number | string, data: { status: string }) =>
    postParsed(apiResponse(jvSchema), `/joint-ventures/${id}/status`, data),

  members: (id: number | string) =>
    getParsed(z.array(jvMemberSchema), `/joint-ventures/${id}/members`),

  addMember: (
    id: number | string,
    data: {
      company_name: string;
      role?: string;
      equity_ratio?: number | null;
      profit_share_ratio?: number | null;
      contact_email?: string | null;
      notes?: string | null;
    },
    opts?: { idempotencyKey?: string },
  ) =>
    postParsed(
      jvMemberSchema,
      `/joint-ventures/${id}/members`,
      jvMemberCreateSchema.parse(data),
      withIdempotencyKey({}, opts?.idempotencyKey),
    ),

  agreements: (id: number | string) =>
    getParsed(z.array(jvAgreementSchema), `/joint-ventures/${id}/agreements`),

  createAgreement: (
    id: number | string,
    data: {
      title: string;
      summary?: string | null;
      signed_at?: string | null;
      document_url?: string | null;
    },
    opts?: { idempotencyKey?: string },
  ) =>
    postParsed(
      jvAgreementSchema,
      `/joint-ventures/${id}/agreements`,
      data,
      withIdempotencyKey({}, opts?.idempotencyKey),
    ),

  disputes: (id: number | string) =>
    getParsed(z.array(jvDisputeSchema), `/joint-ventures/${id}/disputes`),

  createDispute: (
    id: number | string,
    data: {
      title: string;
      claimant_name?: string | null;
      respondent_name?: string | null;
      amount_claimed_jpy?: number | null;
      detail?: string | null;
    },
    opts?: { idempotencyKey?: string },
  ) =>
    postParsed(
      jvDisputeSchema,
      `/joint-ventures/${id}/disputes`,
      data,
      withIdempotencyKey({}, opts?.idempotencyKey),
    ),

  respondDispute: (disputeId: number | string, data: { response_note: string }) =>
    postParsed(jvDisputeSchema, `/joint-ventures/disputes/${disputeId}/respond`, data),

  settlements: (id: number | string) =>
    getParsed(z.array(jvSettlementSchema), `/joint-ventures/${id}/settlements`),

  createSettlement: (
    id: number | string,
    data: {
      title: string;
      settlement_amount_jpy?: number | null;
      detail?: string | null;
    },
    opts?: { idempotencyKey?: string },
  ) =>
    postParsed(
      jvSettlementSchema,
      `/joint-ventures/${id}/settlements`,
      data,
      withIdempotencyKey({}, opts?.idempotencyKey),
    ),

  settle: (settlementId: number | string) =>
    postParsed(jvSettlementSchema, `/joint-ventures/settlements/${settlementId}/settle`, {}),

  dashboard: () => getParsed(apiResponse(jvDashboardSchema), "/joint-ventures/dashboard/summary"),
};

// ===========================================================================
// 29. 協力会社拡張 (ロードマップ #136-#152 / /partners 拡張)
// ===========================================================================

export const partnerExtApi = {
  /** #138/#146/#151 期限アラート一覧 */
  alerts: (params?: { within_days?: number; page?: number; size?: number }) =>
    getParsed(z.array(partnerExpiryFlagsSchema), "/partners/alerts", {
      params: buildParams(params),
    }),

  /** 期限状態フラグ */
  expiryFlags: (partnerId: number | string) =>
    getParsed(apiResponse(partnerExpiryFlagsSchema), `/partners/${partnerId}/expiry-flags`),

  /** #150 Risk Score（計算のみ） */
  riskScore: (partnerId: number | string) =>
    getParsed(apiResponse(partnerRiskScoreSchema), `/partners/${partnerId}/risk-score`),

  /** #150 Risk Score を算出して保存 */
  refreshRiskScore: (partnerId: number | string) =>
    postParsed(
      apiResponse(partnerRiskScoreSchema),
      `/partners/${partnerId}/risk-score/refresh`,
      {},
    ),

  /** #147-#149/#151 再審査一覧 */
  reviews: (partnerId: number | string, params?: { status?: string; type?: string }) =>
    getParsed(paginatedSchema(partnerReviewSchema), `/partners/${partnerId}/reviews`, {
      params: buildParams(params),
    }),

  /** 再審査・incident/violation 起票 */
  createReview: (
    partnerId: number | string,
    data: {
      review_type: string;
      title: string;
      safety_score?: number | null;
      findings?: string | null;
      violation_count?: number;
      incident_count?: number;
      notes?: string | null;
    },
    opts?: { idempotencyKey?: string },
  ) =>
    postParsed(
      partnerReviewSchema,
      `/partners/${partnerId}/reviews`,
      partnerReviewCreateSchema.parse(data),
      withIdempotencyKey({}, opts?.idempotencyKey),
    ),

  /** #151 再審査完了（次回期限を Partner へ反映） */
  completeReview: (
    reviewId: number | string,
    data: {
      safety_score?: number | null;
      findings?: string | null;
      violation_count?: number | null;
      incident_count?: number | null;
      next_review_due?: string | null;
    },
  ) =>
    postParsed(
      partnerReviewSchema,
      `/partners/partner-reviews/${reviewId}/complete`,
      data,
    ),
};

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
  ipAssets: ipAssetsApi,
  ipWatchTargets: ipWatchTargetsApi,
  ipWatchEvents: ipWatchEventsApi,
  ipDocuments: ipDocumentsApi,
  ipDashboard: ipDashboardApi,
  ipMeta: ipMetaApi,
  signing: signingApi,
  negotiations: negotiationsApi,
  obligations: obligationsApi,
  contractSearch: contractSearchApi,
  matters: mattersApi,
  lawFirms: lawFirmsApi,
  engagements: engagementsApi,
  laborWage: laborWageApi,
  priceConsultations: priceConsultationApi,
  contractingAgencies: contractingAgenciesApi,
  ownerNotifications: ownerNotificationsApi,
  publicWorksConsultations: publicWorksConsultationsApi,
  publicWorks: publicWorksApi,
  jv: jvApi,
  partnerExt: partnerExtApi,
} as const;

