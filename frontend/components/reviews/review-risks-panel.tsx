"use client";

import { RiskBadge } from "@/components/risks/risk-badge";
import { Badge } from "@/components/ui/badge";
import type { RiskItem } from "@/lib/api/schemas";

const STATUS_LABEL: Record<string, string> = {
  open: "未対応",
  mitigated: "軽減済み",
  accepted: "受容",
  closed: "解消",
};
const STATUS_V: Record<string, "destructive" | "default" | "secondary" | "outline"> = {
  open: "destructive",
  mitigated: "default",
  accepted: "secondary",
  closed: "outline",
};

interface Props {
  reviewId: string;
  risks?: RiskItem[];
}

export function ReviewRisksPanel({ reviewId: _, risks = [] }: Props) {
  if (risks.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        リスクは検出されませんでした
      </p>
    );
  }

  return (
    <div className="space-y-3 py-2">
      {risks.map((risk) => (
        <div key={risk.id} className="rounded-md border p-4">
          <div className="flex flex-wrap items-center gap-2">
            <RiskBadge level={risk.severity} />
            <Badge variant={STATUS_V[risk.status] ?? "outline"}>
              {STATUS_LABEL[risk.status] ?? risk.status}
            </Badge>
            <span className="ml-auto text-xs text-muted-foreground">
              担当: {risk.owner?.display_name ?? "—"}
            </span>
          </div>
          <p className="mt-2 text-sm font-semibold">{risk.category ?? risk.title}</p>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            {risk.description}
          </p>
          {risk.mitigation ? (
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
              軽減策: {risk.mitigation}
            </p>
          ) : null}
        </div>
      ))}
    </div>
  );
}
export default ReviewRisksPanel;
