import * as React from "react";
import { ShieldAlert, TrendingDown, TrendingUp, Minus } from "lucide-react";

import { cn } from "@/components/lib/utils";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { AiDisclaimerBanner } from "@/components/layout/ai-disclaimer-banner";

export type RiskLevel = "low" | "medium" | "high" | "critical";

export interface RiskScoreCardProps extends React.HTMLAttributes<HTMLDivElement> {
  /** 0-100 のリスクスコア (高いほど危険) */
  score: number;
  /** 前回比 (% で増減) */
  trend?: number;
  title?: string;
  description?: string;
  /** AI 由来かどうかを示し、true の場合は免責文を出す */
  aiGenerated?: boolean;
}

function scoreToLevel(score: number): RiskLevel {
  if (score >= 80) return "critical";
  if (score >= 60) return "high";
  if (score >= 30) return "medium";
  return "low";
}

const LEVEL_META: Record<
  RiskLevel,
  { label: string; tone: string; bar: string }
> = {
  low: {
    label: "低リスク",
    tone: "text-emerald-700 dark:text-emerald-300",
    bar: "bg-emerald-500",
  },
  medium: {
    label: "中リスク",
    tone: "text-amber-700 dark:text-amber-300",
    bar: "bg-amber-500",
  },
  high: {
    label: "高リスク",
    tone: "text-orange-700 dark:text-orange-300",
    bar: "bg-orange-500",
  },
  critical: {
    label: "重大リスク",
    tone: "text-rose-700 dark:text-rose-300",
    bar: "bg-rose-500",
  },
};

export function RiskScoreCard({
  score,
  trend,
  title = "リスクスコア",
  description,
  aiGenerated = true,
  className,
  ...props
}: RiskScoreCardProps) {
  const clamped = Math.max(0, Math.min(100, Math.round(score)));
  const level = scoreToLevel(clamped);
  const meta = LEVEL_META[level];

  const TrendIcon =
    trend == null ? Minus : trend > 0 ? TrendingUp : trend < 0 ? TrendingDown : Minus;
  const trendTone =
    trend == null
      ? "text-muted-foreground"
      : trend > 0
        ? "text-rose-600"
        : trend < 0
          ? "text-emerald-600"
          : "text-muted-foreground";

  return (
    <Card className={cn(className)} {...props}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base">
            <ShieldAlert className={cn("h-4 w-4", meta.tone)} aria-hidden="true" />
            {title}
          </CardTitle>
          <span className={cn("text-xs font-medium", meta.tone)}>
            {meta.label}
          </span>
        </div>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="flex items-baseline justify-between">
          <p className="font-mono text-4xl font-bold">{clamped}</p>
          {trend != null && (
            <p
              className={cn(
                "flex items-center gap-1 text-sm font-medium",
                trendTone
              )}
            >
              <TrendIcon className="h-4 w-4" aria-hidden="true" />
              {trend > 0 ? "+" : ""}
              {trend}%
            </p>
          )}
        </div>
        <Progress
          value={clamped}
          indicatorClassName={meta.bar}
          aria-label={`リスクスコア ${clamped} / 100`}
        />
        {aiGenerated && <AiDisclaimerBanner variant="inline" />}
      </CardContent>
    </Card>
  );
}

export default RiskScoreCard;
