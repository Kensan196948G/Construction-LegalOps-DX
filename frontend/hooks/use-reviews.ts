"use client";

/**
 * Legal reviews TanStack Query hooks
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationOptions,
  type UseQueryOptions,
} from "@tanstack/react-query";

import { ApiError } from "@/lib/api/client";
import { reviewsApi, type ReviewListParams } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/query-keys";
import type { LegalReview, Paginated, ReviewCreate } from "@/lib/api/schemas";

export function useReviews(
  params?: ReviewListParams,
  options?: Omit<UseQueryOptions<Paginated<LegalReview>, ApiError>, "queryKey" | "queryFn">,
) {
  return useQuery<Paginated<LegalReview>, ApiError>({
    queryKey: queryKeys.reviews.list(params),
    queryFn: () => reviewsApi.list(params),
    ...options,
  });
}

export function useReview(
  id: number | string | null | undefined,
  options?: Omit<UseQueryOptions<LegalReview, ApiError>, "queryKey" | "queryFn">,
) {
  return useQuery<LegalReview, ApiError>({
    queryKey: queryKeys.reviews.detail(id ?? ""),
    queryFn: () => reviewsApi.get(id as number | string),
    enabled: id !== null && id !== undefined && id !== "",
    ...options,
  });
}

export function useStartReview(
  options?: UseMutationOptions<
    LegalReview,
    ApiError,
    { contractId: number | string; data: ReviewCreate }
  >,
) {
  const qc = useQueryClient();
  return useMutation<
    LegalReview,
    ApiError,
    { contractId: number | string; data: ReviewCreate }
  >({
    mutationFn: ({ contractId, data }) =>
      reviewsApi.startForContract(contractId, data),
    ...options,
    onSuccess: (data, vars, ctx, fwCtx) => {
      qc.invalidateQueries({ queryKey: queryKeys.reviews.lists() });
      qc.invalidateQueries({
        queryKey: queryKeys.contracts.detail(vars.contractId),
      });
      options?.onSuccess?.(data, vars, ctx, fwCtx);
    },
  });
}

export function useAcceptReview(
  options?: UseMutationOptions<LegalReview, ApiError, number | string>,
) {
  const qc = useQueryClient();
  return useMutation<LegalReview, ApiError, number | string>({
    mutationFn: (id) => reviewsApi.accept(id),
    ...options,
    onSuccess: (data, id, ctx, fwCtx) => {
      qc.invalidateQueries({ queryKey: queryKeys.reviews.detail(id) });
      qc.invalidateQueries({ queryKey: queryKeys.reviews.lists() });
      qc.invalidateQueries({ queryKey: queryKeys.contracts.all });
      options?.onSuccess?.(data, id, ctx, fwCtx);
    },
  });
}

export function useRejectReview(
  options?: UseMutationOptions<
    LegalReview,
    ApiError,
    { id: number | string; reason: string }
  >,
) {
  const qc = useQueryClient();
  return useMutation<
    LegalReview,
    ApiError,
    { id: number | string; reason: string }
  >({
    mutationFn: ({ id, reason }) => reviewsApi.reject(id, reason),
    ...options,
    onSuccess: (data, vars, ctx, fwCtx) => {
      qc.invalidateQueries({ queryKey: queryKeys.reviews.detail(vars.id) });
      qc.invalidateQueries({ queryKey: queryKeys.reviews.lists() });
      options?.onSuccess?.(data, vars, ctx, fwCtx);
    },
  });
}
