"use client";

import { Badge } from "@/components/ui/badge";

export interface WorkflowHistoryStep {
  id: string;
  order: number;
  label: string;
  assigneeName: string | null;
  status: "pending" | "in_progress" | "approved" | "rejected" | "returned" | "skipped";
  decidedAt: string | null;
}

const STATUS_LABEL: Record<WorkflowHistoryStep["status"], string> = {
  pending: "待機中",
  in_progress: "処理中",
  approved: "承認済み",
  rejected: "却下",
  returned: "差戻し",
  skipped: "スキップ",
};

interface Props {
  workflowId: string;
  steps?: WorkflowHistoryStep[];
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("ja-JP", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function WorkflowHistory({ workflowId: _, steps = [] }: Props) {
  const doneSteps = steps.filter((s) => s.decidedAt !== null || s.status !== "pending");

  if (doneSteps.length === 0) {
    return (
      <p className="py-6 text-center text-sm text-muted-foreground">
        承認履歴はまだありません。
      </p>
    );
  }

  return (
    <ol className="relative space-y-4 border-l border-border pl-4">
      {doneSteps.map((step) => (
        <li key={step.id} className="relative">
          <div className="absolute -left-[1.15rem] mt-1 h-2.5 w-2.5 rounded-full border-2 border-border bg-background" />
          <p className="text-xs text-muted-foreground font-mono">{formatDate(step.decidedAt)}</p>
          <p className="mt-0.5 text-sm">
            <span className="font-medium">{step.label}</span>
            <span className="text-muted-foreground">
              {" "}
              · {step.assigneeName ?? "未割当"} · {STATUS_LABEL[step.status]}
            </span>
          </p>
          <Badge variant={step.status === "approved" ? "secondary" : "outline"} className="mt-1 text-xs">
            {STATUS_LABEL[step.status]}
          </Badge>
        </li>
      ))}
    </ol>
  );
}
export default WorkflowHistory;
