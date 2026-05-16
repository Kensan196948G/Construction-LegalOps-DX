"use client";

import { useState, useMemo } from "react";
import { Search, Swords } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
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
  DISPUTES,
  DISPUTE_STATUS_LABELS,
  DISPUTE_TYPES,
  type DisputeStatus,
} from "@/lib/mock-data";
import { AiDisclaimerBanner } from "@/components/layout/ai-disclaimer-banner";

const STATUS_VARIANT: Record<DisputeStatus, "default" | "secondary" | "destructive" | "outline"> = {
  open: "destructive",
  investigating: "secondary",
  resolved: "default",
  escalated: "destructive",
};

const PRIORITY_VARIANT = {
  高: "destructive",
  中: "secondary",
  低: "outline",
} as const;

function fmtYen(n: number) {
  return "¥" + n.toLocaleString("ja-JP");
}

export default function DisputesPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<DisputeStatus | "all">("all");
  const [typeFilter, setTypeFilter] = useState("all");

  const filtered = useMemo(() => {
    return DISPUTES.filter((d) => {
      if (search && !d.title.includes(search) && !d.counterparty.includes(search)) return false;
      if (statusFilter !== "all" && d.status !== statusFilter) return false;
      if (typeFilter !== "all" && d.type !== typeFilter) return false;
      return true;
    });
  }, [search, statusFilter, typeFilter]);

  const openCount = DISPUTES.filter((d) => d.status === "open" || d.status === "investigating").length;
  const escalatedCount = DISPUTES.filter((d) => d.status === "escalated").length;
  const totalAmount = DISPUTES.filter((d) => d.amount !== null).reduce((sum, d) => sum + (d.amount ?? 0), 0);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-foreground">紛争・クレーム管理</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          工事に関する紛争・クレームの記録と対応状況を管理します
        </p>
      </header>

      <AiDisclaimerBanner variant="inline" />

      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardContent className="flex items-center gap-3 pt-4">
            <Swords className="h-8 w-8 text-destructive" />
            <div>
              <p className="text-2xl font-bold">{openCount}</p>
              <p className="text-sm text-muted-foreground">対応中・調査中</p>
            </div>
          </CardContent>
        </Card>
        <Card className={escalatedCount > 0 ? "border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950/30" : ""}>
          <CardContent className="flex items-center gap-3 pt-4">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-destructive/10">
              <span className="text-lg font-bold text-destructive">!</span>
            </div>
            <div>
              <p className="text-2xl font-bold">{escalatedCount}</p>
              <p className="text-sm text-muted-foreground">エスカレーション</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 pt-4">
            <div>
              <p className="text-2xl font-bold">{fmtYen(totalAmount)}</p>
              <p className="text-sm text-muted-foreground">争議金額合計（申告分）</p>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>紛争・クレーム一覧</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="mb-4 flex flex-wrap gap-3">
            <div className="relative min-w-48 flex-1">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="案件名・相手方で検索"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-8"
              />
            </div>
            <Select value={typeFilter} onValueChange={setTypeFilter}>
              <SelectTrigger className="w-40">
                <SelectValue placeholder="種別" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">すべての種別</SelectItem>
                {DISPUTE_TYPES.map((t: string) => (
                  <SelectItem key={t} value={t}>{t}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v as DisputeStatus | "all")}>
              <SelectTrigger className="w-36">
                <SelectValue placeholder="状態" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">すべて</SelectItem>
                {(Object.entries(DISPUTE_STATUS_LABELS) as [DisputeStatus, string][]).map(([v, l]) => (
                  <SelectItem key={v} value={v}>{l}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-32">ID</TableHead>
                  <TableHead className="w-28">種別</TableHead>
                  <TableHead>案件名</TableHead>
                  <TableHead className="w-36">相手方</TableHead>
                  <TableHead className="w-24">状態</TableHead>
                  <TableHead className="w-16">優先度</TableHead>
                  <TableHead className="w-28 text-right">争議金額</TableHead>
                  <TableHead className="w-20">担当</TableHead>
                  <TableHead className="w-24">登録日</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={9} className="py-10 text-center text-sm text-muted-foreground">
                      該当する案件がありません
                    </TableCell>
                  </TableRow>
                ) : (
                  filtered.map((d) => (
                    <TableRow key={d.id} className="cursor-pointer hover:bg-muted/50">
                      <TableCell className="font-mono text-xs">{d.id}</TableCell>
                      <TableCell className="text-sm whitespace-nowrap">{d.type}</TableCell>
                      <TableCell className="max-w-[200px]">
                        <p className="text-sm font-medium truncate">{d.title}</p>
                      </TableCell>
                      <TableCell className="text-sm whitespace-nowrap">{d.counterparty}</TableCell>
                      <TableCell className="whitespace-nowrap">
                        <Badge variant={STATUS_VARIANT[d.status]}>{DISPUTE_STATUS_LABELS[d.status]}</Badge>
                      </TableCell>
                      <TableCell className="whitespace-nowrap">
                        <Badge variant={PRIORITY_VARIANT[d.priority]}>{d.priority}</Badge>
                      </TableCell>
                      <TableCell className="text-right font-mono text-sm whitespace-nowrap">
                        {d.amount !== null ? fmtYen(d.amount) : <span className="text-muted-foreground">—</span>}
                      </TableCell>
                      <TableCell className="text-sm whitespace-nowrap">{d.assignee}</TableCell>
                      <TableCell className="font-mono text-xs text-muted-foreground">{d.registeredAt}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">{filtered.length} 件表示</p>
        </CardContent>
      </Card>
    </div>
  );
}
