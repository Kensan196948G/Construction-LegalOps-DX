import type { Metadata } from "next";
import {
  FileText,
  ClipboardList,
  AlertTriangle,
  ShieldCheck,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { PendingApprovalsList } from "@/components/dashboard/pending-approvals-list";
import { RecentReviewsList } from "@/components/dashboard/recent-reviews-list";
import { RiskDistributionChart } from "@/components/dashboard/risk-distribution-chart";

export const metadata: Metadata = {
  title: "ダッシュボード",
  description: "契約・レビュー・承認状況の概況",
};

interface DashboardSummary {
  contracts: { total: number; delta: number };
  reviews: { inProgress: number; delta: number };
  pendingApprovalsKpi: { count: number; delta: number };
  highRisks: { count: number; delta: number };
  riskDistribution: Array<{ level: "low" | "medium" | "high" | "critical"; count: number }>;
  recentReviews: Array<{
    id: string;
    title: string;
    status: string;
    riskLevel: "low" | "medium" | "high" | "critical";
    updatedAt: string;
  }>;
  pendingApprovals: Array<{
    id: string;
    contractTitle: string;
    route: string;
    waitingFor: string;
    dueDate: string;
  }>;
}

/**
 * Stub データ取得。Loop 4-5 で `@/lib/api/dashboard` 経由の実 API 呼び出しに差し替える。
 */
async function getDashboardSummary(): Promise<DashboardSummary> {
  return {
    contracts: { total: 0, delta: 0 },
    reviews: { inProgress: 0, delta: 0 },
    pendingApprovalsKpi: { count: 0, delta: 0 },
    highRisks: { count: 0, delta: 0 },
    riskDistribution: [
      { level: "low", count: 0 },
      { level: "medium", count: 0 },
      { level: "high", count: 0 },
      { level: "critical", count: 0 },
    ],
    recentReviews: [],
    pendingApprovals: [],
  };
}

export default async function DashboardPage() {
  const summary = await getDashboardSummary();

  return (
    <div className="space-y-6">
      <header className="flex items-baseline justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">ダッシュボード</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            契約・レビュー・承認の状況を一覧表示します。
          </p>
        </div>
      </header>

      <section
        aria-label="主要指標"
        className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4"
      >
        <KpiCard
          icon={FileText}
          label="契約件数（年度累計）"
          value={summary.contracts.total}
          deltaLabel={`前月比 ${summary.contracts.delta >= 0 ? "+" : ""}${summary.contracts.delta}`}
        />
        <KpiCard
          icon={ClipboardList}
          label="レビュー中"
          value={summary.reviews.inProgress}
          deltaLabel={`前週比 ${summary.reviews.delta >= 0 ? "+" : ""}${summary.reviews.delta}`}
        />
        <KpiCard
          icon={ShieldCheck}
          label="承認待ち"
          value={summary.pendingApprovalsKpi.count}
          deltaLabel={`前日比 ${summary.pendingApprovalsKpi.delta >= 0 ? "+" : ""}${summary.pendingApprovalsKpi.delta}`}
        />
        <KpiCard
          icon={AlertTriangle}
          label="高リスク案件"
          value={summary.highRisks.count}
          tone="warning"
          deltaLabel={`前週比 ${summary.highRisks.delta >= 0 ? "+" : ""}${summary.highRisks.delta}`}
        />
      </section>

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>最新の AI 一次レビュー</CardTitle>
          </CardHeader>
          <CardContent>
            <RecentReviewsList reviews={summary.recentReviews} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>リスク分布</CardTitle>
          </CardHeader>
          <CardContent>
            <RiskDistributionChart data={summary.riskDistribution} />
            <p className="mt-3 text-xs text-muted-foreground">
              AI のリスクスコアは参考値であり、確定的な法的評価ではありません。
            </p>
          </CardContent>
        </Card>
      </section>

      <section>
        <Card>
          <CardHeader>
            <CardTitle>あなたの承認待ち</CardTitle>
          </CardHeader>
          <CardContent>
            <PendingApprovalsList items={summary.pendingApprovals} />
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
