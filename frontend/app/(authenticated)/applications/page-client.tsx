"use client";

import { useMemo, useState } from "react";
import { AlertCircle, Plus, RefreshCw, Search } from "lucide-react";
import Link from "next/link";

import { Card, CardContent } from "@/components/ui/card";
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
import { useApplications } from "@/hooks/use-workflows";
import type { WorkflowApplication } from "@/lib/api/schemas";

const STATUS_LABELS: Record<string, string> = {
  pending: "未着手",
  in_progress: "審査中",
  approved: "承認済み",
  rejected: "却下",
  sent_back: "差戻し",
  delegated: "委任",
  skipped: "スキップ",
};

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  pending: "outline",
  in_progress: "default",
  approved: "default",
  rejected: "destructive",
  sent_back: "secondary",
  delegated: "secondary",
  skipped: "outline",
};

function fmtYen(n: number | null | undefined) {
  if (n === null || n === undefined) return "—";
  return "¥" + n.toLocaleString("ja-JP");
}

function urgencyOf(app: WorkflowApplication): "緊急" | "通常" {
  if (!app.due_at) return "通常";
  if (app.status !== "pending" && app.status !== "in_progress") return "通常";
  const due = new Date(app.due_at).getTime();
  const now = Date.now();
  return due - now <= 72 * 60 * 60 * 1000 ? "緊急" : "通常";
}

export default function ApplicationsPage() {
  const { data, isLoading, isError, refetch, isFetching } = useApplications({
    page: 1,
    page_size: 200,
  });
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");

  const items = useMemo(() => data?.items ?? [], [data]);
  const types = useMemo(
    () => Array.from(new Set(items.map((a) => a.contract_type).filter(Boolean))),
    [items],
  );

  const filtered = useMemo(() => {
    return items.filter((a) => {
      if (
        search &&
        !a.title.includes(search) &&
        !(a.applicant ?? "").includes(search) &&
        !(a.contract_no ?? "").includes(search)
      ) {
        return false;
      }
      if (typeFilter !== "all" && a.contract_type !== typeFilter) return false;
      if (statusFilter !== "all" && a.status !== statusFilter) return false;
      return true;
    });
  }, [items, search, typeFilter, statusFilter]);

  return (
    <div className="space-y-6">
      <header className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">契約申請・稟議</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            承認ワークフローに紐づく契約申請を一覧表示します（実データ連動）
          </p>
        </div>
        <Button size="sm" asChild>
          <Link href="/contracts/new">
            <Plus className="mr-1.5 h-4 w-4" />
            新規申請
          </Link>
        </Button>
      </header>

      {isError && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" aria-hidden="true" />
          <AlertDescription>
            稟議一覧を取得できませんでした。権限を確認するか、時間をおいて再試行してください。
          </AlertDescription>
        </Alert>
      )}

      <Card>
        <CardContent className="pt-4">
          <div className="mb-4 flex flex-wrap gap-3">
            <div className="relative min-w-48 flex-1">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="契約名・申請者・契約番号で検索"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-8"
              />
            </div>
            <Select value={typeFilter} onValueChange={setTypeFilter}>
              <SelectTrigger className="w-44" aria-label="契約種別で絞り込み">
                <SelectValue placeholder="契約種別" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">すべての種別</SelectItem>
                {types.map((t) => (
                  <SelectItem key={t} value={t}>
                    {t}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-36" aria-label="ステータスで絞り込み">
                <SelectValue placeholder="ステータス" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">すべて</SelectItem>
                {Object.entries(STATUS_LABELS).map(([v, l]) => (
                  <SelectItem key={v} value={v}>
                    {l}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              variant="outline"
              size="icon"
              onClick={() => void refetch()}
              disabled={isFetching}
              aria-label="再読込"
            >
              <RefreshCw className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`} />
            </Button>
          </div>

          {isLoading ? (
            <div className="space-y-2" aria-label="読み込み中">
              {[0, 1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-36">契約番号</TableHead>
                    <TableHead className="w-28">種別</TableHead>
                    <TableHead>申請内容</TableHead>
                    <TableHead className="w-24">申請者</TableHead>
                    <TableHead className="w-28 text-right">金額</TableHead>
                    <TableHead className="w-16">緊急度</TableHead>
                    <TableHead className="w-24">ステータス</TableHead>
                    <TableHead className="w-24">申請日</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={8} className="py-10 text-center text-sm text-muted-foreground">
                        {items.length === 0
                          ? "承認ワークフローが開始された契約はありません。契約からワークフローを開始するとここに表示されます。"
                          : "該当する申請がありません"}
                      </TableCell>
                    </TableRow>
                  ) : (
                    filtered.map((a) => {
                      const urgency = urgencyOf(a);
                      return (
                        <TableRow key={a.step_id}>
                          <TableCell className="font-mono text-xs">
                            {a.contract_no ?? `ID ${a.contract_id}`}
                          </TableCell>
                          <TableCell className="text-sm">{a.contract_type}</TableCell>
                          <TableCell className="max-w-[220px]">
                            <Link
                              href={`/contracts/${a.contract_id}`}
                              className="text-sm font-medium hover:underline"
                            >
                              {a.title}
                            </Link>
                            <p className="text-xs text-muted-foreground">{a.step_name}</p>
                          </TableCell>
                          <TableCell className="whitespace-nowrap text-sm">
                            {a.applicant ?? "—"}
                          </TableCell>
                          <TableCell className="whitespace-nowrap text-right font-mono text-sm">
                            {fmtYen(a.amount)}
                          </TableCell>
                          <TableCell className="whitespace-nowrap">
                            <Badge variant={urgency === "緊急" ? "destructive" : "secondary"}>
                              {urgency}
                            </Badge>
                          </TableCell>
                          <TableCell className="whitespace-nowrap">
                            <Badge variant={STATUS_VARIANT[a.status] ?? "outline"}>
                              {STATUS_LABELS[a.status] ?? a.status}
                            </Badge>
                          </TableCell>
                          <TableCell className="font-mono text-xs text-muted-foreground">
                            {new Date(a.submitted_at).toLocaleDateString("ja-JP")}
                          </TableCell>
                        </TableRow>
                      );
                    })
                  )}
                </TableBody>
              </Table>
            </div>
          )}
          <p className="mt-2 text-xs text-muted-foreground">
            {filtered.length} 件表示 / 全 {data?.total ?? 0} 件
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
