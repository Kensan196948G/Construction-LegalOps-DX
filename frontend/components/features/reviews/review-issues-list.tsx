import * as React from "react";
import { AlertOctagon, AlertTriangle, Info, ShieldCheck } from "lucide-react";

import { cn } from "@/components/lib/utils";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AiDisclaimerBanner } from "@/components/layout/ai-disclaimer-banner";

export type ReviewIssueSeverity = "critical" | "high" | "medium" | "low" | "info";

export interface ReviewIssue {
  id: string;
  severity: ReviewIssueSeverity;
  title: string;
  description?: string;
  /** 契約書内の参照箇所 (条項番号など) */
  clauseRef?: string;
  category?: string;
}

const SEVERITY_META: Record<
  ReviewIssueSeverity,
  {
    label: string;
    icon: React.ComponentType<{ className?: string }>;
    tone: string;
    bar: string;
  }
> = {
  critical: {
    label: "重大",
    icon: AlertOctagon,
    tone: "text-rose-700 dark:text-rose-300",
    bar: "bg-rose-500",
  },
  high: {
    label: "高",
    icon: AlertTriangle,
    tone: "text-orange-700 dark:text-orange-300",
    bar: "bg-orange-500",
  },
  medium: {
    label: "中",
    icon: AlertTriangle,
    tone: "text-amber-700 dark:text-amber-300",
    bar: "bg-amber-500",
  },
  low: {
    label: "低",
    icon: Info,
    tone: "text-sky-700 dark:text-sky-300",
    bar: "bg-sky-500",
  },
  info: {
    label: "情報",
    icon: ShieldCheck,
    tone: "text-slate-700 dark:text-slate-300",
    bar: "bg-slate-400",
  },
};

export interface ReviewIssuesListProps
  extends React.HTMLAttributes<HTMLDivElement> {
  issues: ReviewIssue[];
  title?: string;
  description?: string;
}

export function ReviewIssuesList({
  issues,
  title = "AI が検出した論点",
  description,
  className,
  ...props
}: ReviewIssuesListProps) {
  return (
    <Card className={cn(className)} {...props}>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <AiDisclaimerBanner variant="inline" />

        {issues.length === 0 ? (
          <p className="rounded-md border border-dashed py-8 text-center text-sm text-muted-foreground">
            検出された論点はありません。
          </p>
        ) : (
          <ul className="flex flex-col gap-3" aria-label="検出論点一覧">
            {issues.map((issue) => {
              const meta = SEVERITY_META[issue.severity];
              const Icon = meta.icon;
              return (
                <li
                  key={issue.id}
                  className="relative overflow-hidden rounded-md border bg-card"
                >
                  <span
                    aria-hidden="true"
                    className={cn(
                      "absolute inset-y-0 left-0 w-1",
                      meta.bar
                    )}
                  />
                  <div className="flex gap-3 p-4 pl-5">
                    <Icon
                      className={cn("mt-0.5 h-4 w-4 shrink-0", meta.tone)}
                      aria-hidden="true"
                    />
                    <div className="flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h4 className="text-sm font-semibold">{issue.title}</h4>
                        <Badge
                          variant="outline"
                          className={cn("border-transparent text-xs", meta.tone)}
                        >
                          {meta.label}
                        </Badge>
                        {issue.category && (
                          <Badge variant="secondary" className="text-xs">
                            {issue.category}
                          </Badge>
                        )}
                        {issue.clauseRef && (
                          <span className="font-mono text-xs text-muted-foreground">
                            {issue.clauseRef}
                          </span>
                        )}
                      </div>
                      {issue.description && (
                        <p className="mt-1 text-sm text-muted-foreground">
                          {issue.description}
                        </p>
                      )}
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

export default ReviewIssuesList;
