import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Pencil } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ContractSummary } from "@/components/contracts/contract-summary";
import { ContractClausesViewer } from "@/components/contracts/contract-clauses-viewer";
import { ContractAttachmentsList } from "@/components/contracts/contract-attachments-list";
import { ContractActivityLog } from "@/components/contracts/contract-activity-log";
import { RiskBadge } from "@/components/risks/risk-badge";

export const metadata: Metadata = {
  title: "契約詳細",
};

interface ContractDetail {
  id: string;
  title: string;
  counterparty: string;
  contractType: string;
  amount: number | null;
  currency: string;
  startDate: string | null;
  endDate: string | null;
  status: string;
  riskLevel: "low" | "medium" | "high" | "critical";
  summary: string;
}

async function getContract(id: string): Promise<ContractDetail | null> {
  // Stub. Loop 4-5 で `@/lib/api/contracts.get(id)` に差し替え。
  if (!id) return null;
  return null;
}

interface ContractDetailPageProps {
  params: Promise<{ id: string }>;
}

export default async function ContractDetailPage({ params }: ContractDetailPageProps) {
  const { id } = await params;
  const contract = await getContract(id);

  if (!contract) {
    notFound();
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs text-muted-foreground">契約 ID: {contract.id}</p>
          <h1 className="mt-1 text-2xl font-bold text-foreground">
            {contract.title}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            相手方: {contract.counterparty} / 種別: {contract.contractType}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <RiskBadge level={contract.riskLevel} />
          <Button asChild variant="outline">
            <Link href={`/contracts/${contract.id}/edit`}>
              <Pencil className="mr-2 h-4 w-4" aria-hidden="true" />
              編集
            </Link>
          </Button>
        </div>
      </header>

      <ContractSummary contract={contract} />

      <Tabs defaultValue="clauses">
        <TabsList>
          <TabsTrigger value="clauses">条項</TabsTrigger>
          <TabsTrigger value="attachments">添付ファイル</TabsTrigger>
          <TabsTrigger value="activity">アクティビティ</TabsTrigger>
        </TabsList>

        <TabsContent value="clauses">
          <Card>
            <CardHeader>
              <CardTitle>条項一覧</CardTitle>
            </CardHeader>
            <CardContent>
              <ContractClausesViewer contractId={contract.id} />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="attachments">
          <Card>
            <CardHeader>
              <CardTitle>添付ファイル</CardTitle>
            </CardHeader>
            <CardContent>
              <ContractAttachmentsList contractId={contract.id} />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="activity">
          <Card>
            <CardHeader>
              <CardTitle>アクティビティ履歴</CardTitle>
            </CardHeader>
            <CardContent>
              <ContractActivityLog contractId={contract.id} />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
