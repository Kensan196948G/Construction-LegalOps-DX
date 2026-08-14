"use client";

import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { Clause } from "@/lib/api/schemas";

interface Props {
  contractId: string;
  clauses?: Clause[];
}

function riskLabel(level: string | null | undefined): string {
  switch (level) {
    case "critical":
      return "重大";
    case "high":
      return "高";
    case "medium":
      return "中";
    case "low":
      return "低";
    default:
      return "確認済";
  }
}

export function ContractClausesViewer({ contractId: _, clauses = [] }: Props) {
  if (clauses.length === 0) {
    return (
      <p className="py-6 text-center text-sm text-muted-foreground">
        条項はまだ登録されていません。契約のレビューが実行されると条項が抽出されます。
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {clauses.map((c) => {
        const hasIssue = c.risk_level === "high" || c.risk_level === "critical";
        return (
          <div key={c.id} className="rounded-md border p-3">
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-2">
                {hasIssue ? (
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" aria-hidden="true" />
                ) : (
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" aria-hidden="true" />
                )}
                <span className="text-sm font-semibold">
                  {c.title ?? `第${c.seq}条`}
                </span>
              </div>
              <Badge variant={hasIssue ? "destructive" : "secondary"} className="shrink-0 text-xs">
                {riskLabel(c.risk_level)}
              </Badge>
            </div>
            <p className="mt-2 pl-6 text-xs leading-relaxed text-muted-foreground">{c.text}</p>
          </div>
        );
      })}
    </div>
  );
}
export default ContractClausesViewer;
