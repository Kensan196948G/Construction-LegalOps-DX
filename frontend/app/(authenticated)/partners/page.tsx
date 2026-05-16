"use client";

import { useState, useMemo } from "react";
import { Search, CheckCircle2, AlertTriangle } from "lucide-react";

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
import { PARTNERS, type RiskLevel } from "@/lib/mock-data";

const RISK_VARIANT: Record<RiskLevel, "default" | "secondary" | "destructive" | "outline"> = {
  low: "outline",
  medium: "secondary",
  high: "destructive",
  critical: "destructive",
};

const RISK_LABELS: Record<RiskLevel, string> = {
  low: "低",
  medium: "中",
  high: "高",
  critical: "重大",
};

const PARTNER_TYPES = Array.from(new Set(PARTNERS.map((p) => p.type)));

export default function PartnersPage() {
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [riskFilter, setRiskFilter] = useState<RiskLevel | "all">("all");

  const filtered = useMemo(() => {
    return PARTNERS.filter((p) => {
      if (search && !p.name.includes(search) && !p.permitNumber.includes(search)) return false;
      if (typeFilter !== "all" && p.type !== typeFilter) return false;
      if (riskFilter !== "all" && p.riskLevel !== riskFilter) return false;
      return true;
    });
  }, [search, typeFilter, riskFilter]);

  const unverified = PARTNERS.filter((p) => p.antiSocialCheck === "未確認").length;
  const expiringPermit = PARTNERS.filter((p) => {
    const days = Math.ceil((new Date(p.permitExpiry.replace(/\//g, "-")).getTime() - new Date("2026-05-16").getTime()) / 86400000);
    return days <= 90;
  }).length;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-foreground">取引先・協力会社管理</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          元請・下請業者の許可情報・反社確認・保険加入状況を管理します
        </p>
      </header>

      {(unverified > 0 || expiringPermit > 0) && (
        <div className="flex gap-3">
          {unverified > 0 && (
            <Card className="flex-1 border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950/30">
              <CardContent className="flex items-center gap-2 pt-3 pb-3">
                <AlertTriangle className="h-5 w-5 text-destructive" />
                <p className="text-sm font-medium text-destructive">
                  反社チェック未実施: {unverified} 社
                </p>
              </CardContent>
            </Card>
          )}
          {expiringPermit > 0 && (
            <Card className="flex-1 border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/30">
              <CardContent className="flex items-center gap-2 pt-3 pb-3">
                <AlertTriangle className="h-5 w-5 text-amber-500" />
                <p className="text-sm font-medium text-amber-700 dark:text-amber-400">
                  90日以内に許可期限: {expiringPermit} 社
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>取引先一覧</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="mb-4 flex flex-wrap gap-3">
            <div className="relative min-w-48 flex-1">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="会社名・許可番号で検索"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-8"
              />
            </div>
            <Select value={typeFilter} onValueChange={setTypeFilter}>
              <SelectTrigger className="w-36">
                <SelectValue placeholder="区分" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">すべての区分</SelectItem>
                {PARTNER_TYPES.map((t) => (
                  <SelectItem key={t} value={t}>{t}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={riskFilter} onValueChange={(v) => setRiskFilter(v as RiskLevel | "all")}>
              <SelectTrigger className="w-28">
                <SelectValue placeholder="リスク" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">すべて</SelectItem>
                {(Object.entries(RISK_LABELS) as [RiskLevel, string][]).map(([v, l]) => (
                  <SelectItem key={v} value={v}>{l}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>会社名</TableHead>
                  <TableHead className="w-28">区分</TableHead>
                  <TableHead>建設業許可</TableHead>
                  <TableHead className="w-24">許可期限</TableHead>
                  <TableHead className="w-24">反社確認</TableHead>
                  <TableHead className="w-20">保険</TableHead>
                  <TableHead className="w-16 text-right">契約数</TableHead>
                  <TableHead className="w-20">リスク</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={8} className="py-10 text-center text-sm text-muted-foreground">
                      該当する取引先がありません
                    </TableCell>
                  </TableRow>
                ) : (
                  filtered.map((p) => {
                    const permitDays = Math.ceil((new Date(p.permitExpiry.replace(/\//g, "-")).getTime() - new Date("2026-05-16").getTime()) / 86400000);
                    const permitWarning = permitDays <= 90;
                    return (
                      <TableRow key={p.id} className="cursor-pointer hover:bg-muted/50">
                        <TableCell>
                          <p className="text-sm font-medium">{p.name}</p>
                          <p className="text-xs text-muted-foreground">最終取引: {p.lastTransaction}</p>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className="text-xs">{p.type}</Badge>
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">{p.permitNumber}</TableCell>
                        <TableCell>
                          <span className={`font-mono text-xs ${permitWarning ? "font-semibold text-amber-600 dark:text-amber-400" : ""}`}>
                            {p.permitExpiry}
                          </span>
                        </TableCell>
                        <TableCell>
                          {p.antiSocialCheck === "確認済" ? (
                            <div className="flex items-center gap-1 text-xs text-emerald-600 dark:text-emerald-400">
                              <CheckCircle2 className="h-3.5 w-3.5" /> 確認済
                            </div>
                          ) : (
                            <div className="flex items-center gap-1 text-xs text-destructive">
                              <AlertTriangle className="h-3.5 w-3.5" /> 未確認
                            </div>
                          )}
                        </TableCell>
                        <TableCell>
                          {p.insurance === "加入済" ? (
                            <span className="text-xs text-emerald-600 dark:text-emerald-400">加入済</span>
                          ) : (
                            <span className="text-xs text-destructive">未確認</span>
                          )}
                        </TableCell>
                        <TableCell className="text-right font-mono text-sm">{p.contractCount}</TableCell>
                        <TableCell>
                          <Badge variant={RISK_VARIANT[p.riskLevel]}>{RISK_LABELS[p.riskLevel]}</Badge>
                        </TableCell>
                      </TableRow>
                    );
                  })
                )}
              </TableBody>
            </Table>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">{filtered.length} 社表示</p>
        </CardContent>
      </Card>
    </div>
  );
}
