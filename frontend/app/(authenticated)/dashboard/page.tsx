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
import { bindServerSession } from "@/lib/auth/session-bridge.server";
import { dashboardApi, reviewsApi, risksApi, workflowsApi } from "@/lib/api/endpoints";
import type { DashboardSummary } from "@/lib/api/schemas";

export const metadata: Metadata = {
  title: "ダッシュボード",
  description: "契約・レビュー・承認状況の概況",
};

export const dynamic = "force-dynamic";

type RiskLevel = "low" | "medium" | "high" | "critical";

interface ReviewItem {
  id: string;
  title: string;
  status: string;
  riskLevel: RiskLevel;
  updatedAt: string;
}

interface ApprovalItem {
  id: string;
  contractTitle: string;
  route: string;
  waitingFor: string;
  dueDate: string;
}

interface PageData {
  summary: DashboardSummary | null;
  riskDistribution: Array<{ level: RiskLevel; count: number }>;
  recentReviews: ReviewItem[];
  pendingApprovals: ApprovalItem[];
  degraded: boolean;
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

const RISK_LEVELS: RiskLevel[] = ["low", "medium", "high", "critical"];

async function getDashboardData(): Promise<PageData> {
  const cleanup = await bindServerSession();
  try {
    const [summaryResult, reviewsResult, heatmapResult, applicationsResult] =
      await Promise.allSettled([
        dashboardApi.summary(),
        reviewsApi.list({ page: 1, size: 5 }),
        risksApi.heatmap(),
        // 「承認待ち」は workflow_step の pending が実体。contracts の status に
        // pending_approval という値は存在しない（ContractStatus は draft /
        // in_review / approved / signed / archived / rejected のみ）ため、
        // contractsApi.list({status:"pending_approval"}) は常に 0 件だった。
        // 稟議一覧 API（workflow_step × contract 結合ビュー）が正しい取得元。
        // 注意: backend のページサイズ param は `size`（`page_size` は無視される）。
        workflowsApi.applications({ status: "pending", page: 1, size: 5 }),
      ]);

    // このバナーは「そのページの指標が実際に取れなかった」ことを示す。
    // heatmap（→ riskDistribution）と applications（→ pendingApprovals）も
    // 失敗時は 0 件/空として描画されてしまうため、degraded に含める。
    const degraded =
      summaryResult.status === "rejected" ||
      reviewsResult.status === "rejected" ||
      heatmapResult.status === "rejected" ||
      applicationsResult.status === "rejected";

    // KPI summary
    const summary =
      summaryResult.status === "fulfilled" ? summaryResult.value : null;

    // Recent reviews list
    const recentReviews: ReviewItem[] =
      reviewsResult.status === "fulfilled"
        ? reviewsResult.value.items.map((r) => ({
            id: String(r.id),
            title: r.summary ?? `レビュー #${r.id}`,
            status: r.status,
            riskLevel: (r.overall_risk ?? "low") as RiskLevel,
            updatedAt: formatDate(r.finished_at ?? r.created_at),
          }))
        : [];

    // Risk distribution from heatmap matrix — aggregate by impact level
    const riskCountMap: Record<RiskLevel, number> = {
      low: 0,
      medium: 0,
      high: 0,
      critical: 0,
    };
    if (heatmapResult.status === "fulfilled") {
      for (const cell of heatmapResult.value.matrix) {
        const level = cell.impact as RiskLevel;
        if (level in riskCountMap) {
          riskCountMap[level] += cell.count;
        }
      }
    }
    const riskDistribution = RISK_LEVELS.map((level) => ({
      level,
      count: riskCountMap[level],
    }));

    // 承認待ち = workflow_step が pending の稟議（contract_id を詳細リンクに使う）
    const pendingApprovals: ApprovalItem[] =
      applicationsResult.status === "fulfilled"
        ? applicationsResult.value.items.map((a) => ({
            id: String(a.contract_id),
            contractTitle: a.title,
            route: a.contract_type,
            waitingFor: a.applicant ?? a.step_name,
            dueDate: formatDate(a.due_at),
          }))
        : [];

    return { summary, riskDistribution, recentReviews, pendingApprovals, degraded };
  } catch {
    return {
      summary: null,
      riskDistribution: RISK_LEVELS.map((level) => ({ level, count: 0 })),
      recentReviews: [],
      pendingApprovals: [],
      degraded: true,
    };
  } finally {
    cleanup();
  }
}

export default async function DashboardPage() {
  const data = await getDashboardData();
  const { summary, riskDistribution, recentReviews, pendingApprovals, degraded } = data;

  return (
    <div className="space-y-6">
      <header className="flex items-baseline justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">ダッシュボード</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            契約・レビュー・承認の状況を一覧表示します。
          </p>
        </div>
        {degraded ? (
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
          icon={ClipboardList}
          label="レビュー中"
          value={summary?.pending_review ?? 0}
          deltaLabel="承認待ちを除く"
        />
        <KpiCard
          icon={ShieldCheck}
          label="承認待ち"
          value={summary?.pending_approval ?? 0}
          deltaLabel="自分宛含む全体"
        />
        <KpiCard
          icon={FileText}
          label="今月完了"
          value={summary?.recent_completed ?? 0}
          deltaLabel="直近 30 日"
        />
        <KpiCard
          icon={AlertTriangle}
          label="高リスク案件"
          value={summary?.high_risk ?? 0}
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
            <RecentReviewsList reviews={recentReviews} />
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
            <RiskDistributionChart data={riskDistribution} />
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
            <PendingApprovalsList items={pendingApprovals} />
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
