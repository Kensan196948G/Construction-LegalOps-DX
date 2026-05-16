"use client";

/**
 * Risks TanStack Query hooks
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationOptions,
  type UseQueryOptions,
} from "@tanstack/react-query";

import { ApiError } from "@/lib/api/client";
import { risksApi, type RiskListParams } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/query-keys";
import type {
  Paginated,
  RiskHeatmap,
  RiskItem,
  RiskUpdate,
} from "@/lib/api/schemas";

export function useRisks(
  params?: RiskListParams,
  options?: Omit<UseQueryOptions<Paginated<RiskItem>, ApiError>, "queryKey" | "queryFn">,
) {
  return useQuery<Paginated<RiskItem>, ApiError>({
    queryKey: queryKeys.risks.list(params),
    queryFn: () => risksApi.list(params),
    ...options,
  });
}

export function useRisk(
  id: number | string | null | undefined,
  options?: Omit<UseQueryOptions<RiskItem, ApiError>, "queryKey" | "queryFn">,
) {
  return useQuery<RiskItem, ApiError>({
    queryKey: queryKeys.risks.detail(id ?? ""),
    queryFn: () => risksApi.get(id as number | string),
    enabled: id !== null && id !== undefined && id !== "",
    ...options,
  });
}

export function useRiskHeatmap(
  options?: Omit<UseQueryOptions<RiskHeatmap, ApiError>, "queryKey" | "queryFn">,
) {
  return useQuery<RiskHeatmap, ApiError>({
    queryKey: queryKeys.risks.heatmap(),
    queryFn: () => risksApi.heatmap(),
    ...options,
  });
}

export function useUpdateRisk(
  options?: UseMutationOptions<
    RiskItem,
    ApiError,
    { id: number | string; data: RiskUpdate }
  >,
) {
  const qc = useQueryClient();
  return useMutation<RiskItem, ApiError, { id: number | string; data: RiskUpdate }>({
    mutationFn: ({ id, data }) => risksApi.update(id, data),
    ...options,
    onSuccess: (data, vars, ctx, fwCtx) => {
      qc.invalidateQueries({ queryKey: queryKeys.risks.all });
      qc.invalidateQueries({ queryKey: queryKeys.dashboard.all });
      options?.onSuccess?.(data, vars, ctx, fwCtx);
    },
  });
}

// Risks にはサーバー側で `create` / `delete` の標準エンドポイントが無いため hook も提供しない。
