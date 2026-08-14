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
import { bindServerSession } from "@/lib/auth/session-bridge.server";
import { contractsApi } from "@/lib/api/endpoints";
import type { WorkflowStep as ApiStep } from "@/lib/api/schemas";

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

type WfStatus = WorkflowDetail["status"];
type StepStatus = WorkflowStep["status"];

function toWfStatus(contractStatus: string): WfStatus {
  switch (contractStatus) {
    case "in_review":
    case "pending_approval":
      return "in_progress";
    case "approved":
    case "executed":
      return "approved";
    case "rejected":
      return "rejected";
    case "returned":
      return "returned";
    default:
      return "withdrawn";
  }
}

function toStepStatus(apiStatus: ApiStep["status"]): StepStatus {
  if (apiStatus === "sent_back") return "returned";
  // "delegated" has no direct equivalent — show as in_progress
  if (apiStatus === "delegated") return "in_progress";
  return apiStatus as StepStatus;
}

function mapStep(s: ApiStep): WorkflowStep {
  return {
    id: String(s.id),
    order: s.seq,
    label: s.name,
    assigneeRole: s.assignee_role ?? "—",
    assigneeName: s.assignee?.display_name ?? null,
    status: toStepStatus(s.status),
    decidedAt: s.decided_at ?? s.finished_at ?? null,
  };
}

// The list page bridges contract IDs as workflow IDs — URL id IS the contract_id.
// Steps are fetched from GET /workflows/{contractId}/steps.
async function getWorkflow(id: string): Promise<WorkflowDetail | null> {
  const cleanup = await bindServerSession();
  try {
    const [c, apiSteps] = await Promise.all([
      contractsApi.get(id),
      contractsApi.workflowSteps(id).catch(() => [] as ApiStep[]),
    ]);
    const wfStatus = toWfStatus(c.status);
    const steps = apiSteps.map(mapStep);
    const inProgressStep = steps.find((s) => s.status === "in_progress");
    return {
      id: String(c.id),
      contractId: String(c.id),
      contractTitle: c.title,
      route: (c.contract_type as RouteId) ?? "A1",
      requiresOutsideCounsel: false,
      status: wfStatus,
      currentStepId: inProgressStep?.id ?? null,
      steps,
      canActAsCurrent: wfStatus === "in_progress" && !!inProgressStep,
    };
  } catch {
    return null;
  } finally {
    cleanup();
  }
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
          <WorkflowHistory workflowId={workflow.id} steps={workflow.steps} />
        </CardContent>
      </Card>
    </div>
  );
}
