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
import { dashboardApi, reviewsApi, risksApi, workflowsApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import type { DashboardKpis } from "@/lib/api/schemas";
import { bindServerSession } from "@/lib/auth/session-bridge";

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

const EMPTY_KPIS: DashboardKpis = {
  total_contracts: 0,
  in_review: 0,
  pending_approval: 0,
  high_risk_open: 0,
  reviews_this_month: 0,
};

/**
 * Dashboard 用集計を Backend `/api/v1/*` から取得する。
 *
 * - KPI / リスク・ヒートマップ / 直近レビュー / 自分宛承認待ち を並列フェッチ
 * - 個別失敗は degraded フラグで通知し、画面は崩さない
 * - 認証エラー (401) は client.ts の interceptor が signOut → /login にリダイレクト
 */
async function getDashboardSummary(): Promise<DashboardSummary> {
  const unbind = await bindServerSession();
  try {
    const [kpisRes, heatmapRes, reviewsRes, workflowStepsAvailable] = await Promise.allSettled([
      dashboardApi.kpis(),
      risksApi.heatmap(),
      reviewsApi.list({ page: 1, page_size: 5, sort: "-updated_at" }),
      // 「自分宛」専用の専用 API 設計はまだ無いため、承認待ちワークフロー一覧で代用。
      // Backend 側で `assignee=self` を解釈する想定。
      workflowsApi.list({ page: 1, page_size: 5 }),
    ]);

    const kpis = kpisRes.status === "fulfilled" ? kpisRes.value : EMPTY_KPIS;

    // Heatmap (probability × impact) を level=max(prob,impact) で粗く集約
    const distMap: Record<"low" | "medium" | "high" | "critical", number> = {
      low: 0,
      medium: 0,
      high: 0,
      critical: 0,
    };
    if (heatmapRes.status === "fulfilled") {
      const order: Array<"low" | "medium" | "high" | "critical"> = [
        "low",
        "medium",
        "high",
        "critical",
      ];
      for (const cell of heatmapRes.value.matrix) {
        const probIdx = order.indexOf(cell.probability);
        const impIdx = order.indexOf(cell.impact);
        const lv = order[Math.max(probIdx, impIdx)] ?? "low";
        distMap[lv] += cell.count;
      }
    }

    const recentReviews =
      reviewsRes.status === "fulfilled"
        ? reviewsRes.value.items.map((r) => ({
            id: String(r.id),
            title: r.summary ?? `レビュー #${r.id}`,
            status: r.status,
            riskLevel:
              (r.overall_risk as "low" | "medium" | "high" | "critical" | undefined) ?? "low",
            updatedAt: r.finished_at ?? r.started_at ?? r.created_at ?? "",
          }))
        : [];

    // 注: workflowsApi.list は WorkflowDefinition 一覧であり、自分宛 step ではない。
    // Workflow Team が `/workflow-steps?assignee=me` を提供したらこの代用を差し替える。
    const pendingApprovals: DashboardSummary["pendingApprovals"] = [];

    const degraded =
      kpisRes.status === "rejected" ||
      heatmapRes.status === "rejected" ||
      reviewsRes.status === "rejected" ||
      workflowStepsAvailable.status === "rejected";

    return {
      kpis,
      riskDistribution: [
        { level: "low", count: distMap.low },
        { level: "medium", count: distMap.medium },
        { level: "high", count: distMap.high },
        { level: "critical", count: distMap.critical },
      ],
      recentReviews,
      pendingApprovals,
      degraded,
    };
  } catch (err) {
    // 想定外の例外: ApiError 含めて degraded で受け流す
    if (!(err instanceof ApiError)) {
      // eslint-disable-next-line no-console
      console.error("[dashboard] unexpected error:", err);
    }
    return {
      kpis: EMPTY_KPIS,
      riskDistribution: [
        { level: "low", count: 0 },
        { level: "medium", count: 0 },
        { level: "high", count: 0 },
        { level: "critical", count: 0 },
      ],
      recentReviews: [],
      pendingApprovals: [],
      degraded: true,
    };
  } finally {
    unbind();
  }
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
