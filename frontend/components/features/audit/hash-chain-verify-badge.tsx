import * as React from "react";
import { ShieldCheck, ShieldAlert, ShieldQuestion } from "lucide-react";

import { cn } from "@/components/lib/utils";
import { Badge } from "@/components/ui/badge";

export type HashChainState =
  | "verified"
  | "tampered"
  | "pending"
  | "unverified";

export interface HashChainVerifyBadgeProps
  extends React.HTMLAttributes<HTMLDivElement> {
  state: HashChainState;
  /** 検証時刻 (任意) */
  verifiedAt?: string;
  /** 詳細表示 (ハッシュ値の先頭部分など) */
  hashPreview?: string;
}

const META: Record<
  HashChainState,
  {
    label: string;
    icon: React.ComponentType<{ className?: string }>;
    className: string;
  }
> = {
  verified: {
    label: "改ざんなし",
    icon: ShieldCheck,
    className:
      "border-transparent bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-100",
  },
  tampered: {
    label: "改ざん検知",
    icon: ShieldAlert,
    className:
      "border-transparent bg-rose-100 text-rose-900 dark:bg-rose-900/40 dark:text-rose-100",
  },
  pending: {
    label: "検証中",
    icon: ShieldQuestion,
    className:
      "border-transparent bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-100",
  },
  unverified: {
    label: "未検証",
    icon: ShieldQuestion,
    className:
      "border-transparent bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200",
  },
};

export function HashChainVerifyBadge({
  state,
  verifiedAt,
  hashPreview,
  className,
  ...props
}: HashChainVerifyBadgeProps) {
  const meta = META[state];
  const Icon = meta.icon;
  return (
    <div
      className={cn("inline-flex items-center gap-2", className)}
      title={
        hashPreview
          ? `hash: ${hashPreview}${verifiedAt ? ` / ${verifiedAt}` : ""}`
          : verifiedAt
      }
      {...props}
    >
      <Badge className={cn("gap-1 px-2 py-0.5", meta.className)}>
        <Icon className="h-3 w-3" aria-hidden="true" />
        {meta.label}
      </Badge>
      {hashPreview && (
        <code className="font-mono text-[10px] text-muted-foreground">
          {hashPreview}
        </code>
      )}
    </div>
  );
}

export default HashChainVerifyBadge;
