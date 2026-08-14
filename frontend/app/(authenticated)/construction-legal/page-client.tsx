"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Loader2,
  Play,
  Search,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  useComplianceChecklists,
  useComplianceRun,
  useStartComplianceRun,
} from "@/hooks/use-compliance";
import { useContracts } from "@/hooks/use-contracts";
import { AiDisclaimerBanner } from "@/components/layout/ai-disclaimer-banner";

const CATEGORY_LABELS: Record<string, string> = {
  construction_law: "建設業法",
  subcontract_act: "下請法（取適法）",
  others: "その他法令",
};

const FINDING_STATUS_LABELS: Record<string, string> = {
  pass: "適合",
  fail: "不適合",
  warning: "要確認",
  skipped: "対象外",
};

const FINDING_STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  pass: "default",
  fail: "destructive",
  warning: "secondary",
  skipped: "outline",
};

const SEVERITY_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  info: "outline",
  low: "outline",
  medium: "secondary",
  high: "destructive",
  critical: "destructive",
};

export default function ConstructionLegalPage() {
  const { data: checklists, isLoading, isError } = useComplianceChecklists();
  const { data: contracts } = useContracts({ page: 1, page_size: 100 });
  const [selectedId, setSelectedId] = useState<string>("");
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const run = useStartComplianceRun({
    onSuccess: () => undefined,
  });
  const resultQuery = useComplianceRun(selectedId || null);

  // デモ初期表示: 先頭の契約を自動選択して機械チェックを1回実行する。
  const autoStarted = useRef(false);
  useEffect(() => {
    const first = contracts?.items?.[0];
    if (!first || autoStarted.current) return;
    autoStarted.current = true;
    setSelectedId(String(first.id));
    run.mutate({ contractId: String(first.id) });
  }, [contracts, run]);

  const items = useMemo(() => {
    const list = checklists ?? [];
    return list.filter((c) => {
      if (search && !c.name.includes(search) && !c.code.includes(search) && !(c.description ?? "").includes(search)) return false;
      if (categoryFilter !== "all" && c.category !== categoryFilter) return false;
      return true;
    });
  }, [checklists, search, categoryFilter]);

  const categorySummary = useMemo(() => {
    const list = checklists ?? [];
    return {
      total: list.length,
      construction_law: list.filter((c) => c.category === "construction_law").length,
      subcontract_act: list.filter((c) => c.category === "subcontract_act").length,
      others: list.filter((c) => c.category === "others").length,
    };
  }, [checklists]);

  const findingSummary = useMemo(() => {
    const findings = resultQuery.data?.findings ?? [];
    return {
      pass: findings.filter((f) => f.status === "pass").length,
      fail: findings.filter((f) => f.status === "fail").length,
      warning: findings.filter((f) => f.status === "warning").length,
      skipped: findings.filter((f) => f.status === "skipped").length,
    };
  }, [resultQuery.data]);

  const executeCheck = () => {
    if (!selectedId) return;
    run.mutate({ contractId: selectedId });
  };

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-foreground">建設業法務チェック</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          チェックリスト定義（正本）と契約ごとの機械チェック結果を表示します
        </p>
      </header>

      <AiDisclaimerBanner variant="inline" />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Card>
          <CardContent className="flex items-center gap-3 pt-4">
            <CheckCircle2 className="h-8 w-8 text-primary" />
            <div>
              <p className="text-2xl font-bold">{categorySummary.total}</p>
              <p className="text-sm text-muted-foreground">チェックリスト総数</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 pt-4">
            <CheckCircle2 className="h-8 w-8 text-emerald-500" />
            <div>
              <p className="text-2xl font-bold">{categorySummary.construction_law}</p>
              <p className="text-sm text-muted-foreground">建設業法</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 pt-4">
            <AlertTriangle className="h-8 w-8 text-amber-500" />
            <div>
              <p className="text-2xl font-bold">{categorySummary.subcontract_act}</p>
              <p className="text-sm text-muted-foreground">下請法（取適法）</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 pt-4">
            <XCircle className="h-8 w-8 text-muted-foreground" />
            <div>
              <p className="text-2xl font-bold">{categorySummary.others}</p>
              <p className="text-sm text-muted-foreground">その他法令</p>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>契約コンプライアンスチェック</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-64 flex-1 space-y-1.5">
              <label htmlFor="contract-select" className="text-sm font-medium">
                対象契約
              </label>
              <Select value={selectedId} onValueChange={setSelectedId}>
                <SelectTrigger id="contract-select">
                  <SelectValue placeholder="契約を選択" />
                </SelectTrigger>
                <SelectContent>
                  {(contracts?.items ?? []).map((c) => (
                    <SelectItem key={c.id} value={String(c.id)}>
                      {c.contract_no ?? `ID ${c.id}`} / {c.title}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button
              onClick={executeCheck}
              disabled={!selectedId || run.isPending}
              className="gap-2"
            >
              {run.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <Play className="h-4 w-4" aria-hidden="true" />
              )}
              チェック実行
            </Button>
          </div>

          {resultQuery.data && (
            <div className="rounded-md border bg-muted/30 p-4">
              <div className="flex flex-wrap items-center gap-3">
                <Badge variant={FINDING_STATUS_VARIANT[resultQuery.data.overall_status]}>
                  総合: {FINDING_STATUS_LABELS[resultQuery.data.overall_status] ?? resultQuery.data.overall_status}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  適合 {findingSummary.pass} / 不適合 {findingSummary.fail} / 要確認 {findingSummary.warning} / 対象外 {findingSummary.skipped}
                </span>
                <span className="ml-auto text-xs text-muted-foreground">
                  実行日時: {new Date(resultQuery.data.checked_at).toLocaleString("ja-JP")}
                </span>
              </div>
              <p className="mt-2 text-xs text-muted-foreground">{resultQuery.data.disclaimer}</p>
            </div>
          )}

          {resultQuery.data && resultQuery.data.findings.length > 0 && (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-28">ルール</TableHead>
                    <TableHead className="w-24">重大度</TableHead>
                    <TableHead className="w-20">状態</TableHead>
                    <TableHead>判定内容</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {resultQuery.data.findings.map((f) => (
                    <TableRow key={f.rule_id}>
                      <TableCell className="text-xs font-medium">{f.rule_name}</TableCell>
                      <TableCell>
                        <Badge variant={SEVERITY_VARIANT[f.severity] ?? "outline"} className="text-xs">
                          {f.severity}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant={FINDING_STATUS_VARIANT[f.status] ?? "outline"} className="text-xs">
                          {FINDING_STATUS_LABELS[f.status] ?? f.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="max-w-[420px]">
                        <p className="text-sm leading-relaxed">{f.message}</p>
                        {f.citations.length > 0 && (
                          <p className="mt-1 text-xs text-muted-foreground">
                            根拠: {f.citations.join(" / ")}
                          </p>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>チェックリスト定義一覧（正本マスタ）</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="mb-4 flex flex-wrap gap-3">
            <div className="relative min-w-48 flex-1">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="チェック項目・コードで検索"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-8"
              />
            </div>
            <Select value={categoryFilter} onValueChange={setCategoryFilter}>
              <SelectTrigger className="w-44" aria-label="カテゴリで絞り込み">
                <SelectValue placeholder="カテゴリ" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">すべて</SelectItem>
                {Object.entries(CATEGORY_LABELS).map(([v, l]) => (
                  <SelectItem key={v} value={v}>
                    {l}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {isLoading ? (
            <div className="space-y-2" aria-label="読み込み中">
              {[0, 1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : isError ? (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" aria-hidden="true" />
              <AlertDescription>
                チェックリストを取得できませんでした。時間をおいて再試行してください。
              </AlertDescription>
            </Alert>
          ) : (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-36">コード</TableHead>
                    <TableHead className="w-32">カテゴリ</TableHead>
                    <TableHead>チェック項目</TableHead>
                    <TableHead className="w-28">対象契約種別</TableHead>
                    <TableHead className="w-16">状態</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={5} className="py-10 text-center text-sm text-muted-foreground">
                        該当するチェック項目がありません
                      </TableCell>
                    </TableRow>
                  ) : (
                    items.map((c) => (
                      <TableRow key={c.id}>
                        <TableCell className="font-mono text-xs">{c.code}</TableCell>
                        <TableCell>
                          <span className="text-xs font-medium">
                            {CATEGORY_LABELS[c.category] ?? c.category}
                          </span>
                        </TableCell>
                        <TableCell className="max-w-[300px]">
                          <p className="text-sm font-medium">{c.name}</p>
                          {c.description && (
                            <p className="text-xs text-muted-foreground">{c.description}</p>
                          )}
                        </TableCell>
                        <TableCell className="text-sm">{c.contract_type ?? "全種別"}</TableCell>
                        <TableCell>
                          <Badge variant={c.is_active ? "default" : "secondary"} className="text-xs">
                            {c.is_active ? "有効" : "無効"}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
