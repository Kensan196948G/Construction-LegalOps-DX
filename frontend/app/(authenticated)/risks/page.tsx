import type { Metadata } from "next";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { RisksTable } from "@/components/risks/risks-table";
import { RisksFilters } from "@/components/risks/risks-filters";
import { RisksOverview } from "@/components/risks/risks-overview";
import { AiDisclaimerInline } from "@/components/legal/ai-disclaimer-inline";
import { bindServerSession } from "@/lib/auth/session-bridge.server";
import { risksApi } from "@/lib/api/endpoints";

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

type RiskLevel = "low" | "medium" | "high" | "critical";
type RiskStatus = "open" | "mitigated" | "accepted" | "closed";

interface RiskListResult {
  items: Array<{
    id: string;
    contractId: string;
    contractTitle: string;
    category: string;
    level: RiskLevel;
    score: number;
    description: string;
    status: RiskStatus;
    owner: string | null;
    detectedAt: string;
  }>;
  total: number;
  page: number;
  perPage: number;
  byLevel: Array<{ level: RiskLevel; count: number }>;
  byCategory: Array<{ category: string; count: number }>;
  heatmapData: HeatmapCell[];
}

const LEVEL_NUM: Record<RiskLevel, 1 | 2 | 3 | 4> = {
  low: 1,
  medium: 2,
  high: 3,
  critical: 4,
};

const RISK_LEVELS: RiskLevel[] = ["low", "medium", "high", "critical"];

function toNumericLevel(level: string | null | undefined): 1 | 2 | 3 | 4 {
  return LEVEL_NUM[level as RiskLevel] ?? 1;
}

function deriveScore(
  probability: string | null | undefined,
  impact: string | null | undefined,
  severity: string,
): number {
  const p = toNumericLevel(probability ?? severity);
  const i = toNumericLevel(impact ?? severity);
  return Math.round((p * i * 100) / 16);
}

function toComponentStatus(apiStatus: string): RiskStatus {
  if (apiStatus === "in_progress") return "open";
  const valid: RiskStatus[] = ["open", "mitigated", "accepted", "closed"];
  return valid.includes(apiStatus as RiskStatus) ? (apiStatus as RiskStatus) : "open";
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

async function getRisks(params: SearchParams): Promise<RiskListResult> {
  const page = Number(params.page ?? 1);
  const perPage = 20;

  const cleanup = await bindServerSession();
  try {
    const [listResult, heatmapResult] = await Promise.allSettled([
      risksApi.list({
        severity: params.level && params.level !== "all" ? params.level : undefined,
        status: params.status && params.status !== "all" ? params.status : undefined,
        page,
        page_size: perPage,
      }),
      risksApi.heatmap(),
    ]);

    const allItems =
      listResult.status === "fulfilled"
        ? listResult.value.items.map((r) => ({
            id: String(r.id),
            contractId: String(r.contract_id ?? ""),
            contractTitle: r.contract_id ? `契約 #${r.contract_id}` : "—",
            category: r.category ?? "その他",
            level: r.severity as RiskLevel,
            score: deriveScore(r.probability, r.impact, r.severity),
            description: r.description ?? r.title,
            status: toComponentStatus(r.status),
            owner: r.owner?.display_name ?? null,
            detectedAt: formatDate(r.created_at),
          }))
        : [];

    const total = listResult.status === "fulfilled" ? listResult.value.total : 0;

    // category filter is client-side only (API doesn't support it)
    const filtered =
      params.category && params.category !== "all"
        ? allItems.filter((r) => r.category === params.category)
        : allItems;

    // Aggregate summaries from the current page items
    const levelCounts: Record<RiskLevel, number> = { low: 0, medium: 0, high: 0, critical: 0 };
    const catCounts: Record<string, number> = {};
    for (const r of allItems) {
      levelCounts[r.level] = (levelCounts[r.level] ?? 0) + 1;
      catCounts[r.category] = (catCounts[r.category] ?? 0) + 1;
    }
    const byLevel = RISK_LEVELS.map((level) => ({ level, count: levelCounts[level] }));
    const byCategory = Object.entries(catCounts).map(([category, count]) => ({ category, count }));

    const heatmapData: HeatmapCell[] =
      heatmapResult.status === "fulfilled"
        ? heatmapResult.value.matrix.map((cell) => ({
            probability: toNumericLevel(cell.probability),
            impact: toNumericLevel(cell.impact),
            count: cell.count,
          }))
        : [];

    return { items: filtered, total, page, perPage, byLevel, byCategory, heatmapData };
  } catch {
    return {
      items: [],
      total: 0,
      page,
      perPage,
      byLevel: RISK_LEVELS.map((level) => ({ level, count: 0 })),
      byCategory: [],
      heatmapData: [],
    };
  } finally {
    cleanup();
  }
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
          <RisksOverview
            byLevel={result.byLevel}
            byCategory={result.byCategory}
            heatmapData={result.heatmapData}
          />
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
