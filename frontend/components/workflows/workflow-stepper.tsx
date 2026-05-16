import { CheckCircle2, Circle, XCircle, RotateCcw, Clock } from "lucide-react";
import { cn } from "@/components/lib/utils";

type StepStatus = "pending" | "in_progress" | "approved" | "rejected" | "returned" | "skipped";

interface Step {
  id: string; order: number; label: string;
  assigneeRole: string; assigneeName: string | null;
  status: StepStatus; decidedAt: string | null;
}

interface Props {
  steps: Step[];
  currentStepId: string | null;
}

const STATUS_CONFIG: Record<StepStatus, { icon: React.ComponentType<{ className?: string }>; color: string; label: string }> = {
  approved: { icon: CheckCircle2, color: "text-emerald-500", label: "承認済み" },
  in_progress: { icon: Clock, color: "text-blue-500", label: "審査中" },
  pending: { icon: Circle, color: "text-muted-foreground", label: "待機中" },
  rejected: { icon: XCircle, color: "text-destructive", label: "却下" },
  returned: { icon: RotateCcw, color: "text-amber-500", label: "差戻し" },
  skipped: { icon: Circle, color: "text-muted-foreground/40", label: "スキップ" },
};

export function WorkflowStepper({ steps, currentStepId }: Props) {
  if (!steps || steps.length === 0) {
    return <p className="py-4 text-sm text-muted-foreground">ステップ情報がありません</p>;
  }

  return (
    <ol className="relative space-y-6">
      {steps.map((step, i) => {
        const cfg = STATUS_CONFIG[step.status];
        const Icon = cfg.icon;
        const isCurrent = step.id === currentStepId || step.status === "in_progress";

        return (
          <li key={step.id} className="relative pl-8">
            {i < steps.length - 1 && (
              <div className="absolute left-3.5 top-6 h-full w-px bg-border" />
            )}
            <div className={cn(
              "absolute left-0 top-0 flex h-7 w-7 items-center justify-center rounded-full border-2 bg-background",
              isCurrent ? "border-blue-500" : "border-border"
            )}>
              <Icon className={cn("h-4 w-4", cfg.color)} />
            </div>
            <div className={cn("pb-2", isCurrent && "font-semibold")}>
              <p className="text-sm">
                <span className="text-xs text-muted-foreground mr-2">STEP {step.order}</span>
                {step.label}
              </p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {step.assigneeRole}
                {step.assigneeName && <span className="ml-1">— {step.assigneeName}</span>}
              </p>
              <div className="mt-1 flex items-center gap-2">
                <span className={cn("text-xs", cfg.color)}>{cfg.label}</span>
                {step.decidedAt && (
                  <span className="text-xs text-muted-foreground">{step.decidedAt}</span>
                )}
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
export default WorkflowStepper;
