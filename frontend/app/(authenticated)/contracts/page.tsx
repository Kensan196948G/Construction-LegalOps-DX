import type { Metadata } from "next";
import Link from "next/link";
import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ContractsTable } from "@/components/contracts/contracts-table";
import { ContractsFilters } from "@/components/contracts/contracts-filters";

export const metadata: Metadata = {
  title: "契約台帳",
  description: "契約書一覧 — 検索・絞り込み・新規登録",
};

interface SearchParams {
  q?: string;
  status?: string;
  contractType?: string;
  riskLevel?: string;
  page?: string;
  perPage?: string;
}

interface ContractsPageProps {
  searchParams?: Promise<SearchParams>;
}

interface ContractListResult {
  items: Array<{
    id: string;
    title: string;
    counterparty: string;
    contractType: string;
    amount: number | null;
    status: string;
    riskLevel: "low" | "medium" | "high" | "critical";
    updatedAt: string;
  }>;
  total: number;
  page: number;
  perPage: number;
}

import { MOCK_CONTRACTS } from "@/lib/mock-data";

async function getContracts(params: SearchParams): Promise<ContractListResult> {
  let items = MOCK_CONTRACTS.map(c => ({
    id: c.id, title: c.title, counterparty: c.counterparty,
    contractType: c.contractType, amount: c.amount,
    status: c.status, riskLevel: c.riskLevel, updatedAt: c.updatedAt,
  }));
  if (params.q) {
    const q = params.q.toLowerCase();
    items = items.filter(c => c.title.toLowerCase().includes(q) || c.counterparty.toLowerCase().includes(q));
  }
  if (params.status) items = items.filter(c => c.status === params.status);
  if (params.riskLevel) items = items.filter(c => c.riskLevel === params.riskLevel);
  if (params.contractType) items = items.filter(c => c.contractType === params.contractType);
  const page = Number(params.page ?? 1);
  const perPage = Number(params.perPage ?? 20);
  const total = items.length;
  items = items.slice((page - 1) * perPage, page * perPage);
  return { items, total, page, perPage };
}

export default async function ContractsPage({ searchParams }: ContractsPageProps) {
  const params = (await searchParams) ?? {};
  const result = await getContracts(params);

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">契約台帳</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            登録済みの契約書を一覧表示します。
          </p>
        </div>
        <Button asChild>
          <Link href="/contracts/new">
            <Plus className="mr-2 h-4 w-4" aria-hidden="true" />
            新規契約を登録
          </Link>
        </Button>
      </header>

      <ContractsFilters
        defaultValues={{
          q: params.q,
          status: params.status,
          contractType: params.contractType,
          riskLevel: params.riskLevel,
        }}
      />

      <ContractsTable
        items={result.items}
        total={result.total}
        page={result.page}
        perPage={result.perPage}
      />
    </div>
  );
}
