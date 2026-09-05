import type { Metadata } from "next";
import SigningPage from "./page-client";

export const metadata: Metadata = {
  title: "電子契約・署名",
  description: "電子契約エンベロープの作成・送付・承諾証跡・締結を管理します",
};

interface PageProps {
  searchParams?: Promise<{ contract_id?: string }>;
}

export default async function Page({ searchParams }: PageProps) {
  const sp = await searchParams;
  return <SigningPage initialContractId={sp?.contract_id ?? null} />;
}
