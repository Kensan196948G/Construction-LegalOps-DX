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
import type { DashboardSummary, DashboardTrends } from "@/lib/api/schemas";

export function useDashboardSummary(
  params?: { department_id?: number | string },
  options?: Omit<UseQueryOptions<DashboardSummary, ApiError>, "queryKey" | "queryFn">,
) {
  return useQuery<DashboardSummary, ApiError>({
    queryKey: queryKeys.dashboard.summary(params),
    queryFn: () => dashboardApi.summary(params),
    staleTime: 60_000,
    ...options,
  });
}

export function useDashboardTrends(
  params?: { interval?: "week" | "month"; weeks?: number; department_id?: number | string },
  options?: Omit<UseQueryOptions<DashboardTrends, ApiError>, "queryKey" | "queryFn">,
) {
  return useQuery<DashboardTrends, ApiError>({
    queryKey: queryKeys.dashboard.trends(params),
    queryFn: () => dashboardApi.trends(params),
    staleTime: 60_000,
    ...options,
  });
}
