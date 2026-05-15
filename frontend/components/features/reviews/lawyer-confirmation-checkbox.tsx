"use client";

import * as React from "react";
import { Check, ScaleIcon } from "lucide-react";

import { cn } from "@/components/lib/utils";

export interface LawyerConfirmationCheckboxProps {
  /** チェック状態 (制御モード) */
  checked?: boolean;
  /** デフォルト値 (非制御モード) */
  defaultChecked?: boolean;
  onCheckedChange?: (next: boolean) => void;
  /** react-hook-form の register 連携用 */
  name?: string;
  id?: string;
  disabled?: boolean;
  required?: boolean;
  /** 確認者名の表示 (任意) */
  confirmedBy?: string;
  /** 確認日時の ISO 文字列 */
  confirmedAt?: string;
  className?: string;
}

/**
 * 「弁護士確認済み」チェックボックス。
 * react-hook-form の Controller / register 双方から扱えるよう、
 * ネイティブ <input type="checkbox"> をベースに装飾しています。
 */
export const LawyerConfirmationCheckbox = React.forwardRef<
  HTMLInputElement,
  LawyerConfirmationCheckboxProps
>(function LawyerConfirmationCheckbox(
  {
    checked,
    defaultChecked,
    onCheckedChange,
    name,
    id,
    disabled = false,
    required = false,
    confirmedBy,
    confirmedAt,
    className,
  },
  ref
) {
  const reactId = React.useId();
  const inputId = id ?? reactId;
  const isControlled = typeof checked === "boolean";
  const [internal, setInternal] = React.useState(defaultChecked ?? false);
  const current = isControlled ? checked! : internal;

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const next = e.target.checked;
    if (!isControlled) setInternal(next);
    onCheckedChange?.(next);
  };

  return (
    <label
      htmlFor={inputId}
      className={cn(
        "flex cursor-pointer items-start gap-3 rounded-md border bg-card p-3 transition-colors",
        current
          ? "border-emerald-400 bg-emerald-50 dark:bg-emerald-950/30"
          : "hover:bg-accent",
        disabled && "cursor-not-allowed opacity-60",
        className
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded border bg-background transition-colors",
          current
            ? "border-emerald-500 bg-emerald-500 text-white"
            : "border-input"
        )}
      >
        {current && <Check className="h-3.5 w-3.5" />}
      </span>

      <input
        ref={ref}
        id={inputId}
        type="checkbox"
        name={name}
        checked={isControlled ? current : undefined}
        defaultChecked={isControlled ? undefined : defaultChecked}
        onChange={handleChange}
        disabled={disabled}
        required={required}
        className="sr-only"
      />

      <span className="flex flex-1 flex-col">
        <span className="flex items-center gap-1.5 text-sm font-medium">
          <ScaleIcon className="h-3.5 w-3.5 text-emerald-600" aria-hidden="true" />
          弁護士確認済み
          {required && (
            <span className="text-xs text-destructive" aria-hidden="true">
              *
            </span>
          )}
        </span>
        <span className="text-xs text-muted-foreground">
          AI による提案・分析結果を、法務担当者または顧問弁護士が確認しました。
        </span>
        {(confirmedBy || confirmedAt) && current && (
          <span className="mt-1 text-xs text-muted-foreground">
            {confirmedBy && <>確認者: {confirmedBy} </>}
            {confirmedAt && <>/ {confirmedAt}</>}
          </span>
        )}
      </span>
    </label>
  );
});

export default LawyerConfirmationCheckbox;
