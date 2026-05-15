import type { Metadata } from "next";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { RisksTable } from "@/components/risks/risks-table";
import { RisksFilters } from "@/components/risks/risks-filters";
import { RisksOverview } from "@/components/risks/risks-overview";
import { AiDisclaimerInline } from "@/components/legal/ai-disclaimer-inline";

export const metadata: Metadata = {
  title: "リスク管理",
  description: "契約・案件横断のリスク台帳",
};

interface SearchParams {
  level?: string;
  category?: string;
  status?: string;
  page?: string;
}

interface RisksPageProps {
  searchParams?: Promise<SearchParams>;
}

interface RiskListResult {
  items: Array<{
    id: string;
    contractId: string;
    contractTitle: string;
    category: string;
    level: "low" | "medium" | "high" | "critical";
    score: number;
    description: string;
    status: "open" | "mitigated" | "accepted" | "closed";
    owner: string | null;
    detectedAt: string;
  }>;
  total: number;
  page: number;
  perPage: number;
  byLevel: Array<{ level: "low" | "medium" | "high" | "critical"; count: number }>;
  byCategory: Array<{ category: string; count: number }>;
}

async function getRisks(_params: SearchParams): Promise<RiskListResult> {
  return {
    items: [],
    total: 0,
    page: 1,
    perPage: 20,
    byLevel: [],
    byCategory: [],
  };
}

export default async function RisksPage({ searchParams }: RisksPageProps) {
  const params = (await searchParams) ?? {};
  const result = await getRisks(params);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-foreground">リスク管理</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          AI が抽出したリスクと、法務担当者が登録した案件横断リスクを管理します。
        </p>
      </header>

      <AiDisclaimerInline>
        リスクスコアは AI による参考情報です。最終的な評価・対応方針は
        法務担当者・顧問弁護士が決定します。
      </AiDisclaimerInline>

      <Card>
        <CardHeader>
          <CardTitle>サマリー</CardTitle>
        </CardHeader>
        <CardContent>
          <RisksOverview byLevel={result.byLevel} byCategory={result.byCategory} />
        </CardContent>
      </Card>

      <RisksFilters
        defaultValues={{
          level: params.level,
          category: params.category,
          status: params.status,
        }}
      />

      <RisksTable
        items={result.items}
        total={result.total}
        page={result.page}
        perPage={result.perPage}
      />
    </div>
  );
}
