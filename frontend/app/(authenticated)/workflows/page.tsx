import type { Metadata } from "next";

import { WorkflowsTable } from "@/components/workflows/workflows-table";
import { WorkflowsFilters } from "@/components/workflows/workflows-filters";

export const metadata: Metadata = {
  title: "承認ワークフロー",
  description: "契約承認ルート (A1/A2/B1/B2/C1/C2/D1) の状況一覧",
};

interface SearchParams {
  status?: string;
  route?: string;
  assignedToMe?: string;
  page?: string;
}

interface WorkflowsPageProps {
  searchParams?: Promise<SearchParams>;
}

interface WorkflowListResult {
  items: Array<{
    id: string;
    contractId: string;
    contractTitle: string;
    route: "A1" | "A2" | "B1" | "B2" | "C1" | "C2" | "D1";
    currentStep: string;
    waitingFor: string;
    status: "in_progress" | "approved" | "rejected" | "returned" | "withdrawn";
    requiresOutsideCounsel: boolean;
    dueDate: string | null;
    updatedAt: string;
  }>;
  total: number;
  page: number;
  perPage: number;
}

import { MOCK_WORKFLOWS } from "@/lib/mock-data";

async function getWorkflows(params: SearchParams): Promise<WorkflowListResult> {
  let items = MOCK_WORKFLOWS.map(w => ({
    id: w.id, contractId: w.contractId, contractTitle: w.contractTitle,
    route: w.route, currentStep: w.currentStep, waitingFor: w.waitingFor,
    status: w.status, requiresOutsideCounsel: w.requiresOutsideCounsel,
    dueDate: w.dueDate, updatedAt: w.updatedAt,
  }));
  if (params.status) items = items.filter(w => w.status === params.status);
  if (params.route) items = items.filter(w => w.route === params.route);
  if (params.assignedToMe === "true") items = items.filter(w => w.waitingFor === "田中 太郎");
  const page = Number(params.page ?? 1);
  const perPage = 20;
  const total = items.length;
  items = items.slice((page - 1) * perPage, page * perPage);
  return { items, total, page, perPage };
}

export default async function WorkflowsPage({ searchParams }: WorkflowsPageProps) {
  const params = (await searchParams) ?? {};
  const result = await getWorkflows(params);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-foreground">承認ワークフロー</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          契約承認ルートの状況を一覧表示します。承認ルートは金額・リスクに応じて
          A1 / A2 / B1 / B2 / C1 / C2 / D1 のいずれかが自動付与されます。
        </p>
      </header>

      <WorkflowsFilters
        defaultValues={{
          status: params.status,
          route: params.route,
          assignedToMe: params.assignedToMe,
        }}
      />

      <WorkflowsTable
        items={result.items}
        total={result.total}
        page={result.page}
        perPage={result.perPage}
      />
    </div>
  );
}
