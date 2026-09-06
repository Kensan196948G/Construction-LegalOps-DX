/**
 * TanStack Query — 階層的 queryKey 定義
 *
 * 階層化方針:
 *   [domain, "list" | "detail" | "<sub-resource>", ...args]
 *
 * 例:
 *   contracts: [ "contracts", "list", params ]
 *   contract detail: [ "contracts", "detail", id ]
 *   clauses sub-resource: [ "contracts", "detail", id, "clauses" ]
 *
 * 利点:
 *   - `invalidateQueries({ queryKey: ["contracts"] })` で全 contracts キャッシュ無効化
 *   - `invalidateQueries({ queryKey: ["contracts", "list"] })` で一覧だけ無効化
 *   - 詳細だけ無効化したいときも明確に表現できる
 */

export const queryKeys = {
  auth: {
    all: ["auth"] as const,
    me: () => ["auth", "me"] as const,
  },

  users: {
    all: ["users"] as const,
    lists: () => ["users", "list"] as const,
    list: (params?: unknown) => ["users", "list", params] as const,
    details: () => ["users", "detail"] as const,
    detail: (id: number | string) => ["users", "detail", id] as const,
  },

  contracts: {
    all: ["contracts"] as const,
    lists: () => ["contracts", "list"] as const,
    list: (params?: unknown) => ["contracts", "list", params] as const,
    details: () => ["contracts", "detail"] as const,
    detail: (id: number | string) => ["contracts", "detail", id] as const,
    clauses: (id: number | string) => ["contracts", "detail", id, "clauses"] as const,
    auditTrail: (id: number | string) =>
      ["contracts", "detail", id, "audit-trail"] as const,
    workflowSteps: (id: number | string) =>
      ["contracts", "detail", id, "workflow-steps"] as const,
  },

  reviews: {
    all: ["reviews"] as const,
    lists: () => ["reviews", "list"] as const,
    list: (params?: unknown) => ["reviews", "list", params] as const,
    details: () => ["reviews", "detail"] as const,
    detail: (id: number | string) => ["reviews", "detail", id] as const,
  },

  workflows: {
    all: ["workflows"] as const,
    lists: () => ["workflows", "list"] as const,
    list: (params?: unknown) => ["workflows", "list", params] as const,
    details: () => ["workflows", "detail"] as const,
    detail: (id: number | string) => ["workflows", "detail", id] as const,
    step: (stepId: number | string) => ["workflows", "step", stepId] as const,
    applications: (params?: unknown) => ["workflows", "applications", params] as const,
  },

  risks: {
    all: ["risks"] as const,
    lists: () => ["risks", "list"] as const,
    list: (params?: unknown) => ["risks", "list", params] as const,
    details: () => ["risks", "detail"] as const,
    detail: (id: number | string) => ["risks", "detail", id] as const,
    heatmap: () => ["risks", "heatmap"] as const,
  },

  compliance: {
    all: ["compliance"] as const,
    checklists: (params?: unknown) => ["compliance", "checklists", params] as const,
    runs: () => ["compliance", "runs"] as const,
    run: (id: number | string) => ["compliance", "runs", id] as const,
  },

  templates: {
    all: ["templates"] as const,
    lists: () => ["templates", "list"] as const,
    list: (params?: unknown) => ["templates", "list", params] as const,
    details: () => ["templates", "detail"] as const,
    detail: (id: number | string) => ["templates", "detail", id] as const,
    clauseLibrary: (params?: unknown) =>
      ["templates", "clause-library", params] as const,
  },

  knowledge: {
    all: ["knowledge"] as const,
    lists: () => ["knowledge", "list"] as const,
    list: (params?: unknown) => ["knowledge", "list", params] as const,
    details: () => ["knowledge", "detail"] as const,
    detail: (id: number | string) => ["knowledge", "detail", id] as const,
  },

  auditLogs: {
    all: ["audit-logs"] as const,
    lists: () => ["audit-logs", "list"] as const,
    list: (params?: unknown) => ["audit-logs", "list", params] as const,
  },

  uploads: {
    all: ["uploads"] as const,
    detail: (id: number | string) => ["uploads", "detail", id] as const,
  },

  notifications: {
    all: ["notifications"] as const,
    lists: () => ["notifications", "list"] as const,
    list: (params?: unknown) => ["notifications", "list", params] as const,
    unreadCount: () => ["notifications", "unread-count"] as const,
  },

  dashboard: {
    all: ["dashboard"] as const,
    summary: (params?: unknown) => ["dashboard", "summary", params] as const,
    trends: (params?: unknown) => ["dashboard", "trends", params] as const,
  },

  settings: {
    all: ["settings"] as const,
    aiSettings: () => ["settings", "ai-settings"] as const,
  },

  changeOrders: {
    all: ["change-orders"] as const,
    lists: () => ["change-orders", "list"] as const,
    list: (params?: unknown) => ["change-orders", "list", params] as const,
    impact: (contractId: number | string) =>
      ["change-orders", "impact", contractId] as const,
  },

  partners: {
    all: ["partners"] as const,
    lists: () => ["partners", "list"] as const,
    list: (params?: unknown) => ["partners", "list", params] as const,
    summary: () => ["partners", "summary"] as const,
  },

  disputes: {
    all: ["disputes"] as const,
    lists: () => ["disputes", "list"] as const,
    list: (params?: unknown) => ["disputes", "list", params] as const,
    details: () => ["disputes", "detail"] as const,
    detail: (id: number | string) => ["disputes", "detail", id] as const,
    exposure: () => ["disputes", "exposure"] as const,
  },

  payments: {
    all: ["payments"] as const,
    check: (contractId: number | string) =>
      ["payments", "check", contractId] as const,
  },

  governance: {
    all: ["governance"] as const,
    acl: (contractId: number | string) =>
      ["governance", "acl", contractId] as const,
    legalHolds: (params?: unknown) => ["governance", "legal-holds", params] as const,
    retention: () => ["governance", "retention"] as const,
  },

  signing: {
    all: ["signing"] as const,
    lists: () => ["signing", "list"] as const,
    list: (params?: unknown) => ["signing", "list", params] as const,
    details: () => ["signing", "detail"] as const,
    detail: (id: number | string) => ["signing", "detail", id] as const,
    events: (id: number | string) => ["signing", "detail", id, "events"] as const,
  },

  negotiations: {
    all: ["negotiations"] as const,
    list: (contractId: number | string, params?: unknown) =>
      ["negotiations", "list", contractId, params] as const,
  },

  obligations: {
    all: ["obligations"] as const,
    lists: () => ["obligations", "list"] as const,
    list: (params?: unknown) => ["obligations", "list", params] as const,
    renewalCheck: (params?: unknown) =>
      ["obligations", "renewal-check", params] as const,
  },

  search: {
    all: ["search"] as const,
    contracts: (params?: unknown) => ["search", "contracts", params] as const,
  },

  matters: {
    all: ["matters"] as const,
    lists: () => ["matters", "list"] as const,
    list: (params?: unknown) => ["matters", "list", params] as const,
    details: () => ["matters", "detail"] as const,
    detail: (id: number | string) => ["matters", "detail", id] as const,
    events: (id: number | string) => ["matters", "detail", id, "events"] as const,
    contracts: (id: number | string) =>
      ["matters", "detail", id, "contracts"] as const,
  },

  outsideCounsel: {
    all: ["outside-counsel"] as const,
    firms: (params?: unknown) => ["outside-counsel", "firms", params] as const,
    lawyers: (params?: unknown) =>
      ["outside-counsel", "lawyers", params] as const,
    firmLawyers: (firmId: number | string, params?: unknown) =>
      ["outside-counsel", "firms", firmId, "lawyers", params] as const,
    engagements: (params?: unknown) =>
      ["outside-counsel", "engagements", params] as const,
    engagement: (id: number | string) =>
      ["outside-counsel", "engagements", id] as const,
  },

  laborWage: {
    all: ["labor-wage"] as const,
    standards: (params?: unknown) => ["labor-wage", "standards", params] as const,
    latest: (params?: unknown) =>
      ["labor-wage", "standards", "latest", params] as const,
    discrepancy: (params?: unknown) =>
      ["labor-wage", "discrepancy", params] as const,
  },

  priceConsultations: {
    all: ["price-consultations"] as const,
    lists: () => ["price-consultations", "list"] as const,
    list: (params?: unknown) => ["price-consultations", "list", params] as const,
    monitor: (params?: unknown) =>
      ["price-consultations", "monitor", params] as const,
    detail: (id: number | string) => ["price-consultations", "detail", id] as const,
  },

  publicWorks: {
    all: ["public-works"] as const,
    agencies: (params?: unknown) => ["public-works", "agencies", params] as const,
    notifications: (params?: unknown) =>
      ["public-works", "notifications", params] as const,
    consultations: (params?: unknown) =>
      ["public-works", "consultations", params] as const,
    clauseCheck: (contractId: number | string) =>
      ["public-works", "clause-check", contractId] as const,
    dashboard: () => ["public-works", "dashboard"] as const,
  },

  jv: {
    all: ["joint-ventures"] as const,
    lists: () => ["joint-ventures", "list"] as const,
    list: (params?: unknown) => ["joint-ventures", "list", params] as const,
    detail: (id: number | string) => ["joint-ventures", "detail", id] as const,
    members: (id: number | string) => ["joint-ventures", "detail", id, "members"] as const,
    dashboard: () => ["joint-ventures", "dashboard"] as const,
  },

  partnerExt: {
    all: ["partner-ext"] as const,
    alerts: (params?: unknown) => ["partner-ext", "alerts", params] as const,
    reviews: (partnerId: number | string, params?: unknown) =>
      ["partner-ext", "reviews", partnerId, params] as const,
    riskScore: (partnerId: number | string) =>
      ["partner-ext", "risk-score", partnerId] as const,
  },

  evidence: {
    all: ["evidence"] as const,
    lists: () => ["evidence", "list"] as const,
    list: (params?: unknown) => ["evidence", "list", params] as const,
    detail: (id: number | string) => ["evidence", "detail", id] as const,
    duplicates: (id: number | string) => ["evidence", "detail", id, "duplicates"] as const,
    timeline: (id: number | string) => ["evidence", "detail", id, "timeline"] as const,
    viewHistory: (id: number | string) => ["evidence", "detail", id, "view-history"] as const,
    custody: (id: number | string) => ["evidence", "detail", id, "custody"] as const,
    holdReleaseRequests: (params?: unknown) =>
      ["evidence", "hold-release-requests", params] as const,
  },
} as const;
