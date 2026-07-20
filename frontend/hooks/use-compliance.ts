"use client";

/**
 * Compliance TanStack Query hooks
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationOptions,
  type UseQueryOptions,
} from "@tanstack/react-query";

import type { ApiError } from "@/lib/api/client";
import { complianceApi } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/query-keys";
import type {
  ComplianceCheckResult,
  ComplianceChecklist,
  ComplianceRun,
} from "@/lib/api/schemas";

export function useComplianceChecklists(
  params?: { page?: number; page_size?: number; q?: string },
  options?: Omit<
    UseQueryOptions<ComplianceChecklist[], ApiError>,
    "queryKey" | "queryFn"
  >,
) {
  return useQuery<ComplianceChecklist[], ApiError>({
    queryKey: queryKeys.compliance.checklists(params),
    queryFn: () => complianceApi.checklists(params),
    ...options,
  });
}

export function useComplianceRun(
  id: number | string | null | undefined,
  options?: Omit<UseQueryOptions<ComplianceCheckResult, ApiError>, "queryKey" | "queryFn">,
) {
  return useQuery<ComplianceCheckResult, ApiError>({
    queryKey: queryKeys.compliance.run(id ?? ""),
    queryFn: () => complianceApi.getResult(id as number | string),
    enabled: id !== null && id !== undefined && id !== "",
    ...options,
  });
}

export function useStartComplianceRun(
  options?: UseMutationOptions<
    ComplianceRun,
    ApiError,
    { contractId: number | string; checklistCodes?: string[] }
  >,
) {
  const qc = useQueryClient();
  return useMutation<
    ComplianceRun,
    ApiError,
    { contractId: number | string; checklistCodes?: string[] }
  >({
    mutationFn: ({ contractId, checklistCodes }) =>
      complianceApi.runForContract(contractId, checklistCodes),
    ...options,
    onSuccess: (data, vars, ctx, fwCtx) => {
      qc.invalidateQueries({ queryKey: queryKeys.compliance.all });
      qc.invalidateQueries({
        queryKey: queryKeys.contracts.detail(vars.contractId),
      });
      options?.onSuccess?.(data, vars, ctx, fwCtx);
    },
  });
}
