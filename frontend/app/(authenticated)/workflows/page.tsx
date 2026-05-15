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

async function getWorkflows(_params: SearchParams): Promise<WorkflowListResult> {
  return { items: [], total: 0, page: 1, perPage: 20 };
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
