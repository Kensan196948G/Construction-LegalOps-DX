import * as React from "react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/components/lib/utils";

export type ContractStatus =
  | "draft"
  | "in_review"
  | "approved"
  | "expired"
  | "archived";

const STATUS_META: Record<
  ContractStatus,
  { label: string; className: string }
> = {
  draft: {
    label: "下書き",
    className:
      "bg-slate-100 text-slate-700 hover:bg-slate-100 dark:bg-slate-800 dark:text-slate-200",
  },
  in_review: {
    label: "レビュー中",
    className:
      "bg-amber-100 text-amber-900 hover:bg-amber-100 dark:bg-amber-900/40 dark:text-amber-100",
  },
  approved: {
    label: "承認済み",
    className:
      "bg-emerald-100 text-emerald-900 hover:bg-emerald-100 dark:bg-emerald-900/40 dark:text-emerald-100",
  },
  expired: {
    label: "期限切れ",
    className:
      "bg-rose-100 text-rose-900 hover:bg-rose-100 dark:bg-rose-900/40 dark:text-rose-100",
  },
  archived: {
    label: "アーカイブ",
    className:
      "bg-zinc-100 text-zinc-600 hover:bg-zinc-100 dark:bg-zinc-800 dark:text-zinc-300",
  },
};

export interface ContractStatusBadgeProps
  extends React.HTMLAttributes<HTMLDivElement> {
  status: ContractStatus;
}

export function ContractStatusBadge({
  status,
  className,
  ...props
}: ContractStatusBadgeProps) {
  const meta = STATUS_META[status] ?? STATUS_META.draft;
  return (
    <Badge
      variant="secondary"
      className={cn("border-transparent", meta.className, className)}
      {...props}
    >
      {meta.label}
    </Badge>
  );
}

export default ContractStatusBadge;
