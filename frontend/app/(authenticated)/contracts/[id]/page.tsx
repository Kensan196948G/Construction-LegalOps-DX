import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Handshake, ListChecks, Pencil, PenLine, Scale } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ContractSummary } from "@/components/contracts/contract-summary";
import { ContractClausesViewer } from "@/components/contracts/contract-clauses-viewer";
import { ContractAttachmentsList } from "@/components/contracts/contract-attachments-list";
import { ContractActivityLog } from "@/components/contracts/contract-activity-log";
import { RiskBadge } from "@/components/risks/risk-badge";
import { bindServerSession } from "@/lib/auth/session-bridge.server";
import { ApiError } from "@/lib/api/client";
import { contractsApi } from "@/lib/api/endpoints";
import type { AuditLog, Clause, ContractDocument } from "@/lib/api/schemas";

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

interface ContractDetailData {
  contract: ContractDetail;
  clauses: Clause[];
  documents: ContractDocument[];
  activityLogs: AuditLog[];
  activityForbidden: boolean;
}

function formatDate(iso: string | null | undefined): string | null {
  if (!iso) return null;
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

async function getContract(id: string): Promise<ContractDetailData | null> {
  const cleanup = await bindServerSession();
  try {
    const [c, clausesResult, documentsResult, auditResult] = await Promise.allSettled([
      contractsApi.get(id),
      contractsApi.clauses(id),
      contractsApi.documents(id),
      contractsApi.auditTrail(id, { page: 1, size: 20 }),
    ]);
    if (c.status === "rejected") {
      console.error("contract-detail.primary-fetch-rejected", c.reason);
      return null;
    }
    const contract = c.value;
    const clauses = clausesResult.status === "fulfilled" ? clausesResult.value : [];
    const documents = documentsResult.status === "fulfilled" ? documentsResult.value : [];
    let activityLogs: AuditLog[] = [];
    let activityForbidden = false;
    if (auditResult.status === "fulfilled") {
      activityLogs = auditResult.value.items;
    } else {
      const reason = auditResult.reason;
      activityForbidden = reason instanceof ApiError && reason.status === 403;
    }
    return {
      contract: {
        id: String(contract.id),
        title: contract.title,
        counterparty: contract.counterparty ?? "—",
        contractType: contract.contract_type,
        amount: contract.amount ?? null,
        currency: contract.currency ?? "JPY",
        startDate: formatDate(contract.start_date),
        endDate: formatDate(contract.end_date),
        status: contract.status,
        riskLevel: "low",
        summary: `${contract.contract_type}に関する契約書。相手方 ${contract.counterparty ?? "—"} との合意事項を記載。最終的な法的判断は法務担当者・顧問弁護士が行います。`,
      },
      clauses,
      documents,
      activityLogs,
      activityForbidden,
    };
  } catch (error) {
    console.error("contract-detail.fetch-failed", error);
    return null;
  } finally {
    cleanup();
  }
}

interface ContractDetailPageProps {
  params: Promise<{ id: string }>;
}

export default async function ContractDetailPage({ params }: ContractDetailPageProps) {
  const { id } = await params;
  const data = await getContract(id);

  if (!data) {
    notFound();
  }
  const { contract, clauses, documents, activityLogs, activityForbidden } = data;

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
        <div className="flex flex-wrap items-center gap-3">
          <RiskBadge level={contract.riskLevel} />
          <div className="flex items-center gap-2">
            <Button asChild variant="outline" size="sm">
              <Link href={`/negotiations?contract_id=${contract.id}`}>
                <Handshake className="mr-1 h-4 w-4" aria-hidden="true" />
                交渉
              </Link>
            </Button>
            <Button asChild variant="outline" size="sm">
              <Link href={`/signing?contract_id=${contract.id}`}>
                <PenLine className="mr-1 h-4 w-4" aria-hidden="true" />
                電子契約
              </Link>
            </Button>
            <Button asChild variant="outline" size="sm">
              <Link href={`/obligations?contract_id=${contract.id}`}>
                <ListChecks className="mr-1 h-4 w-4" aria-hidden="true" />
                義務
              </Link>
            </Button>
            <Button asChild variant="outline" size="sm">
              <Link href={`/matters`}>
                <Scale className="mr-1 h-4 w-4" aria-hidden="true" />
                Matter
              </Link>
            </Button>
          </div>
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
              <ContractClausesViewer contractId={contract.id} clauses={clauses} />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="attachments">
          <Card>
            <CardHeader>
              <CardTitle>添付ファイル</CardTitle>
            </CardHeader>
            <CardContent>
              <ContractAttachmentsList contractId={contract.id} documents={documents} />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="activity">
          <Card>
            <CardHeader>
              <CardTitle>アクティビティ履歴</CardTitle>
            </CardHeader>
            <CardContent>
              <ContractActivityLog
                contractId={contract.id}
                logs={activityLogs}
                forbidden={activityForbidden}
              />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
