"use client";

/**
 * Templates / Clause library TanStack Query hooks
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationOptions,
  type UseQueryOptions,
} from "@tanstack/react-query";

import { ApiError } from "@/lib/api/client";
import { templatesApi } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/query-keys";
import type {
  ClauseLibraryEntry,
  Paginated,
  Template,
} from "@/lib/api/schemas";

export function useTemplates(
  params?: { page?: number; page_size?: number; q?: string; contract_type?: string },
  options?: Omit<UseQueryOptions<Paginated<Template>, ApiError>, "queryKey" | "queryFn">,
) {
  return useQuery<Paginated<Template>, ApiError>({
    queryKey: queryKeys.templates.list(params),
    queryFn: () => templatesApi.list(params),
    ...options,
  });
}

export function useTemplate(
  id: number | string | null | undefined,
  options?: Omit<UseQueryOptions<Template, ApiError>, "queryKey" | "queryFn">,
) {
  return useQuery<Template, ApiError>({
    queryKey: queryKeys.templates.detail(id ?? ""),
    queryFn: () => templatesApi.get(id as number | string),
    enabled: id !== null && id !== undefined && id !== "",
    ...options,
  });
}

export function useCreateTemplate(
  options?: UseMutationOptions<
    Template,
    ApiError,
    Parameters<typeof templatesApi.create>[0]
  >,
) {
  const qc = useQueryClient();
  return useMutation<Template, ApiError, Parameters<typeof templatesApi.create>[0]>({
    mutationFn: (data) => templatesApi.create(data),
    ...options,
    onSuccess: (data, vars, ctx, fwCtx) => {
      qc.invalidateQueries({ queryKey: queryKeys.templates.lists() });
      options?.onSuccess?.(data, vars, ctx, fwCtx);
    },
  });
}

export function useUpdateTemplate(
  options?: UseMutationOptions<
    Template,
    ApiError,
    { id: number | string; data: Parameters<typeof templatesApi.update>[1] }
  >,
) {
  const qc = useQueryClient();
  return useMutation<
    Template,
    ApiError,
    { id: number | string; data: Parameters<typeof templatesApi.update>[1] }
  >({
    mutationFn: ({ id, data }) => templatesApi.update(id, data),
    ...options,
    onSuccess: (data, vars, ctx, fwCtx) => {
      qc.invalidateQueries({ queryKey: queryKeys.templates.detail(vars.id) });
      qc.invalidateQueries({ queryKey: queryKeys.templates.lists() });
      options?.onSuccess?.(data, vars, ctx, fwCtx);
    },
  });
}

export function useDeleteTemplate(
  options?: UseMutationOptions<void, ApiError, number | string>,
) {
  const qc = useQueryClient();
  return useMutation<void, ApiError, number | string>({
    mutationFn: (id) => templatesApi.delete(id),
    ...options,
    onSuccess: (data, id, ctx, fwCtx) => {
      qc.invalidateQueries({ queryKey: queryKeys.templates.all });
      options?.onSuccess?.(data, id, ctx, fwCtx);
    },
  });
}

// --- Clause library --------------------------------------------------------

export function useClauseLibrary(
  params?: {
    page?: number;
    page_size?: number;
    q?: string;
    category?: string;
    tag?: string;
    recommendation?: string;
  },
  options?: Omit<
    UseQueryOptions<Paginated<ClauseLibraryEntry>, ApiError>,
    "queryKey" | "queryFn"
  >,
) {
  return useQuery<Paginated<ClauseLibraryEntry>, ApiError>({
    queryKey: queryKeys.templates.clauseLibrary(params),
    queryFn: () => templatesApi.clauseLibraryList(params),
    ...options,
  });
}

export function useCreateClauseLibraryEntry(
  options?: UseMutationOptions<
    ClauseLibraryEntry,
    ApiError,
    Parameters<typeof templatesApi.clauseLibraryCreate>[0]
  >,
) {
  const qc = useQueryClient();
  return useMutation<
    ClauseLibraryEntry,
    ApiError,
    Parameters<typeof templatesApi.clauseLibraryCreate>[0]
  >({
    mutationFn: (data) => templatesApi.clauseLibraryCreate(data),
    ...options,
    onSuccess: (data, vars, ctx, fwCtx) => {
      qc.invalidateQueries({ queryKey: queryKeys.templates.all });
      options?.onSuccess?.(data, vars, ctx, fwCtx);
    },
  });
}
