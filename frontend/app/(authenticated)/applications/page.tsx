"use client";

import { useState, useMemo } from "react";
import { Plus, Search } from "lucide-react";
import Link from "next/link";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
  CONTRACT_APPLICATIONS,
  APP_STATUS_LABELS,
  APP_TYPES,
  type AppStatus,
} from "@/lib/mock-data";

const URGENCY_VARIANT = {
  緊急: "destructive",
  通常: "secondary",
  低: "outline",
} as const;

const STATUS_VARIANT: Record<AppStatus, "default" | "secondary" | "destructive" | "outline"> = {
  draft: "outline",
  submitted: "secondary",
  under_review: "default",
  approved: "default",
  rejected: "destructive",
  withdrawn: "outline",
};

function fmtYen(n: number) {
  return "¥" + n.toLocaleString("ja-JP");
}

export default function ApplicationsPage() {
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");

  const filtered = useMemo(() => {
    return CONTRACT_APPLICATIONS.filter((a) => {
      if (search && !a.title.includes(search) && !a.applicant.includes(search) && !a.projectName.includes(search)) return false;
      if (typeFilter !== "all" && a.type !== typeFilter) return false;
      if (statusFilter !== "all" && a.status !== statusFilter) return false;
      return true;
    });
  }, [search, typeFilter, statusFilter]);

  return (
    <div className="space-y-6">
      <header className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">契約申請・稟議</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            契約書の新規申請・変更・更新の稟議管理
          </p>
        </div>
        <Button size="sm" asChild>
          <Link href="/contracts/new">
            <Plus className="mr-1.5 h-4 w-4" />
            新規申請
          </Link>
        </Button>
      </header>

      <Card>
        <CardContent className="pt-4">
          <div className="mb-4 flex flex-wrap gap-3">
            <div className="relative min-w-48 flex-1">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="申請名・申請者・案件名で検索"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-8"
              />
            </div>
            <Select value={typeFilter} onValueChange={setTypeFilter}>
              <SelectTrigger className="w-40">
                <SelectValue placeholder="申請種別" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">すべての種別</SelectItem>
                {APP_TYPES.map((t) => (
                  <SelectItem key={t} value={t}>{t}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-36">
                <SelectValue placeholder="ステータス" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">すべて</SelectItem>
                {(Object.entries(APP_STATUS_LABELS) as [AppStatus, string][]).map(([v, l]) => (
                  <SelectItem key={v} value={v}>{l}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-36">申請 ID</TableHead>
                  <TableHead className="w-24">種別</TableHead>
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
                      該当する申請がありません
                    </TableCell>
                  </TableRow>
                ) : (
                  filtered.map((a) => (
                    <TableRow key={a.id} className="cursor-pointer hover:bg-muted/50">
                      <TableCell className="font-mono text-xs">{a.id}</TableCell>
                      <TableCell className="text-sm">{a.type}</TableCell>
                      <TableCell className="max-w-[220px]">
                        <p className="text-sm font-medium truncate">{a.title}</p>
                        <p className="text-xs text-muted-foreground truncate">{a.projectName}</p>
                      </TableCell>
                      <TableCell className="text-sm whitespace-nowrap">{a.applicant}</TableCell>
                      <TableCell className="text-right font-mono text-sm whitespace-nowrap">{fmtYen(a.amount)}</TableCell>
                      <TableCell className="whitespace-nowrap">
                        <Badge variant={URGENCY_VARIANT[a.urgency]}>{a.urgency}</Badge>
                      </TableCell>
                      <TableCell className="whitespace-nowrap">
                        <Badge variant={STATUS_VARIANT[a.status]}>{APP_STATUS_LABELS[a.status]}</Badge>
                      </TableCell>
                      <TableCell className="font-mono text-xs text-muted-foreground">
                        {a.submittedAt}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            {filtered.length} 件表示
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
