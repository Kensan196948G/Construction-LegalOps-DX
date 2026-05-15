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

import { ApiError } from "@/lib/api/client";
import { complianceApi } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/query-keys";
import type {
  ComplianceChecklist,
  ComplianceRun,
  Paginated,
} from "@/lib/api/schemas";

export function useComplianceChecklists(
  params?: { page?: number; page_size?: number; q?: string },
  options?: Omit<
    UseQueryOptions<Paginated<ComplianceChecklist>, ApiError>,
    "queryKey" | "queryFn"
  >,
) {
  return useQuery<Paginated<ComplianceChecklist>, ApiError>({
    queryKey: queryKeys.compliance.checklists(params),
    queryFn: () => complianceApi.checklists(params),
    ...options,
  });
}

export function useComplianceRun(
  id: number | string | null | undefined,
  options?: Omit<UseQueryOptions<ComplianceRun, ApiError>, "queryKey" | "queryFn">,
) {
  return useQuery<ComplianceRun, ApiError>({
    queryKey: queryKeys.compliance.run(id ?? ""),
    queryFn: () => complianceApi.getRun(id as number | string),
    enabled: id !== null && id !== undefined && id !== "",
    ...options,
  });
}

export function useStartComplianceRun(
  options?: UseMutationOptions<
    ComplianceRun,
    ApiError,
    { contractId: number | string; checklist_id: number | string }
  >,
) {
  const qc = useQueryClient();
  return useMutation<
    ComplianceRun,
    ApiError,
    { contractId: number | string; checklist_id: number | string }
  >({
    mutationFn: ({ contractId, checklist_id }) =>
      complianceApi.runForContract(contractId, { checklist_id }),
    ...options,
    onSuccess: (data, vars, ctx) => {
      qc.invalidateQueries({ queryKey: queryKeys.compliance.all });
      qc.invalidateQueries({
        queryKey: queryKeys.contracts.detail(vars.contractId),
      });
      options?.onSuccess?.(data, vars, ctx);
    },
  });
}
