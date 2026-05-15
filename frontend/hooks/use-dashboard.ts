"use client";

/**
 * Dashboard TanStack Query hooks
 */

import {
  useQuery,
  type UseQueryOptions,
} from "@tanstack/react-query";

import { ApiError } from "@/lib/api/client";
import { dashboardApi } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/query-keys";
import type { DashboardKpis, DashboardTimeseries } from "@/lib/api/schemas";

export function useDashboardKpis(
  options?: Omit<UseQueryOptions<DashboardKpis, ApiError>, "queryKey" | "queryFn">,
) {
  return useQuery<DashboardKpis, ApiError>({
    queryKey: queryKeys.dashboard.kpis(),
    queryFn: () => dashboardApi.kpis(),
    staleTime: 60_000,
    ...options,
  });
}

export function useDashboardTimeseries(
  metric: string,
  params?: { from?: string; to?: string },
  options?: Omit<UseQueryOptions<DashboardTimeseries, ApiError>, "queryKey" | "queryFn">,
) {
  return useQuery<DashboardTimeseries, ApiError>({
    queryKey: queryKeys.dashboard.timeseries(metric, params),
    queryFn: () => dashboardApi.timeseries(metric, params),
    staleTime: 60_000,
    ...options,
  });
}
