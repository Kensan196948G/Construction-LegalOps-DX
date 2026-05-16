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
import type { DashboardKpis } from "@/lib/api/schemas";
import {
  MOCK_DASHBOARD_KPIS, MOCK_RISK_DISTRIBUTION, MOCK_REVIEWS, MOCK_WORKFLOWS,
} from "@/lib/mock-data";

export const metadata: Metadata = {
  title: "ダッシュボード",
  description: "契約・レビュー・承認状況の概況",
};

// Server Component で毎リクエスト取得する (KPI は集計値、cache 不要)。
export const dynamic = "force-dynamic";

interface DashboardSummary {
  kpis: DashboardKpis;
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
  /** Backend が落ちている等、取得失敗時のフラグ */
  degraded: boolean;
}


async function getDashboardSummary(): Promise<DashboardSummary> {
  const recentReviews = MOCK_REVIEWS.slice(0, 5).map(r => ({
    id: r.id,
    title: r.contractTitle,
    status: r.status,
    riskLevel: r.riskLevel,
    updatedAt: r.completedAt ?? "2026/05/16",
  }));

  const pendingApprovals = MOCK_WORKFLOWS
    .filter(w => w.status === "in_progress")
    .slice(0, 5)
    .map(w => ({
      id: w.id,
      contractTitle: w.contractTitle,
      route: w.route,
      waitingFor: w.waitingFor,
      dueDate: w.dueDate ?? "—",
    }));

  return {
    kpis: MOCK_DASHBOARD_KPIS as DashboardKpis,
    riskDistribution: MOCK_RISK_DISTRIBUTION,
    recentReviews,
    pendingApprovals,
    degraded: false,
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
        {summary.degraded ? (
          <p className="text-xs text-amber-700" role="status" aria-live="polite">
            一部の指標を取得できませんでした。最新値ではない可能性があります。
          </p>
        ) : null}
      </header>

      <section
        aria-label="主要指標"
        className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4"
      >
        <KpiCard
          icon={FileText}
          label="契約件数（年度累計）"
          value={summary.kpis.total_contracts}
          deltaLabel="集計値"
        />
        <KpiCard
          icon={ClipboardList}
          label="レビュー中"
          value={summary.kpis.in_review}
          deltaLabel={`今月 ${summary.kpis.reviews_this_month} 件完了`}
        />
        <KpiCard
          icon={ShieldCheck}
          label="承認待ち"
          value={summary.kpis.pending_approval}
          deltaLabel="自分宛含む全体"
        />
        <KpiCard
          icon={AlertTriangle}
          label="高リスク案件"
          value={summary.kpis.high_risk_open}
          tone="warning"
          deltaLabel="未対応のみ"
        />
      </section>

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>最新の AI 一次レビュー</CardTitle>
          </CardHeader>
          <CardContent>
            <RecentReviewsList reviews={summary.recentReviews} />
            <p className="mt-3 text-xs text-muted-foreground">
              AI レビュー結果は参考情報であり、確定的な法的評価ではありません。最終判断は法務担当者・顧問弁護士が行います。
            </p>
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
