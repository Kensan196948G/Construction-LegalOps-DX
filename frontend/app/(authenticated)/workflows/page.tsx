import type { Metadata } from "next";

import { WorkflowsTable } from "@/components/workflows/workflows-table";
import { WorkflowsFilters } from "@/components/workflows/workflows-filters";
import { bindServerSession } from "@/lib/auth/session-bridge.server";
import { contractsApi } from "@/lib/api/endpoints";

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

type WfStatus = "in_progress" | "approved" | "rejected" | "returned" | "withdrawn";

interface WorkflowListResult {
  items: Array<{
    id: string;
    contractId: string;
    contractTitle: string;
    route: string;
    currentStep: string;
    waitingFor: string;
    status: WfStatus;
    requiresOutsideCounsel: boolean;
    dueDate: string | null;
    updatedAt: string;
  }>;
  total: number;
  page: number;
  perPage: number;
}

function toWorkflowStatus(contractStatus: string): WfStatus | null {
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
    case "terminated":
    case "expired":
      return "withdrawn";
    default:
      return null;
  }
}

function getCurrentStep(contractStatus: string): string {
  switch (contractStatus) {
    case "in_review":
      return "法務確認中";
    case "pending_approval":
      return "承認待ち";
    case "approved":
    case "executed":
      return "完了";
    case "rejected":
      return "否決済み";
    case "returned":
      return "差戻し中";
    default:
      return "—";
  }
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("ja-JP", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
  } catch {
    return iso;
  }
}

async function getWorkflows(params: SearchParams): Promise<WorkflowListResult> {
  const page = Number(params.page ?? 1);
  const perPage = 20;

  const cleanup = await bindServerSession();
  try {
    const result = await contractsApi.list({ page, page_size: perPage });

    const allItems = result.items
      .map((c) => {
        const wfStatus = toWorkflowStatus(c.status);
        if (!wfStatus) return null;
        return {
          id: String(c.id),
          contractId: String(c.id),
          contractTitle: c.title,
          route: c.contract_type,
          currentStep: getCurrentStep(c.status),
          waitingFor: c.drafter?.display_name ?? "—",
          status: wfStatus,
          requiresOutsideCounsel: false,
          dueDate: c.end_date ? formatDate(c.end_date) : null,
          updatedAt: formatDate(c.updated_at),
        };
      })
      .filter((item): item is NonNullable<typeof item> => item !== null);

    const filtered = allItems.filter((w) => {
      if (params.status && params.status !== "all" && w.status !== params.status) return false;
      if (params.route && params.route !== "all" && w.route !== params.route) return false;
      return true;
    });

    return { items: filtered, total: result.total, page, perPage };
  } catch {
    return { items: [], total: 0, page, perPage };
  } finally {
    cleanup();
  }
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
