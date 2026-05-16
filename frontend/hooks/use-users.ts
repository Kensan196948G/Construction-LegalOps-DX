"use client";

/**
 * Users TanStack Query hooks (auth/me 含む)
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationOptions,
  type UseQueryOptions,
} from "@tanstack/react-query";

import { ApiError } from "@/lib/api/client";
import { authApi, usersApi, type UserListParams } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/query-keys";
import type { Paginated, User } from "@/lib/api/schemas";

// --- /auth/me --------------------------------------------------------------

export function useCurrentUser(
  options?: Omit<UseQueryOptions<User, ApiError>, "queryKey" | "queryFn">,
) {
  return useQuery<User, ApiError>({
    queryKey: queryKeys.auth.me(),
    queryFn: () => authApi.me(),
    staleTime: 5 * 60_000,
    ...options,
  });
}

// --- /users ----------------------------------------------------------------

export function useUsers(
  params?: UserListParams,
  options?: Omit<UseQueryOptions<Paginated<User>, ApiError>, "queryKey" | "queryFn">,
) {
  return useQuery<Paginated<User>, ApiError>({
    queryKey: queryKeys.users.list(params),
    queryFn: () => usersApi.list(params),
    ...options,
  });
}

export function useUser(
  id: number | string | null | undefined,
  options?: Omit<UseQueryOptions<User, ApiError>, "queryKey" | "queryFn">,
) {
  return useQuery<User, ApiError>({
    queryKey: queryKeys.users.detail(id ?? ""),
    queryFn: () => usersApi.get(id as number | string),
    enabled: id !== null && id !== undefined && id !== "",
    ...options,
  });
}

export function useUpdateUser(
  options?: UseMutationOptions<
    User,
    ApiError,
    { id: number | string; data: Parameters<typeof usersApi.update>[1] }
  >,
) {
  const qc = useQueryClient();
  return useMutation<
    User,
    ApiError,
    { id: number | string; data: Parameters<typeof usersApi.update>[1] }
  >({
    mutationFn: ({ id, data }) => usersApi.update(id, data),
    ...options,
    onSuccess: (data, vars, ctx, fwCtx) => {
      qc.invalidateQueries({ queryKey: queryKeys.users.detail(vars.id) });
      qc.invalidateQueries({ queryKey: queryKeys.users.lists() });
      options?.onSuccess?.(data, vars, ctx, fwCtx);
    },
  });
}

export function useSyncUsers(
  options?: UseMutationOptions<{ job_id: string }, ApiError, void>,
) {
  const qc = useQueryClient();
  return useMutation<{ job_id: string }, ApiError, void>({
    mutationFn: () => usersApi.sync(),
    ...options,
    onSuccess: (data, vars, ctx, fwCtx) => {
      qc.invalidateQueries({ queryKey: queryKeys.users.all });
      options?.onSuccess?.(data, vars, ctx, fwCtx);
    },
  });
}
