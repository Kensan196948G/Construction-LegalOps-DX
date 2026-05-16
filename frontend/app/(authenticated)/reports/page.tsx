"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  FileText,
  FileSearch,
  ShieldAlert,
  TrendingUp,
  CheckCircle2,
  AlertTriangle,
  XCircle,
} from "lucide-react";

const QUARTERLY_STATS = {
  totalContracts: 22,
  newContracts: 8,
  completedReviews: 12,
  avgReviewDays: 2.3,
  highRiskResolved: 3,
  complianceRate: 94,
};

const MONTHLY_REVIEWS = [
  { month: "1月", count: 3 },
  { month: "2月", count: 5 },
  { month: "3月", count: 4 },
  { month: "4月", count: 7 },
  { month: "5月（現在）", count: 2 },
];

const RISK_DISTRIBUTION = [
  { level: "low", label: "低リスク", count: 8, color: "bg-emerald-500" },
  { level: "medium", label: "中リスク", count: 7, color: "bg-amber-500" },
  { level: "high", label: "高リスク", count: 5, color: "bg-orange-500" },
  { level: "critical", label: "重大リスク", count: 2, color: "bg-red-500" },
];

const TOP_ISSUES = [
  { law: "下請法", item: "支払期日（60日ルール）", count: 4, trend: "up" },
  { law: "建設業法", item: "主任技術者の配置", count: 2, trend: "stable" },
  { law: "建設業法", item: "一括下請負の禁止", count: 1, trend: "down" },
  { law: "公共工事入札適正化法", item: "施工体制台帳", count: 3, trend: "up" },
];

const COMPLIANCE_OVERVIEW = [
  { status: "compliant", label: "適合", count: 5, icon: CheckCircle2, color: "text-emerald-500" },
  { status: "warning", label: "要確認", count: 2, icon: AlertTriangle, color: "text-amber-500" },
  { status: "non_compliant", label: "不適合", count: 1, icon: XCircle, color: "text-destructive" },
];

function MiniBarChart({ data, maxCount }: { data: typeof MONTHLY_REVIEWS; maxCount: number }) {
  return (
    <div className="flex items-end gap-2 h-24">
      {data.map((d) => (
        <div key={d.month} className="flex flex-1 flex-col items-center gap-1">
          <span className="text-xs font-medium text-foreground">{d.count}</span>
          <div
            className="w-full rounded-t bg-primary/80"
            style={{ height: `${(d.count / maxCount) * 80}px`, minHeight: "4px" }}
          />
          <span className="text-[10px] text-muted-foreground text-center leading-tight">{d.month}</span>
        </div>
      ))}
    </div>
  );
}

function RiskBar({ level, count, total, color }: { level: string; label: string; count: number; total: number; color: string }) {
  const pct = total > 0 ? Math.round((count / total) * 100) : 0;
  return (
    <div className="flex items-center gap-3">
      <span className="w-16 text-xs text-muted-foreground">{level}</span>
      <div className="flex-1 rounded-full bg-muted h-2">
        <div className={`${color} h-2 rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-8 text-right text-xs font-medium">{count}</span>
    </div>
  );
}

export default function ReportsPage() {
  const totalRisk = RISK_DISTRIBUTION.reduce((s, d) => s + d.count, 0);
  const maxReviews = Math.max(...MONTHLY_REVIEWS.map((m) => m.count));

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-foreground">レポート・分析</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          2026年度 Q1–Q2（4月〜9月）の法務活動サマリー
        </p>
      </header>

      {/* KPI Row */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        {[
          { icon: FileText, label: "契約総件数", value: QUARTERLY_STATS.totalContracts, unit: "件" },
          { icon: FileText, label: "新規契約", value: QUARTERLY_STATS.newContracts, unit: "件" },
          { icon: FileSearch, label: "完了レビュー", value: QUARTERLY_STATS.completedReviews, unit: "件" },
          { icon: TrendingUp, label: "平均レビュー日数", value: QUARTERLY_STATS.avgReviewDays, unit: "日" },
          { icon: ShieldAlert, label: "高リスク解消", value: QUARTERLY_STATS.highRiskResolved, unit: "件" },
          { icon: CheckCircle2, label: "コンプライアンス率", value: QUARTERLY_STATS.complianceRate, unit: "%" },
        ].map((kpi) => (
          <Card key={kpi.label}>
            <CardContent className="pt-4">
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">{kpi.label}</span>
                <kpi.icon className="h-4 w-4 text-muted-foreground" />
              </div>
              <p className="mt-2 text-2xl font-bold">
                {kpi.value}
                <span className="ml-1 text-sm font-normal text-muted-foreground">{kpi.unit}</span>
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Monthly Reviews Chart */}
        <Card>
          <CardHeader>
            <CardTitle>月次 AI レビュー件数</CardTitle>
          </CardHeader>
          <CardContent>
            <MiniBarChart data={MONTHLY_REVIEWS} maxCount={maxReviews} />
          </CardContent>
        </Card>

        {/* Risk Distribution */}
        <Card>
          <CardHeader>
            <CardTitle>リスクレベル分布</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {RISK_DISTRIBUTION.map((d) => (
              <RiskBar
                key={d.level}
                level={d.label}
                label={d.label}
                count={d.count}
                total={totalRisk}
                color={d.color}
              />
            ))}
            <p className="mt-2 text-xs text-muted-foreground">
              AI リスクスコアは参考値です。最終判断は法務担当者が行います。
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Top Issues */}
        <Card>
          <CardHeader>
            <CardTitle>頻出法的指摘事項 Top 4</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {TOP_ISSUES.map((issue, i) => (
                <div key={i} className="flex items-center justify-between border-b pb-2 last:border-0 last:pb-0">
                  <div>
                    <p className="text-sm font-medium">{issue.item}</p>
                    <p className="text-xs text-muted-foreground">{issue.law}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold">{issue.count} 件</span>
                    {issue.trend === "up" && <TrendingUp className="h-4 w-4 text-destructive" />}
                    {issue.trend === "down" && <TrendingUp className="h-4 w-4 rotate-180 text-emerald-500" />}
                    {issue.trend === "stable" && <span className="h-4 w-4 text-muted-foreground">→</span>}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Compliance Overview */}
        <Card>
          <CardHeader>
            <CardTitle>コンプライアンス概況</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="mb-4 flex gap-4">
              {COMPLIANCE_OVERVIEW.map((c) => (
                <div key={c.status} className="flex-1 text-center">
                  <c.icon className={`mx-auto h-8 w-8 ${c.color}`} />
                  <p className="mt-1 text-xl font-bold">{c.count}</p>
                  <p className="text-xs text-muted-foreground">{c.label}</p>
                </div>
              ))}
            </div>
            <div className="flex h-4 overflow-hidden rounded-full">
              {COMPLIANCE_OVERVIEW.map((c) => {
                const total = COMPLIANCE_OVERVIEW.reduce((s, x) => s + x.count, 0);
                const pct = (c.count / total) * 100;
                const bg = c.status === "compliant" ? "bg-emerald-500" : c.status === "warning" ? "bg-amber-400" : "bg-red-500";
                return <div key={c.status} className={bg} style={{ width: `${pct}%` }} />;
              })}
            </div>
            <div className="mt-2 flex justify-between text-xs text-muted-foreground">
              <span>不適合 12.5%</span>
              <span className="font-medium text-emerald-600 dark:text-emerald-400">適合率 62.5%</span>
            </div>
            <div className="mt-4 flex justify-center">
              <Badge variant="outline" className="text-xs">
                コンプライアンス総合スコア: {QUARTERLY_STATS.complianceRate}%
              </Badge>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
