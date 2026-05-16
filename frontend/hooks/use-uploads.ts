"use client";

/**
 * Uploads TanStack Query hooks
 */

import {
  useMutation,
  useQueryClient,
  type UseMutationOptions,
} from "@tanstack/react-query";

import { ApiError } from "@/lib/api/client";
import { uploadsApi } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/query-keys";
import type { Attachment } from "@/lib/api/schemas";

export function useUploadFile(
  options?: UseMutationOptions<
    Attachment,
    ApiError,
    Parameters<typeof uploadsApi.upload>[0]
  >,
) {
  const qc = useQueryClient();
  return useMutation<Attachment, ApiError, Parameters<typeof uploadsApi.upload>[0]>({
    mutationFn: (params) => uploadsApi.upload(params),
    ...options,
    onSuccess: (data, vars, ctx, fwCtx) => {
      if (vars.contract_id !== undefined) {
        qc.invalidateQueries({
          queryKey: queryKeys.contracts.detail(vars.contract_id),
        });
      }
      qc.invalidateQueries({ queryKey: queryKeys.uploads.all });
      options?.onSuccess?.(data, vars, ctx, fwCtx);
    },
  });
}

export function useDeleteUpload(
  options?: UseMutationOptions<void, ApiError, number | string>,
) {
  const qc = useQueryClient();
  return useMutation<void, ApiError, number | string>({
    mutationFn: (id) => uploadsApi.delete(id),
    ...options,
    onSuccess: (data, id, ctx, fwCtx) => {
      qc.invalidateQueries({ queryKey: queryKeys.uploads.all });
      qc.invalidateQueries({ queryKey: queryKeys.contracts.all });
      options?.onSuccess?.(data, id, ctx, fwCtx);
    },
  });
}

/** ダウンロード URL を返すヘルパ (Query にしなくても良いユーティリティ) */
export function getUploadDownloadUrl(id: number | string): string {
  return uploadsApi.downloadUrl(id);
}
