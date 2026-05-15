import * as React from "react";
import { AlertTriangle } from "lucide-react";

import { cn } from "@/components/lib/utils";

export interface AiDisclaimerBannerProps
  extends React.HTMLAttributes<HTMLDivElement> {
  /** 表示形式: 'banner' は固定バナー、'inline' は控えめなインライン文 */
  variant?: "banner" | "inline";
}

/**
 * AI 法的判断回避用の免責バナー。
 * AI 出力を画面に表示するすべてのレイアウト・コンポーネントに併設する。
 */
export function AiDisclaimerBanner({
  className,
  variant = "banner",
  ...props
}: AiDisclaimerBannerProps) {
  if (variant === "inline") {
    return (
      <p
        role="note"
        className={cn(
          "text-xs text-muted-foreground",
          "flex items-start gap-1.5",
          className
        )}
        {...props}
      >
        <AlertTriangle
          className="mt-[2px] h-3.5 w-3.5 shrink-0 text-amber-500"
          aria-hidden="true"
        />
        <span>
          AI は法的判断を確定しません。最終判断は法務担当者・顧問弁護士が行います。
        </span>
      </p>
    );
  }

  return (
    <div
      role="note"
      aria-label="AI 利用に関する免責"
      className={cn(
        "flex items-start gap-3 border-b border-amber-300 bg-amber-50 px-4 py-2.5 text-amber-900 dark:border-amber-700/50 dark:bg-amber-950/40 dark:text-amber-100",
        className
      )}
      {...props}
    >
      <AlertTriangle
        className="mt-0.5 h-4 w-4 shrink-0 text-amber-600 dark:text-amber-300"
        aria-hidden="true"
      />
      <p className="text-sm leading-snug">
        <strong className="font-semibold">
          AI は法的判断を確定しません。
        </strong>
        最終判断は法務担当者・顧問弁護士が行います。本システムの AI 出力は参考情報であり、法的助言を構成するものではありません。
      </p>
    </div>
  );
}

export default AiDisclaimerBanner;
