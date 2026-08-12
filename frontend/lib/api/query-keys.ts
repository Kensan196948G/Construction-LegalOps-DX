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
} as const;
