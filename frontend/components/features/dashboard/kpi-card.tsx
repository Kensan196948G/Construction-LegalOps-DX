import * as React from "react";
import { TrendingDown, TrendingUp, Minus, type LucideIcon } from "lucide-react";

import { cn } from "@/components/lib/utils";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export interface KpiCardProps extends React.HTMLAttributes<HTMLDivElement> {
  label: string;
  value: number | string;
  unit?: string;
  /** 前期比 (%) */
  delta?: number;
  /** デルタの「上昇=良い」場合 true、「上昇=悪い」場合 false */
  positiveIsGood?: boolean;
  description?: string;
  icon?: LucideIcon;
}

export function KpiCard({
  label,
  value,
  unit,
  delta,
  positiveIsGood = true,
  description,
  icon: Icon,
  className,
  ...props
}: KpiCardProps) {
  const TrendIcon =
    delta == null ? Minus : delta > 0 ? TrendingUp : delta < 0 ? TrendingDown : Minus;
  const good =
    delta == null
      ? null
      : (positiveIsGood ? delta > 0 : delta < 0)
        ? true
        : delta === 0
          ? null
          : false;
  const trendTone =
    good == null
      ? "text-muted-foreground"
      : good
        ? "text-emerald-600"
        : "text-rose-600";

  return (
    <Card className={cn(className)} {...props}>
      <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {label}
        </CardTitle>
        {Icon && <Icon className="h-4 w-4 text-muted-foreground" aria-hidden="true" />}
      </CardHeader>
      <CardContent>
        <div className="flex items-baseline gap-1">
          <p className="text-3xl font-bold tracking-tight">{value}</p>
          {unit && (
            <span className="text-sm text-muted-foreground">{unit}</span>
          )}
        </div>
        {delta != null && (
          <p
            className={cn(
              "mt-1 flex items-center gap-1 text-xs font-medium",
              trendTone
            )}
          >
            <TrendIcon className="h-3.5 w-3.5" aria-hidden="true" />
            {delta > 0 ? "+" : ""}
            {delta}%
            <span className="text-muted-foreground">前期比</span>
          </p>
        )}
        {description && (
          <CardDescription className="mt-1">{description}</CardDescription>
        )}
      </CardContent>
    </Card>
  );
}

export default KpiCard;
