import type { LucideIcon } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/components/lib/utils";

interface KpiCardProps {
  icon: LucideIcon;
  label: string;
  value: number;
  deltaLabel?: string;
  tone?: "default" | "warning";
}

export function KpiCard({ icon: Icon, label, value, deltaLabel, tone }: KpiCardProps) {
  return (
    <Card className={cn(tone === "warning" && "border-amber-300 bg-amber-50 dark:border-amber-700 dark:bg-amber-950/30")}>
      <CardContent className="pt-5">
        <div className="flex items-start justify-between">
          <p className="text-sm font-medium text-muted-foreground">{label}</p>
          <Icon className={cn("h-4 w-4 text-muted-foreground", tone === "warning" && "text-amber-500")} aria-hidden />
        </div>
        <p className={cn("mt-2 text-3xl font-bold", tone === "warning" && "text-amber-700 dark:text-amber-400")}>
          {value.toLocaleString()}
        </p>
        {deltaLabel && <p className="mt-1 text-xs text-muted-foreground">{deltaLabel}</p>}
      </CardContent>
    </Card>
  );
}
export default KpiCard;
