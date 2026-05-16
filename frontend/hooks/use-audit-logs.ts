"use client";

/**
 * Audit logs TanStack Query hooks
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationOptions,
  type UseQueryOptions,
} from "@tanstack/react-query";

import { ApiError } from "@/lib/api/client";
import { auditLogsApi, type AuditLogListParams } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/query-keys";
import type { AuditLog, AuditVerifyResult, Paginated } from "@/lib/api/schemas";

export function useAuditLogs(
  params?: AuditLogListParams,
  options?: Omit<UseQueryOptions<Paginated<AuditLog>, ApiError>, "queryKey" | "queryFn">,
) {
  return useQuery<Paginated<AuditLog>, ApiError>({
    queryKey: queryKeys.auditLogs.list(params),
    queryFn: () => auditLogsApi.list(params),
    ...options,
  });
}

export function useVerifyAuditLogs(
  options?: UseMutationOptions<AuditVerifyResult, ApiError, void>,
) {
  const qc = useQueryClient();
  return useMutation<AuditVerifyResult, ApiError, void>({
    mutationFn: () => auditLogsApi.verify(),
    ...options,
    onSuccess: (data, vars, ctx, fwCtx) => {
      qc.invalidateQueries({ queryKey: queryKeys.auditLogs.all });
      options?.onSuccess?.(data, vars, ctx, fwCtx);
    },
  });
}

export function useExportAuditLogs(
  options?: UseMutationOptions<Blob, ApiError, AuditLogListParams | undefined>,
) {
  return useMutation<Blob, ApiError, AuditLogListParams | undefined>({
    mutationFn: (params) => auditLogsApi.exportCsv(params),
    ...options,
  });
}
