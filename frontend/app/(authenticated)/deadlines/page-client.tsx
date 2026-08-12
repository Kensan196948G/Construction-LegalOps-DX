"use client";

import { useMemo, useState } from "react";
import { AlertTriangle, CalendarClock, RefreshCw } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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
import { Alert, AlertDescription } from "@/components/ui/alert";

interface DeadlineContract {
  id: number | string;
  contract_no: string | null;
  title: string;
  counterparty: string | null;
  contract_type: string;
  end_date: string | null;
  amount: number | null;
  status: string;
}

interface DeadlinesPageProps {
  contracts: DeadlineContract[];
  error: string | null;
}

function todayString(): string {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function daysUntil(endDate: string): number {
  const end = new Date(`${endDate}T00:00:00+09:00`);
  const start = new Date(`${todayString()}T00:00:00+09:00`);
  return Math.round((end.getTime() - start.getTime()) / 86_400_000);
}

function DaysLeftBadge({ days }: { days: number }) {
  if (days < 0) return <Badge variant="destructive">期限切れ</Badge>;
  if (days <= 7) return <Badge variant="destructive">残 {days} 日</Badge>;
  if (days <= 30) {
    return (
      <Badge variant="secondary" className="bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200">
        残 {days} 日
      </Badge>
    );
  }
  return <Badge variant="outline">{days} 日後</Badge>;
}

function formatAmount(amount: number | null): string {
  if (amount === null || amount === undefined) return "—";
  return `${amount.toLocaleString("ja-JP")} 円`;
}

export default function DeadlinesPage({ contracts, error }: DeadlinesPageProps) {
  const [filter, setFilter] = useState("all");

  const dated = useMemo(
    () =>
      contracts
        .filter((c) => c.end_date)
        .map((c) => ({ ...c, daysLeft: daysUntil(c.end_date as string) }))
        .sort((a, b) => a.daysLeft - b.daysLeft),
    [contracts],
  );

  const filtered = useMemo(() => {
    if (filter === "urgent") return dated.filter((c) => c.daysLeft >= 0 && c.daysLeft <= 30);
    if (filter === "expired") return dated.filter((c) => c.daysLeft < 0);
    return dated;
  }, [dated, filter]);

  const urgent = dated.filter((c) => c.daysLeft >= 0 && c.daysLeft <= 30).length;
  const expiringSoon = dated.filter((c) => c.daysLeft >= 0 && c.daysLeft <= 60).length;
  const expired = dated.filter((c) => c.daysLeft < 0).length;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-foreground">契約期限・更新管理</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          契約台帳の期間情報から算出した期限一覧（実データ連動）
        </p>
      </header>

      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" aria-hidden="true" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-3 gap-4">
        <Card className={urgent > 0 ? "border-red-300 bg-red-50 dark:border-red-800 dark:bg-red-950/30" : ""}>
          <CardContent className="flex items-center gap-3 pt-4">
            <AlertTriangle className={`h-8 w-8 ${urgent > 0 ? "text-destructive" : "text-muted-foreground"}`} />
            <div>
              <p className="text-2xl font-bold">{urgent}</p>
              <p className="text-sm text-muted-foreground">30日以内に期限</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 pt-4">
            <CalendarClock className="h-8 w-8 text-amber-500" />
            <div>
              <p className="text-2xl font-bold">{expiringSoon}</p>
              <p className="text-sm text-muted-foreground">60日以内に期限</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 pt-4">
            <RefreshCw className="h-8 w-8 text-destructive" />
            <div>
              <p className="text-2xl font-bold">{expired}</p>
              <p className="text-sm text-muted-foreground">期限切れ</p>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <div className="flex items-center justify-between border-b px-6 py-4">
          <p className="text-sm font-semibold">期限一覧（近い順）</p>
          <Select value={filter} onValueChange={setFilter}>
            <SelectTrigger className="w-40" aria-label="絞り込み">
              <SelectValue placeholder="絞り込み" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">すべての契約</SelectItem>
              <SelectItem value="urgent">30日以内</SelectItem>
              <SelectItem value="expired">期限切れ</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="rounded-md border-x-0 border-b-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>契約名</TableHead>
                <TableHead className="w-40">取引先</TableHead>
                <TableHead className="w-28">満了日</TableHead>
                <TableHead className="w-28">残り日数</TableHead>
                <TableHead className="w-32">金額</TableHead>
                <TableHead className="w-20">状態</TableHead>
                <TableHead className="w-16"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="py-10 text-center text-sm text-muted-foreground">
                    {dated.length === 0
                      ? "満了日が設定された契約がありません。契約台帳から期間を登録してください。"
                      : "該当する契約がありません"}
                  </TableCell>
                </TableRow>
              ) : (
                filtered.map((c) => (
                  <TableRow
                    key={c.id}
                    className={
                      c.daysLeft < 0
                        ? "bg-red-50/50 dark:bg-red-950/20"
                        : c.daysLeft <= 30
                          ? "bg-amber-50/50 dark:bg-amber-950/20"
                          : ""
                    }
                  >
                    <TableCell className="max-w-[200px]">
                      <p className="truncate text-sm font-medium">{c.title}</p>
                      <p className="text-xs text-muted-foreground">
                        {c.contract_no ?? `ID ${c.id}`} / {c.contract_type}
                      </p>
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-sm">
                      {c.counterparty ?? "—"}
                    </TableCell>
                    <TableCell className="whitespace-nowrap font-mono text-sm">
                      {c.end_date}
                    </TableCell>
                    <TableCell className="whitespace-nowrap">
                      <DaysLeftBadge days={c.daysLeft} />
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-sm">
                      {formatAmount(c.amount)}
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-sm">{c.status}</TableCell>
                    <TableCell>
                      <Button variant="ghost" size="sm" asChild>
                        <Link href={`/contracts/${c.id}`}>詳細</Link>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      </Card>
    </div>
  );
}
