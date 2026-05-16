import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowUpRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { WorkflowStepper } from "@/components/workflows/workflow-stepper";
import { WorkflowActions } from "@/components/workflows/workflow-actions";
import { WorkflowHistory } from "@/components/workflows/workflow-history";
import { RouteBadge } from "@/components/workflows/route-badge";
import { MOCK_WORKFLOWS, MOCK_WORKFLOW_STEPS } from "@/lib/mock-data";

export const metadata: Metadata = {
  title: "ワークフロー詳細",
};

type RouteId = "A1" | "A2" | "B1" | "B2" | "C1" | "C2" | "D1";

interface WorkflowStep {
  id: string;
  order: number;
  label: string;
  assigneeRole: string;
  assigneeName: string | null;
  status: "pending" | "in_progress" | "approved" | "rejected" | "returned" | "skipped";
  decidedAt: string | null;
}

interface WorkflowDetail {
  id: string;
  contractId: string;
  contractTitle: string;
  route: RouteId;
  requiresOutsideCounsel: boolean;
  status: "in_progress" | "approved" | "rejected" | "returned" | "withdrawn";
  currentStepId: string | null;
  steps: WorkflowStep[];
  canActAsCurrent: boolean;
}

async function getWorkflow(id: string): Promise<WorkflowDetail | null> {
  const found = MOCK_WORKFLOWS.find(w => w.id === id) ?? MOCK_WORKFLOWS[0];
  if (!found) return null;
  const steps = MOCK_WORKFLOW_STEPS[found.id] ?? MOCK_WORKFLOW_STEPS["WF-0001"] ?? [];
  const currentStep = steps.find(s => s.status === "in_progress") ?? null;
  return {
    id: found.id,
    contractId: found.contractId,
    contractTitle: found.contractTitle,
    route: found.route as RouteId,
    requiresOutsideCounsel: found.requiresOutsideCounsel,
    status: found.status as WorkflowDetail["status"],
    currentStepId: currentStep?.id ?? null,
    steps,
    canActAsCurrent: found.status === "in_progress",
  };
}

interface WorkflowDetailPageProps {
  params: Promise<{ id: string }>;
}

export default async function WorkflowDetailPage({ params }: WorkflowDetailPageProps) {
  const { id } = await params;
  const workflow = await getWorkflow(id);

  if (!workflow) {
    notFound();
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs text-muted-foreground">
            ワークフロー ID: {workflow.id}
          </p>
          <h1 className="mt-1 text-2xl font-bold text-foreground">
            {workflow.contractTitle}
          </h1>
          <div className="mt-2 flex items-center gap-3 text-sm text-muted-foreground">
            <RouteBadge route={workflow.route} />
            {workflow.requiresOutsideCounsel ? (
              <span className="rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-900">
                顧問弁護士確認 必須
              </span>
            ) : null}
          </div>
        </div>
        <Button asChild variant="outline">
          <Link href={`/contracts/${workflow.contractId}`}>
            契約を開く
            <ArrowUpRight className="ml-2 h-4 w-4" aria-hidden="true" />
          </Link>
        </Button>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>承認ルート</CardTitle>
        </CardHeader>
        <CardContent>
          <WorkflowStepper
            steps={workflow.steps}
            currentStepId={workflow.currentStepId}
          />
        </CardContent>
      </Card>

      {workflow.canActAsCurrent ? (
        <Card>
          <CardHeader>
            <CardTitle>あなたの操作</CardTitle>
          </CardHeader>
          <CardContent>
            <WorkflowActions workflowId={workflow.id} />
            <p className="mt-3 text-xs text-muted-foreground">
              承認・差戻し・却下の操作は Entra ID の多要素認証セッションが必要です。
              高リスク案件では再認証を求められる場合があります。
            </p>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>履歴</CardTitle>
        </CardHeader>
        <CardContent>
          <WorkflowHistory workflowId={workflow.id} />
        </CardContent>
      </Card>
    </div>
  );
}
