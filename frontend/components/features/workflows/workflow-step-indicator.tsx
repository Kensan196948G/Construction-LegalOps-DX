import * as React from "react";
import { Check } from "lucide-react";

import { cn } from "@/components/lib/utils";

export type WorkflowRouteCode = "A1" | "A2" | "B" | "C" | "D";
export type WorkflowStepState = "done" | "current" | "pending" | "rejected" | "skipped";

export interface WorkflowStep {
  /** ルート識別子 (A1 / A2 / B / C / D) */
  code: WorkflowRouteCode | string;
  /** ステップ名 (例: 法務一次確認 / 役員承認) */
  label: string;
  state: WorkflowStepState;
  /** 担当者・役職 */
  assignee?: string;
}

export interface WorkflowStepIndicatorProps
  extends React.HTMLAttributes<HTMLDivElement> {
  steps: WorkflowStep[];
  /** ルート名 (例: A1 ルート: 法務単独承認) */
  routeLabel?: string;
}

const STATE_STYLES: Record<
  WorkflowStepState,
  { circle: string; line: string; text: string }
> = {
  done: {
    circle: "border-emerald-500 bg-emerald-500 text-white",
    line: "bg-emerald-500",
    text: "text-foreground",
  },
  current: {
    circle:
      "border-primary bg-background text-primary ring-2 ring-primary/30 animate-pulse",
    line: "bg-muted",
    text: "text-foreground font-medium",
  },
  pending: {
    circle: "border-input bg-background text-muted-foreground",
    line: "bg-muted",
    text: "text-muted-foreground",
  },
  rejected: {
    circle: "border-rose-500 bg-rose-500 text-white",
    line: "bg-rose-500",
    text: "text-rose-700 dark:text-rose-300",
  },
  skipped: {
    circle: "border-dashed border-input bg-background text-muted-foreground",
    line: "bg-muted",
    text: "text-muted-foreground line-through",
  },
};

export function WorkflowStepIndicator({
  steps,
  routeLabel,
  className,
  ...props
}: WorkflowStepIndicatorProps) {
  return (
    <div className={cn("flex flex-col gap-3", className)} {...props}>
      {routeLabel && (
        <p className="text-sm font-medium text-muted-foreground">
          {routeLabel}
        </p>
      )}
      <ol className="flex w-full items-start gap-1" aria-label="承認ワークフローの進捗">
        {steps.map((step, idx) => {
          const meta = STATE_STYLES[step.state];
          const isLast = idx === steps.length - 1;
          return (
            <li key={`${step.code}-${idx}`} className="flex flex-1 items-start">
              <div className="flex flex-1 flex-col items-center">
                <div className="flex w-full items-center">
                  <div
                    className={cn(
                      "flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 text-xs font-semibold",
                      meta.circle
                    )}
                    aria-current={step.state === "current" ? "step" : undefined}
                  >
                    {step.state === "done" ? (
                      <Check className="h-4 w-4" />
                    ) : (
                      step.code
                    )}
                  </div>
                  {!isLast && (
                    <div
                      className={cn("h-0.5 flex-1", meta.line)}
                      aria-hidden="true"
                    />
                  )}
                </div>
                <div className="mt-2 px-1 text-center">
                  <p className={cn("text-xs", meta.text)}>{step.label}</p>
                  {step.assignee && (
                    <p className="text-[10px] text-muted-foreground">
                      {step.assignee}
                    </p>
                  )}
                </div>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

export default WorkflowStepIndicator;
