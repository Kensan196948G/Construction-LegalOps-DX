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

interface HeatmapCell {
  probability: 1 | 2 | 3 | 4;
  impact: 1 | 2 | 3 | 4;
  count: number;
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
  heatmapData: HeatmapCell[];
}

import { MOCK_RISKS } from "@/lib/mock-data";

async function getRisks(params: SearchParams): Promise<RiskListResult> {
  let items = MOCK_RISKS.map(r => ({
    id: r.id, contractId: r.contractId, contractTitle: r.contractTitle,
    category: r.category, level: r.level, score: r.score,
    description: r.description, status: r.status, owner: r.owner, detectedAt: r.detectedAt,
  }));
  if (params.level) items = items.filter(r => r.level === params.level);
  if (params.category) items = items.filter(r => r.category === params.category);
  if (params.status) items = items.filter(r => r.status === params.status);
  const byLevel = (["low","medium","high","critical"] as const).map(level => ({
    level, count: MOCK_RISKS.filter(r => r.level === level).length,
  }));
  const cats = Array.from(new Set(MOCK_RISKS.map(r => r.category)));
  const byCategory = cats.map(category => ({
    category, count: MOCK_RISKS.filter(r => r.category === category).length,
  }));
  const heatmapData: HeatmapCell[] = [];
  for (const p of [1, 2, 3, 4] as const) {
    for (const i of [1, 2, 3, 4] as const) {
      const count = MOCK_RISKS.filter(r => r.probability === p && r.impact === i).length;
      if (count > 0) heatmapData.push({ probability: p, impact: i, count });
    }
  }
  const page = Number(params.page ?? 1);
  const perPage = 20;
  const total = items.length;
  items = items.slice((page - 1) * perPage, page * perPage);
  return { items, total, page, perPage, byLevel, byCategory, heatmapData };
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
          <RisksOverview byLevel={result.byLevel} byCategory={result.byCategory} heatmapData={result.heatmapData} />
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
