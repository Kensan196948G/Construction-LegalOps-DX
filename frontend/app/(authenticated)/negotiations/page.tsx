import type { Metadata } from "next";
import NegotiationsPage from "./page-client";

export const metadata: Metadata = {
  title: "契約交渉・Redline",
  description: "契約条項の交渉履歴・条項ステータス・担当オーナーを管理します",
};

interface PageProps {
  searchParams?: Promise<{ contract_id?: string }>;
}

export default async function Page({ searchParams }: PageProps) {
  const sp = await searchParams;
  return <NegotiationsPage initialContractId={sp?.contract_id ?? null} />;
}
