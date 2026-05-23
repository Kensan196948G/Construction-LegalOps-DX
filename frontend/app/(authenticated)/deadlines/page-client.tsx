"use client";

import { useState, useMemo } from "react";
import { CalendarClock, AlertTriangle, RefreshCw } from "lucide-react";
import Link from "next/link";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import { CONTRACT_DEADLINES } from "@/lib/mock-data";

function DaysLeftBadge({ days }: { days: number }) {
  if (days <= 7) return <Badge variant="destructive">残 {days} 日</Badge>;
  if (days <= 30) return <Badge variant="secondary" className="bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200">残 {days} 日</Badge>;
  return <Badge variant="outline">{days} 日後</Badge>;
}

export default function DeadlinesPage() {
  const [filter, setFilter] = useState("all");

  const filtered = useMemo(() => {
    return CONTRACT_DEADLINES.filter((c) => {
      if (filter === "urgent") return c.daysLeft <= 30;
      if (filter === "auto") return c.autoRenew;
      return true;
    });
  }, [filter]);

  const urgent = CONTRACT_DEADLINES.filter((c) => c.daysLeft <= 30).length;
  const expiringSoon = CONTRACT_DEADLINES.filter((c) => c.daysLeft <= 60).length;
  const autoRenew = CONTRACT_DEADLINES.filter((c) => c.autoRenew).length;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-foreground">契約期限・更新管理</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          期限が迫る契約のアラートと自動更新設定を管理します
        </p>
      </header>

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
            <RefreshCw className="h-8 w-8 text-primary" />
            <div>
              <p className="text-2xl font-bold">{autoRenew}</p>
              <p className="text-sm text-muted-foreground">自動更新設定済み</p>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle>期限一覧（近い順）</CardTitle>
          <Select value={filter} onValueChange={setFilter}>
            <SelectTrigger className="w-40">
              <SelectValue placeholder="絞り込み" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">すべての契約</SelectItem>
              <SelectItem value="urgent">30日以内</SelectItem>
              <SelectItem value="auto">自動更新のみ</SelectItem>
            </SelectContent>
          </Select>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>契約名</TableHead>
                  <TableHead className="w-40">取引先</TableHead>
                  <TableHead className="w-24">満了日</TableHead>
                  <TableHead className="w-28">残り日数</TableHead>
                  <TableHead className="w-20">自動更新</TableHead>
                  <TableHead className="w-20">保証期間</TableHead>
                  <TableHead className="w-24">担当者</TableHead>
                  <TableHead className="w-16"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={8} className="py-10 text-center text-sm text-muted-foreground">
                      該当する契約がありません
                    </TableCell>
                  </TableRow>
                ) : (
                  filtered.map((c) => (
                    <TableRow
                      key={c.id}
                      className={c.daysLeft <= 7 ? "bg-red-50/50 dark:bg-red-950/20" : c.daysLeft <= 30 ? "bg-amber-50/50 dark:bg-amber-950/20" : ""}
                    >
                      <TableCell className="max-w-[200px]">
                        <p className="text-sm font-medium truncate">{c.title}</p>
                        <p className="text-xs text-muted-foreground">{c.type}</p>
                      </TableCell>
                      <TableCell className="text-sm whitespace-nowrap">{c.counterparty}</TableCell>
                      <TableCell className="font-mono text-sm whitespace-nowrap">{c.expiresAt}</TableCell>
                      <TableCell className="whitespace-nowrap">
                        <DaysLeftBadge days={c.daysLeft} />
                      </TableCell>
                      <TableCell className="whitespace-nowrap">
                        {c.autoRenew ? (
                          <Badge variant="default" className="gap-1">
                            <RefreshCw className="h-3 w-3" /> あり
                          </Badge>
                        ) : (
                          <span className="text-xs text-muted-foreground">なし</span>
                        )}
                      </TableCell>
                      <TableCell className="text-sm whitespace-nowrap">{c.guaranteePeriod}</TableCell>
                      <TableCell className="text-sm whitespace-nowrap">{c.owner}</TableCell>
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
        </CardContent>
      </Card>
    </div>
  );
}
