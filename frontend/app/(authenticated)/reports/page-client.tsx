"use client";

import { useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AlertCircle, FileText, FileSearch, ShieldAlert, Clock, ListTodo } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { useDashboardSummary, useDashboardTrends } from "@/hooks/use-dashboard";
import { useRisks } from "@/hooks/use-risks";
import { useComplianceChecklists } from "@/hooks/use-compliance";

const SEVERITY_LABELS: Record<string, string> = {
  low: "低リスク",
  medium: "中リスク",
  high: "高リスク",
  critical: "重大リスク",
};

const SEVERITY_COLORS: Record<string, string> = {
  low: "bg-emerald-500",
  medium: "bg-amber-500",
  high: "bg-orange-500",
  critical: "bg-red-500",
};

const STATUS_LABELS: Record<string, string> = {
  draft: "下書き",
  in_review: "審査中",
  approved: "承認済み",
  rejected: "却下",
  canceled: "取消",
};

function MiniBarChart({ data }: { data: Array<{ label: string; value: number }> }) {
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <div className="flex h-24 items-end gap-2">
      {data.map((d) => (
        <div key={d.label} className="flex flex-1 flex-col items-center gap-1">
          <span className="text-xs font-medium text-foreground">{d.value}</span>
          <div
            className="w-full rounded-t bg-primary/80"
            style={{ height: `${Math.max(4, (d.value / max) * 80)}px` }}
          />
          <span className="text-[10px] text-muted-foreground text-center leading-tight">
            {d.label}
          </span>
        </div>
      ))}
    </div>
  );
}

export default function ReportsPage() {
  const summary = useDashboardSummary();
  const trends = useDashboardTrends({ interval: "month", weeks: 6 });
  const risks = useRisks({ page: 1, page_size: 200 });
  const checklists = useComplianceChecklists();

  const s = summary.data;

  const trendData = useMemo(() => {
    const series = trends.data?.series;
    if (!series) return [];
    const key = series.reviews ? "reviews" : Object.keys(series)[0];
    if (!key) return [];
    return (series[key] ?? []).map((p) => ({
      label: p.bucket.slice(5).replace("-", "/"),
      value: p.value,
    }));
  }, [trends.data]);

  const riskDistribution = useMemo(() => {
    const counts: Record<string, number> = { low: 0, medium: 0, high: 0, critical: 0 };
    for (const r of risks.data?.items ?? []) {
      counts[r.severity] = (counts[r.severity] ?? 0) + 1;
    }
    return counts;
  }, [risks.data]);

  const statusDistribution = useMemo(() => {
    const entries = Object.entries(s?.contracts_by_status ?? {});
    return entries.map(([status, count]) => ({
      status,
      label: STATUS_LABELS[status] ?? status,
      count,
    }));
  }, [s]);

  const checklistCounts = useMemo(() => {
    const list = checklists.data ?? [];
    return {
      total: list.length,
      construction_law: list.filter((c) => c.category === "construction_law").length,
      subcontract_act: list.filter((c) => c.category === "subcontract_act").length,
      others: list.filter((c) => c.category === "others").length,
    };
  }, [checklists.data]);

  const kpis = [
    { icon: FileText, label: "未レビュー", value: s?.pending_review, unit: "件" },
    { icon: FileSearch, label: "承認待ち", value: s?.pending_approval, unit: "件" },
    { icon: Clock, label: "期限切れ", value: s?.overdue, unit: "件" },
    { icon: ShieldAlert, label: "高リスク", value: s?.high_risk, unit: "件" },
    { icon: FileSearch, label: "直近完了", value: s?.recent_completed, unit: "件" },
    { icon: ListTodo, label: "自分宛タスク", value: s?.my_tasks, unit: "件" },
  ];

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-foreground">レポート・分析</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          ダッシュボード集計・リスク・コンプライアンスの実データを表示します
        </p>
      </header>

      {summary.isError && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" aria-hidden="true" />
          <AlertDescription>
            レポートデータを取得できませんでした。権限を確認するか、時間をおいて再試行してください。
          </AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        {kpis.map((kpi) => (
          <Card key={kpi.label}>
            <CardContent className="pt-4">
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">{kpi.label}</span>
                <kpi.icon className="h-4 w-4 text-muted-foreground" />
              </div>
              {summary.isLoading ? (
                <Skeleton className="mt-2 h-8 w-16" />
              ) : (
                <p className="mt-2 text-2xl font-bold">
                  {kpi.value ?? 0}
                  <span className="ml-1 text-sm font-normal text-muted-foreground">{kpi.unit}</span>
                </p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>月次レビュー件数推移</CardTitle>
          </CardHeader>
          <CardContent>
            {trends.isLoading ? (
              <Skeleton className="h-24 w-full" />
            ) : trendData.length === 0 ? (
              <p className="py-8 text-center text-sm text-muted-foreground">
                集計データがありません
              </p>
            ) : (
              <MiniBarChart data={trendData} />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>リスクレベル分布</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {risks.isLoading ? (
              <Skeleton className="h-24 w-full" />
            ) : (
              Object.entries(SEVERITY_LABELS).map(([level, label]) => {
                const count = riskDistribution[level] ?? 0;
                const total = Math.max(1, Object.values(riskDistribution).reduce((a, b) => a + b, 0));
                return (
                  <div key={level} className="flex items-center gap-3">
                    <span className="w-20 text-xs text-muted-foreground">{label}</span>
                    <div className="h-2 flex-1 rounded-full bg-muted">
                      <div
                        className={`h-2 rounded-full ${SEVERITY_COLORS[level]}`}
                        style={{ width: `${Math.round((count / total) * 100)}%` }}
                      />
                    </div>
                    <span className="w-8 text-right text-xs font-medium">{count}</span>
                  </div>
                );
              })
            )}
            <p className="mt-2 text-xs text-muted-foreground">
              AI リスクスコアは参考値です。最終判断は法務担当者が行います。
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>契約ステータス内訳</CardTitle>
          </CardHeader>
          <CardContent>
            {statusDistribution.length === 0 ? (
              <p className="py-8 text-center text-sm text-muted-foreground">
                契約データがありません
              </p>
            ) : (
              <div className="space-y-3">
                {statusDistribution.map((d) => (
                  <div key={d.status} className="flex items-center justify-between border-b pb-2 last:border-0 last:pb-0">
                    <span className="text-sm font-medium">{d.label}</span>
                    <span className="text-sm font-semibold">{d.count} 件</span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>コンプライアンスチェック定義</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="mb-4 flex gap-4">
              <div className="flex-1 text-center">
                <p className="text-xl font-bold">{checklistCounts.construction_law}</p>
                <p className="text-xs text-muted-foreground">建設業法</p>
              </div>
              <div className="flex-1 text-center">
                <p className="text-xl font-bold">{checklistCounts.subcontract_act}</p>
                <p className="text-xs text-muted-foreground">下請法（取適法）</p>
              </div>
              <div className="flex-1 text-center">
                <p className="text-xl font-bold">{checklistCounts.others}</p>
                <p className="text-xs text-muted-foreground">その他法令</p>
              </div>
            </div>
            <div className="mt-4 flex justify-center">
              <Badge variant="outline" className="text-xs">
                チェックリスト定義総数: {checklistCounts.total} 件
              </Badge>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
