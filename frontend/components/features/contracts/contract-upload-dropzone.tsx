"use client";

import * as React from "react";
import { useDropzone, type FileRejection } from "react-dropzone";
import { FileUp, FileText, X } from "lucide-react";

import { cn } from "@/components/lib/utils";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

export const CONTRACT_ACCEPT = {
  "application/pdf": [".pdf"],
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [
    ".docx",
  ],
  "application/msword": [".doc"],
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [
    ".xlsx",
  ],
  "application/vnd.ms-excel": [".xls"],
};

const DEFAULT_MAX_SIZE = 50 * 1024 * 1024; // 50 MB
const DEFAULT_MAX_FILES = 10;

export interface ContractUploadDropzoneProps {
  /** 受領済みファイル一覧 (制御モード) */
  value?: File[];
  onChange?: (files: File[]) => void;
  /** 1 ファイルあたりの最大バイト数 */
  maxSize?: number;
  /** 同時アップロード上限 */
  maxFiles?: number;
  disabled?: boolean;
  className?: string;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function ContractUploadDropzone({
  value,
  onChange,
  maxSize = DEFAULT_MAX_SIZE,
  maxFiles = DEFAULT_MAX_FILES,
  disabled = false,
  className,
}: ContractUploadDropzoneProps) {
  const [internal, setInternal] = React.useState<File[]>([]);
  const [rejected, setRejected] = React.useState<FileRejection[]>([]);
  const isControlled = value !== undefined;
  const files = isControlled ? value! : internal;

  const update = React.useCallback(
    (next: File[]) => {
      if (!isControlled) setInternal(next);
      onChange?.(next);
    },
    [isControlled, onChange]
  );

  const onDrop = React.useCallback(
    (accepted: File[], rejections: FileRejection[]) => {
      setRejected(rejections);
      if (accepted.length === 0) return;
      const dedup = [...files];
      for (const f of accepted) {
        if (!dedup.find((x) => x.name === f.name && x.size === f.size)) {
          dedup.push(f);
        }
      }
      update(dedup.slice(0, maxFiles));
    },
    [files, maxFiles, update]
  );

  const { getRootProps, getInputProps, isDragActive, isDragReject } =
    useDropzone({
      onDrop,
      accept: CONTRACT_ACCEPT,
      maxSize,
      maxFiles,
      disabled,
    });

  const remove = (idx: number) => {
    update(files.filter((_, i) => i !== idx));
  };

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      <div
        {...getRootProps()}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-input bg-card px-6 py-10 text-center transition-colors",
          isDragActive && "border-primary bg-primary/5",
          isDragReject && "border-destructive bg-destructive/5",
          disabled && "cursor-not-allowed opacity-60"
        )}
        aria-label="契約書ファイルをドロップ"
      >
        <input {...getInputProps()} />
        <FileUp className="h-8 w-8 text-muted-foreground" aria-hidden="true" />
        <p className="text-sm font-medium">
          {isDragActive
            ? "ここにドロップしてください"
            : "ファイルをドラッグ&ドロップ または クリックして選択"}
        </p>
        <p className="text-xs text-muted-foreground">
          対応形式: PDF / DOCX / XLSX(DOC, XLS 含む) ・ 最大 {formatBytes(maxSize)} / 同時 {maxFiles} 件
        </p>
      </div>

      {rejected.length > 0 && (
        <Alert variant="destructive">
          <AlertTitle>アップロードできなかったファイルがあります</AlertTitle>
          <AlertDescription>
            <ul className="mt-1 list-disc pl-4 text-sm">
              {rejected.map(({ file, errors }) => (
                <li key={file.name}>
                  {file.name}: {errors.map((e) => e.message).join(" / ")}
                </li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}

      {files.length > 0 && (
        <ul className="flex flex-col gap-2" aria-label="アップロード予定のファイル">
          {files.map((file, idx) => (
            <li
              key={`${file.name}-${idx}`}
              className="flex items-center justify-between rounded-md border bg-background px-3 py-2"
            >
              <div className="flex min-w-0 items-center gap-2">
                <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{file.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {formatBytes(file.size)}
                  </p>
                </div>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => remove(idx)}
                aria-label={`${file.name} を削除`}
              >
                <X className="h-4 w-4" />
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default ContractUploadDropzone;
