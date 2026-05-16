"use client";

import { useState, useMemo } from "react";
import { Search, CheckCircle2, AlertTriangle, XCircle } from "lucide-react";

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
  CONSTRUCTION_CHECKS,
  CL_STATUS_LABELS,
  type ConstructionLegalStatus,
} from "@/lib/mock-data";
import { AiDisclaimerBanner } from "@/components/layout/ai-disclaimer-banner";

const STATUS_VARIANT: Record<
  ConstructionLegalStatus,
  "default" | "secondary" | "destructive" | "outline"
> = {
  ok: "default",
  warning: "secondary",
  ng: "destructive",
};

const LAWS = Array.from(new Set(CONSTRUCTION_CHECKS.map((c) => c.law)));

function StatusIcon({ status }: { status: ConstructionLegalStatus }) {
  if (status === "ok") return <CheckCircle2 className="h-4 w-4 text-emerald-500" />;
  if (status === "warning") return <AlertTriangle className="h-4 w-4 text-amber-500" />;
  return <XCircle className="h-4 w-4 text-destructive" />;
}

export default function ConstructionLegalPage() {
  const [search, setSearch] = useState("");
  const [lawFilter, setLawFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState<ConstructionLegalStatus | "all">("all");

  const filtered = useMemo(() => {
    return CONSTRUCTION_CHECKS.filter((c) => {
      if (search && !c.item.includes(search) && !c.target.includes(search)) return false;
      if (lawFilter !== "all" && c.law !== lawFilter) return false;
      if (statusFilter !== "all" && c.status !== statusFilter) return false;
      return true;
    });
  }, [search, lawFilter, statusFilter]);

  const summary = useMemo(() => ({
    ok: CONSTRUCTION_CHECKS.filter((c) => c.status === "ok").length,
    warning: CONSTRUCTION_CHECKS.filter((c) => c.status === "warning").length,
    ng: CONSTRUCTION_CHECKS.filter((c) => c.status === "ng").length,
  }), []);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-foreground">建設業法務チェック</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          建設業法・下請法・労働安全衛生法等の遵守状況を管理します
        </p>
      </header>

      <AiDisclaimerBanner variant="inline" />

      <div className="grid grid-cols-3 gap-4">
        <Card className="border-emerald-200 bg-emerald-50 dark:border-emerald-800 dark:bg-emerald-950/30">
          <CardContent className="flex items-center gap-3 pt-4">
            <CheckCircle2 className="h-8 w-8 text-emerald-500" />
            <div>
              <p className="text-2xl font-bold text-emerald-700 dark:text-emerald-400">{summary.ok}</p>
              <p className="text-sm text-emerald-600 dark:text-emerald-500">適合</p>
            </div>
          </CardContent>
        </Card>
        <Card className="border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/30">
          <CardContent className="flex items-center gap-3 pt-4">
            <AlertTriangle className="h-8 w-8 text-amber-500" />
            <div>
              <p className="text-2xl font-bold text-amber-700 dark:text-amber-400">{summary.warning}</p>
              <p className="text-sm text-amber-600 dark:text-amber-500">要確認</p>
            </div>
          </CardContent>
        </Card>
        <Card className="border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950/30">
          <CardContent className="flex items-center gap-3 pt-4">
            <XCircle className="h-8 w-8 text-destructive" />
            <div>
              <p className="text-2xl font-bold text-destructive">{summary.ng}</p>
              <p className="text-sm text-destructive/80">不適合</p>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>チェック一覧</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="mb-4 flex flex-wrap gap-3">
            <div className="relative min-w-48 flex-1">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="チェック項目・対象で検索"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-8"
              />
            </div>
            <Select value={lawFilter} onValueChange={setLawFilter}>
              <SelectTrigger className="w-44">
                <SelectValue placeholder="法令" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">すべての法令</SelectItem>
                {LAWS.map((l) => (
                  <SelectItem key={l} value={l}>{l}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v as ConstructionLegalStatus | "all")}>
              <SelectTrigger className="w-32">
                <SelectValue placeholder="状態" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">すべて</SelectItem>
                {(Object.entries(CL_STATUS_LABELS) as [ConstructionLegalStatus, string][]).map(([v, l]) => (
                  <SelectItem key={v} value={v}>{l}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-8"></TableHead>
                  <TableHead className="w-36">法令</TableHead>
                  <TableHead>チェック項目</TableHead>
                  <TableHead>対象</TableHead>
                  <TableHead className="w-20">状態</TableHead>
                  <TableHead className="w-24">確認日</TableHead>
                  <TableHead className="w-24">確認者</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="py-10 text-center text-sm text-muted-foreground">
                      該当するチェック項目がありません
                    </TableCell>
                  </TableRow>
                ) : (
                  filtered.map((c) => (
                    <TableRow key={c.id}>
                      <TableCell>
                        <StatusIcon status={c.status} />
                      </TableCell>
                      <TableCell>
                        <span className="text-xs font-medium">{c.law}</span>
                      </TableCell>
                      <TableCell className="max-w-[200px]">
                        <p className="text-sm truncate">{c.item}</p>
                      </TableCell>
                      <TableCell className="text-sm whitespace-nowrap">{c.target}</TableCell>
                      <TableCell className="whitespace-nowrap">
                        <Badge variant={STATUS_VARIANT[c.status]}>{CL_STATUS_LABELS[c.status]}</Badge>
                      </TableCell>
                      <TableCell className="font-mono text-xs text-muted-foreground">{c.checkedAt}</TableCell>
                      <TableCell className="text-sm">{c.checker}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
