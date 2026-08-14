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
    <div className="overflow-x-auto pb-2">
    <ol className="flex min-w-max items-start">
      {steps.map((step, i) => {
        const cfg = STATUS_CONFIG[step.status];
        const Icon = cfg.icon;
        const isCurrent = step.id === currentStepId || step.status === "in_progress";

        return (
          <li key={step.id} className="flex items-start">
            <div className="flex w-44 flex-col items-center px-2 text-center">
              <div
                className={cn(
                  "flex h-7 w-7 shrink-0 items-center justify-center rounded-full border-2 bg-background",
                  isCurrent ? "border-blue-500" : "border-border",
                )}
              >
                <Icon className={cn("h-4 w-4", cfg.color)} />
              </div>
              <p className="mt-2 text-xs text-muted-foreground">STEP {step.order}</p>
              <p className={cn("mt-0.5 text-sm leading-snug", isCurrent && "font-semibold")}>
                {step.label}
              </p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {step.assigneeRole}
                {step.assigneeName && <span className="ml-1">— {step.assigneeName}</span>}
              </p>
              <div className="mt-1 flex flex-wrap items-center justify-center gap-1">
                <span className={cn("text-xs", cfg.color)}>{cfg.label}</span>
                {step.decidedAt && (
                  <span className="text-xs text-muted-foreground">{step.decidedAt}</span>
                )}
              </div>
            </div>
            {i < steps.length - 1 && (
              <div
                aria-hidden="true"
                className={cn(
                  "mt-3.5 h-px w-8 shrink-0",
                  step.status === "approved" || step.status === "skipped" ? "bg-emerald-300" : "bg-border",
                )}
              />
            )}
          </li>
        );
      })}
    </ol>
    </div>
  );
}
export default WorkflowStepper;
