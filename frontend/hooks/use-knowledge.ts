"use client";

/**
 * Knowledge TanStack Query hooks
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationOptions,
  type UseQueryOptions,
} from "@tanstack/react-query";

import { ApiError } from "@/lib/api/client";
import { knowledgeApi } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/query-keys";
import type { KnowledgeArticle, Paginated } from "@/lib/api/schemas";

export function useKnowledgeArticles(
  params?: { page?: number; page_size?: number; q?: string; tag?: string },
  options?: Omit<
    UseQueryOptions<Paginated<KnowledgeArticle>, ApiError>,
    "queryKey" | "queryFn"
  >,
) {
  return useQuery<Paginated<KnowledgeArticle>, ApiError>({
    queryKey: queryKeys.knowledge.list(params),
    queryFn: () => knowledgeApi.list(params),
    ...options,
  });
}

export function useKnowledgeArticle(
  id: number | string | null | undefined,
  options?: Omit<UseQueryOptions<KnowledgeArticle, ApiError>, "queryKey" | "queryFn">,
) {
  return useQuery<KnowledgeArticle, ApiError>({
    queryKey: queryKeys.knowledge.detail(id ?? ""),
    queryFn: () => knowledgeApi.get(id as number | string),
    enabled: id !== null && id !== undefined && id !== "",
    ...options,
  });
}

export function useCreateKnowledgeArticle(
  options?: UseMutationOptions<
    KnowledgeArticle,
    ApiError,
    Parameters<typeof knowledgeApi.create>[0]
  >,
) {
  const qc = useQueryClient();
  return useMutation<
    KnowledgeArticle,
    ApiError,
    Parameters<typeof knowledgeApi.create>[0]
  >({
    mutationFn: (data) => knowledgeApi.create(data),
    ...options,
    onSuccess: (data, vars, ctx) => {
      qc.invalidateQueries({ queryKey: queryKeys.knowledge.lists() });
      options?.onSuccess?.(data, vars, ctx);
    },
  });
}

export function useUpdateKnowledgeArticle(
  options?: UseMutationOptions<
    KnowledgeArticle,
    ApiError,
    { id: number | string; data: Parameters<typeof knowledgeApi.update>[1] }
  >,
) {
  const qc = useQueryClient();
  return useMutation<
    KnowledgeArticle,
    ApiError,
    { id: number | string; data: Parameters<typeof knowledgeApi.update>[1] }
  >({
    mutationFn: ({ id, data }) => knowledgeApi.update(id, data),
    ...options,
    onSuccess: (data, vars, ctx) => {
      qc.invalidateQueries({ queryKey: queryKeys.knowledge.detail(vars.id) });
      qc.invalidateQueries({ queryKey: queryKeys.knowledge.lists() });
      options?.onSuccess?.(data, vars, ctx);
    },
  });
}

export function useDeleteKnowledgeArticle(
  options?: UseMutationOptions<void, ApiError, number | string>,
) {
  const qc = useQueryClient();
  return useMutation<void, ApiError, number | string>({
    mutationFn: (id) => knowledgeApi.delete(id),
    ...options,
    onSuccess: (data, id, ctx) => {
      qc.invalidateQueries({ queryKey: queryKeys.knowledge.all });
      options?.onSuccess?.(data, id, ctx);
    },
  });
}
