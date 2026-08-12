import type { Metadata } from "next";

import { bindServerSession } from "@/lib/auth/session-bridge.server";
import { contractsApi } from "@/lib/api/endpoints";
import DeadlinesPage from "./page-client";

export const metadata: Metadata = {
  title: "契約期限・更新管理",
  description: "契約の期限・更新期日を一覧管理します",
};

async function loadContracts() {
  const cleanup = await bindServerSession();
  try {
    const result = await contractsApi.list({ page: 1, page_size: 200, sort: "end_date" });
    return {
      contracts: result.items.map((c) => ({
        id: c.id,
        contract_no: c.contract_no ?? null,
        title: c.title,
        counterparty: c.counterparty ?? null,
        contract_type: c.contract_type,
        end_date: c.end_date ?? null,
        amount: c.amount ?? null,
        status: c.status,
      })),
      error: null as string | null,
    };
  } catch {
    return {
      contracts: [],
      error: "契約データを取得できませんでした。時間をおいて再試行してください。",
    };
  } finally {
    cleanup();
  }
}

export default async function Page() {
  const data = await loadContracts();
  return <DeadlinesPage contracts={data.contracts} error={data.error} />;
}
