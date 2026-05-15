"use client";

/**
 * Contracts TanStack Query hooks
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationOptions,
  type UseQueryOptions,
} from "@tanstack/react-query";

import { ApiError } from "@/lib/api/client";
import { contractsApi, type ContractListParams } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/query-keys";
import type {
  Clause,
  Contract,
  ContractCreate,
  ContractUpdate,
  Paginated,
  WorkflowStep,
} from "@/lib/api/schemas";

export function useContracts(
  params?: ContractListParams,
  options?: Omit<UseQueryOptions<Paginated<Contract>, ApiError>, "queryKey" | "queryFn">,
) {
  return useQuery<Paginated<Contract>, ApiError>({
    queryKey: queryKeys.contracts.list(params),
    queryFn: () => contractsApi.list(params),
    ...options,
  });
}

export function useContract(
  id: number | string | null | undefined,
  options?: Omit<UseQueryOptions<Contract, ApiError>, "queryKey" | "queryFn">,
) {
  return useQuery<Contract, ApiError>({
    queryKey: queryKeys.contracts.detail(id ?? ""),
    queryFn: () => contractsApi.get(id as number | string),
    enabled: id !== null && id !== undefined && id !== "",
    ...options,
  });
}

export function useContractClauses(
  id: number | string | null | undefined,
  options?: Omit<UseQueryOptions<Clause[], ApiError>, "queryKey" | "queryFn">,
) {
  return useQuery<Clause[], ApiError>({
    queryKey: queryKeys.contracts.clauses(id ?? ""),
    queryFn: () => contractsApi.clauses(id as number | string),
    enabled: id !== null && id !== undefined && id !== "",
    ...options,
  });
}

export function useContractWorkflowSteps(
  id: number | string | null | undefined,
  options?: Omit<UseQueryOptions<WorkflowStep[], ApiError>, "queryKey" | "queryFn">,
) {
  return useQuery<WorkflowStep[], ApiError>({
    queryKey: queryKeys.contracts.workflowSteps(id ?? ""),
    queryFn: () => contractsApi.workflowSteps(id as number | string),
    enabled: id !== null && id !== undefined && id !== "",
    ...options,
  });
}

export function useCreateContract(
  options?: UseMutationOptions<Contract, ApiError, ContractCreate>,
) {
  const qc = useQueryClient();
  return useMutation<Contract, ApiError, ContractCreate>({
    mutationFn: (data) => contractsApi.create(data),
    ...options,
    onSuccess: (data, vars, ctx) => {
      qc.invalidateQueries({ queryKey: queryKeys.contracts.lists() });
      qc.invalidateQueries({ queryKey: queryKeys.dashboard.all });
      options?.onSuccess?.(data, vars, ctx);
    },
  });
}

export function useUpdateContract(
  options?: UseMutationOptions<
    Contract,
    ApiError,
    { id: number | string; data: ContractUpdate }
  >,
) {
  const qc = useQueryClient();
  return useMutation<Contract, ApiError, { id: number | string; data: ContractUpdate }>({
    mutationFn: ({ id, data }) => contractsApi.update(id, data),
    ...options,
    onSuccess: (data, vars, ctx) => {
      qc.invalidateQueries({ queryKey: queryKeys.contracts.lists() });
      qc.invalidateQueries({ queryKey: queryKeys.contracts.detail(vars.id) });
      options?.onSuccess?.(data, vars, ctx);
    },
  });
}

export function useDeleteContract(
  options?: UseMutationOptions<void, ApiError, number | string>,
) {
  const qc = useQueryClient();
  return useMutation<void, ApiError, number | string>({
    mutationFn: (id) => contractsApi.delete(id),
    ...options,
    onSuccess: (data, id, ctx) => {
      qc.invalidateQueries({ queryKey: queryKeys.contracts.all });
      qc.invalidateQueries({ queryKey: queryKeys.dashboard.all });
      options?.onSuccess?.(data, id, ctx);
    },
  });
}

export function useSubmitContract(
  options?: UseMutationOptions<Contract, ApiError, number | string>,
) {
  const qc = useQueryClient();
  return useMutation<Contract, ApiError, number | string>({
    mutationFn: (id) => contractsApi.submit(id),
    ...options,
    onSuccess: (data, id, ctx) => {
      qc.invalidateQueries({ queryKey: queryKeys.contracts.detail(id) });
      qc.invalidateQueries({ queryKey: queryKeys.contracts.lists() });
      qc.invalidateQueries({ queryKey: queryKeys.workflows.all });
      options?.onSuccess?.(data, id, ctx);
    },
  });
}
