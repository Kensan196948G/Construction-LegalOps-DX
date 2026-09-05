import type { Metadata } from "next";
import ObligationsPage from "./page-client";

export const metadata: Metadata = {
  title: "契約義務",
  description: "契約上の報告・通知・提出・保険等の義務を期限カレンダーで管理します",
};

interface PageProps {
  searchParams?: Promise<{ contract_id?: string }>;
}

export default async function Page({ searchParams }: PageProps) {
  const sp = await searchParams;
  return <ObligationsPage initialContractId={sp?.contract_id ?? null} />;
}
