"use client";

/**
 * Workflows TanStack Query hooks
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationOptions,
  type UseQueryOptions,
} from "@tanstack/react-query";

import { ApiError } from "@/lib/api/client";
import { workflowsApi } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/query-keys";
import type { Paginated, Workflow, WorkflowStep } from "@/lib/api/schemas";

export function useWorkflows(
  params?: { page?: number; page_size?: number; q?: string },
  options?: Omit<UseQueryOptions<Paginated<Workflow>, ApiError>, "queryKey" | "queryFn">,
) {
  return useQuery<Paginated<Workflow>, ApiError>({
    queryKey: queryKeys.workflows.list(params),
    queryFn: () => workflowsApi.list(params),
    ...options,
  });
}

export function useWorkflow(
  id: number | string | null | undefined,
  options?: Omit<UseQueryOptions<Workflow, ApiError>, "queryKey" | "queryFn">,
) {
  return useQuery<Workflow, ApiError>({
    queryKey: queryKeys.workflows.detail(id ?? ""),
    queryFn: () => workflowsApi.get(id as number | string),
    enabled: id !== null && id !== undefined && id !== "",
    ...options,
  });
}

export function useCreateWorkflow(
  options?: UseMutationOptions<
    Workflow,
    ApiError,
    Parameters<typeof workflowsApi.create>[0]
  >,
) {
  const qc = useQueryClient();
  return useMutation<Workflow, ApiError, Parameters<typeof workflowsApi.create>[0]>({
    mutationFn: (data) => workflowsApi.create(data),
    ...options,
    onSuccess: (data, vars, ctx, fwCtx) => {
      qc.invalidateQueries({ queryKey: queryKeys.workflows.lists() });
      options?.onSuccess?.(data, vars, ctx, fwCtx);
    },
  });
}

export function useUpdateWorkflow(
  options?: UseMutationOptions<
    Workflow,
    ApiError,
    { id: number | string; data: Parameters<typeof workflowsApi.update>[1] }
  >,
) {
  const qc = useQueryClient();
  return useMutation<
    Workflow,
    ApiError,
    { id: number | string; data: Parameters<typeof workflowsApi.update>[1] }
  >({
    mutationFn: ({ id, data }) => workflowsApi.update(id, data),
    ...options,
    onSuccess: (data, vars, ctx, fwCtx) => {
      qc.invalidateQueries({ queryKey: queryKeys.workflows.detail(vars.id) });
      qc.invalidateQueries({ queryKey: queryKeys.workflows.lists() });
      options?.onSuccess?.(data, vars, ctx, fwCtx);
    },
  });
}

export function useDeleteWorkflow(
  options?: UseMutationOptions<void, ApiError, number | string>,
) {
  const qc = useQueryClient();
  return useMutation<void, ApiError, number | string>({
    mutationFn: (id) => workflowsApi.delete(id),
    ...options,
    onSuccess: (data, id, ctx, fwCtx) => {
      qc.invalidateQueries({ queryKey: queryKeys.workflows.all });
      options?.onSuccess?.(data, id, ctx, fwCtx);
    },
  });
}

// --- Step actions ----------------------------------------------------------

type StepInvalidators = (qc: ReturnType<typeof useQueryClient>) => void;
const invalidateWorkflowsAndContracts: StepInvalidators = (qc) => {
  qc.invalidateQueries({ queryKey: queryKeys.workflows.all });
  qc.invalidateQueries({ queryKey: queryKeys.contracts.all });
};

export function useApproveStep(
  options?: UseMutationOptions<
    WorkflowStep,
    ApiError,
    { stepId: number | string; comment?: string }
  >,
) {
  const qc = useQueryClient();
  return useMutation<
    WorkflowStep,
    ApiError,
    { stepId: number | string; comment?: string }
  >({
    mutationFn: ({ stepId, comment }) => workflowsApi.approveStep(stepId, comment),
    ...options,
    onSuccess: (data, vars, ctx, fwCtx) => {
      invalidateWorkflowsAndContracts(qc);
      options?.onSuccess?.(data, vars, ctx, fwCtx);
    },
  });
}

export function useRejectStep(
  options?: UseMutationOptions<
    WorkflowStep,
    ApiError,
    { stepId: number | string; comment: string }
  >,
) {
  const qc = useQueryClient();
  return useMutation<
    WorkflowStep,
    ApiError,
    { stepId: number | string; comment: string }
  >({
    mutationFn: ({ stepId, comment }) => workflowsApi.rejectStep(stepId, comment),
    ...options,
    onSuccess: (data, vars, ctx, fwCtx) => {
      invalidateWorkflowsAndContracts(qc);
      options?.onSuccess?.(data, vars, ctx, fwCtx);
    },
  });
}

export function useSendBackStep(
  options?: UseMutationOptions<
    WorkflowStep,
    ApiError,
    { stepId: number | string; toSeq: number; comment?: string }
  >,
) {
  const qc = useQueryClient();
  return useMutation<
    WorkflowStep,
    ApiError,
    { stepId: number | string; toSeq: number; comment?: string }
  >({
    mutationFn: ({ stepId, toSeq, comment }) =>
      workflowsApi.sendBackStep(stepId, toSeq, comment),
    ...options,
    onSuccess: (data, vars, ctx, fwCtx) => {
      invalidateWorkflowsAndContracts(qc);
      options?.onSuccess?.(data, vars, ctx, fwCtx);
    },
  });
}

export function useDelegateStep(
  options?: UseMutationOptions<
    WorkflowStep,
    ApiError,
    { stepId: number | string; toUserId: number | string; comment?: string }
  >,
) {
  const qc = useQueryClient();
  return useMutation<
    WorkflowStep,
    ApiError,
    { stepId: number | string; toUserId: number | string; comment?: string }
  >({
    mutationFn: ({ stepId, toUserId, comment }) =>
      workflowsApi.delegateStep(stepId, toUserId, comment),
    ...options,
    onSuccess: (data, vars, ctx, fwCtx) => {
      invalidateWorkflowsAndContracts(qc);
      options?.onSuccess?.(data, vars, ctx, fwCtx);
    },
  });
}
