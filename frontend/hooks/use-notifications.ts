"use client";

/**
 * Notifications TanStack Query hooks
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationOptions,
  type UseQueryOptions,
} from "@tanstack/react-query";

import { ApiError } from "@/lib/api/client";
import { notificationsApi, type NotificationListParams } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/query-keys";
import type { Notification, Paginated } from "@/lib/api/schemas";

export function useNotifications(
  params?: NotificationListParams,
  options?: Omit<
    UseQueryOptions<Paginated<Notification>, ApiError>,
    "queryKey" | "queryFn"
  >,
) {
  return useQuery<Paginated<Notification>, ApiError>({
    queryKey: queryKeys.notifications.list(params),
    queryFn: () => notificationsApi.list(params),
    ...options,
  });
}

export function useUnreadNotificationCount(
  options?: Omit<UseQueryOptions<number, ApiError>, "queryKey" | "queryFn">,
) {
  return useQuery<number, ApiError>({
    queryKey: queryKeys.notifications.unreadCount(),
    queryFn: () => notificationsApi.unreadCount(),
    // 30 秒ごとに backend に問い合わせる軽量ポーリング
    refetchInterval: 30_000,
    ...options,
  });
}

export function useMarkNotificationRead(
  options?: UseMutationOptions<void, ApiError, number | string>,
) {
  const qc = useQueryClient();
  return useMutation<void, ApiError, number | string>({
    mutationFn: (id) => notificationsApi.markAsRead(id),
    ...options,
    onSuccess: (data, id, ctx, fwCtx) => {
      qc.invalidateQueries({ queryKey: queryKeys.notifications.all });
      options?.onSuccess?.(data, id, ctx, fwCtx);
    },
  });
}
