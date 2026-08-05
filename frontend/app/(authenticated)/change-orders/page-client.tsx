"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, FileDiff, RefreshCw, Search } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import { Textarea } from "@/components/ui/textarea";
import { changeOrdersApi } from "@/lib/api";
import type { ChangeOrder } from "@/lib/api/schemas";
import { AiDisclaimerBanner } from "@/components/layout/ai-disclaimer-banner";
import { formatCurrency } from "@/lib/utils/format-currency";

const TYPE_LABELS: Record<string, string> = {
  design_change: "設計変更",
  additional_work: "追加工事",
  verbal_direction: "口頭指示",
  schedule_extension: "工期延長",
  price_slide: "価格スライド",
  claim: "クレーム",
  other: "その他",
};

const STATUS_LABELS: Record<string, string> = {
  registered: "登録",
  notice_sent: "通知済",
  in_consultation: "協議中",
  approved: "承認済",
  rejected: "却下",
  forfeited: "失権",
};

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  registered: "outline",
  notice_sent: "secondary",
  in_consultation: "secondary",
  approved: "default",
  rejected: "destructive",
  forfeited: "destructive",
};

export default function ChangeOrdersPage() {
  const [rows, setRows] = useState<ChangeOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [createOpen, setCreateOpen] = useState(false);
  const [detail, setDetail] = useState<ChangeOrder | null>(null);

  const [form, setForm] = useState({
    contract_id: "",
    change_type: "design_change",
    title: "",
    status: "registered",
    requested_by: "",
    requested_at: "",
    response_deadline: "",
    amount_jpy: "",
    schedule_impact_days: "",
    description: "",
  });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const list = await changeOrdersApi.list({ page: 1, size: 100 });
      setRows(list.items);
      setOffline(false);
    } catch {
      setRows([]);
      setOffline(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const filtered = useMemo(() => {
    return rows.filter((c) => {
      if (search && !c.title.includes(search) && !c.change_no.includes(search)) return false;
      if (statusFilter !== "all" && c.status !== statusFilter) return false;
      return true;
    });
  }, [rows, search, statusFilter]);

  const forfeitCount = rows.filter((c) => c.forfeiture_warning).length;
  const approvedDelta = rows
    .filter((c) => c.status === "approved")
    .reduce((sum, c) => sum + (c.amount_jpy ?? 0), 0);
  const openCount = rows.filter((c) => !["approved", "rejected", "forfeited"].includes(c.status)).length;

  const createOrder = async () => {
    try {
      const created = await changeOrdersApi.create(form.contract_id, {
        change_type: form.change_type as ChangeOrder["change_type"],
        title: form.title,
        status: form.status as ChangeOrder["status"],
        requested_by: form.requested_by || undefined,
        requested_at: form.requested_at || undefined,
        response_deadline: form.response_deadline || undefined,
        amount_jpy: form.amount_jpy ? Number(form.amount_jpy) : undefined,
        schedule_impact_days: form.schedule_impact_days ? Number(form.schedule_impact_days) : undefined,
        description: form.description || undefined,
      });
      setRows((prev) => [created, ...prev]);
      setCreateOpen(false);
      setForm({
        contract_id: "",
        change_type: "design_change",
        title: "",
        status: "registered",
        requested_by: "",
        requested_at: "",
        response_deadline: "",
        amount_jpy: "",
        schedule_impact_days: "",
        description: "",
      });
    } catch {
      setOffline(true);
    }
  };

  const isOverdue = (deadline?: string | null) =>
    deadline ? new Date(deadline).getTime() < Date.now() : false;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-foreground">変更契約・クレーム管理</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            設計変更指示・追加工事・工期延長・価格スライド・口頭指示の追認を管理します
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>変更契約登録</Button>
      </header>

      <AiDisclaimerBanner variant="inline" />

      {offline && (
        <Badge variant="outline" className="border-amber-400 bg-amber-50 text-amber-800 dark:bg-amber-950">
          API 未接続（バックエンド起動後に自動再接続）
        </Badge>
      )}

      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardContent className="flex items-center gap-3 pt-4">
            <FileDiff className="h-8 w-8 text-primary" />
            <div>
              <p className="text-2xl font-bold">{loading ? "—" : openCount}</p>
              <p className="text-sm text-muted-foreground">未確定の変更案件</p>
            </div>
          </CardContent>
        </Card>
        <Card className={forfeitCount > 0 ? "border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950/30" : ""}>
          <CardContent className="flex items-center gap-3 pt-4">
            <AlertTriangle className="h-8 w-8 text-destructive" />
            <div>
              <p className="text-2xl font-bold">{loading ? "—" : forfeitCount}</p>
              <p className="text-sm text-muted-foreground">失権リスク警告</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 pt-4">
            <div>
              <p className="text-2xl font-bold">{loading ? "—" : formatCurrency(approvedDelta)}</p>
              <p className="text-sm text-muted-foreground">承認済み変更額（累積）</p>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle>変更契約・クレーム一覧</CardTitle>
          <Button variant="ghost" size="sm" onClick={() => void load()} disabled={loading}>
            <RefreshCw className={`mr-1 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            更新
          </Button>
        </CardHeader>
        <CardContent>
          <div className="mb-4 flex flex-wrap gap-3">
            <div className="relative min-w-48 flex-1">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="件名・変更番号で検索"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-8"
              />
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-36">
                <SelectValue placeholder="状態" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">すべて</SelectItem>
                {Object.entries(STATUS_LABELS).map(([v, l]) => (
                  <SelectItem key={v} value={v}>{l}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-32">番号</TableHead>
                  <TableHead className="w-28">種別</TableHead>
                  <TableHead>件名</TableHead>
                  <TableHead className="w-28">状態</TableHead>
                  <TableHead className="w-28">通知期限</TableHead>
                  <TableHead className="w-28 text-right">金額</TableHead>
                  <TableHead className="w-20">工期影響</TableHead>
                  <TableHead className="w-16" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={8} className="py-10 text-center text-sm text-muted-foreground">
                      変更契約・クレームの記録がありません
                    </TableCell>
                  </TableRow>
                ) : (
                  filtered.map((c) => (
                    <TableRow key={String(c.id)}>
                      <TableCell className="font-mono text-xs">{c.change_no}</TableCell>
                      <TableCell className="text-sm">{TYPE_LABELS[c.change_type] ?? c.change_type}</TableCell>
                      <TableCell className="max-w-[240px]">
                        <p className="truncate text-sm font-medium">{c.title}</p>
                        {c.forfeiture_warning && (
                          <p className="flex items-center gap-1 text-xs text-destructive">
                            <AlertTriangle className="h-3 w-3" />
                            {c.forfeiture_warning}
                          </p>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge variant={STATUS_VARIANT[c.status] ?? "outline"}>
                          {STATUS_LABELS[c.status] ?? c.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm whitespace-nowrap">
                        {c.response_deadline ? (
                          <span className={isOverdue(c.response_deadline) ? "font-semibold text-destructive" : ""}>
                            {c.response_deadline}
                          </span>
                        ) : (
                          "—"
                        )}
                      </TableCell>
                      <TableCell className="text-right text-sm tabular-nums">
                        {c.amount_jpy === null || c.amount_jpy === undefined ? "—" : formatCurrency(c.amount_jpy)}
                      </TableCell>
                      <TableCell className="text-center text-sm">
                        {c.schedule_impact_days === null || c.schedule_impact_days === undefined
                          ? "—"
                          : `${c.schedule_impact_days} 日`}
                      </TableCell>
                      <TableCell>
                        <Button variant="ghost" size="sm" onClick={() => setDetail(c)}>
                          詳細
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

      {/* 新規登録 */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>変更契約・クレーム登録</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>契約 ID *</Label>
                <Input type="number" value={form.contract_id} onChange={(e) => setForm({ ...form, contract_id: e.target.value })} />
              </div>
              <div>
                <Label>種別</Label>
                <Select value={form.change_type} onValueChange={(v) => setForm({ ...form, change_type: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {Object.entries(TYPE_LABELS).map(([v, l]) => (
                      <SelectItem key={v} value={v}>{l}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div>
              <Label>件名 *</Label>
              <Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>状態</Label>
                <Select value={form.status} onValueChange={(v) => setForm({ ...form, status: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {Object.entries(STATUS_LABELS).map(([v, l]) => (
                      <SelectItem key={v} value={v}>{l}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>申出者</Label>
                <Input value={form.requested_by} onChange={(e) => setForm({ ...form, requested_by: e.target.value })} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>申出日</Label>
                <Input type="date" value={form.requested_at} onChange={(e) => setForm({ ...form, requested_at: e.target.value })} />
              </div>
              <div>
                <Label>回答期限</Label>
                <Input type="date" value={form.response_deadline} onChange={(e) => setForm({ ...form, response_deadline: e.target.value })} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>変更金額（円）</Label>
                <Input type="number" value={form.amount_jpy} onChange={(e) => setForm({ ...form, amount_jpy: e.target.value })} />
              </div>
              <div>
                <Label>工期影響（日）</Label>
                <Input type="number" value={form.schedule_impact_days} onChange={(e) => setForm({ ...form, schedule_impact_days: e.target.value })} />
              </div>
            </div>
            <div>
              <Label>内容</Label>
              <Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>キャンセル</Button>
            <Button onClick={() => void createOrder()} disabled={!form.title || !form.contract_id}>
              登録
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 詳細 */}
      <Dialog open={detail !== null} onOpenChange={(v) => !v && setDetail(null)}>
        <DialogContent className="max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{detail?.title ?? "変更契約詳細"}</DialogTitle>
          </DialogHeader>
          {detail && (
            <div className="space-y-3 text-sm">
              <div className="flex flex-wrap gap-2">
                <Badge variant={STATUS_VARIANT[detail.status] ?? "outline"}>
                  {STATUS_LABELS[detail.status] ?? detail.status}
                </Badge>
                <Badge variant="outline">{TYPE_LABELS[detail.change_type] ?? detail.change_type}</Badge>
                <Badge variant="outline">{detail.change_no}</Badge>
              </div>
              <p>契約 ID: {String(detail.contract_id)}</p>
              {detail.requested_at && <p>申出日: {detail.requested_at}</p>}
              {detail.response_deadline && (
                <p className={isOverdue(detail.response_deadline) ? "font-semibold text-destructive" : ""}>
                  回答期限: {detail.response_deadline}
                </p>
              )}
              {detail.amount_jpy !== null && detail.amount_jpy !== undefined && (
                <p>変更金額: {formatCurrency(detail.amount_jpy)}</p>
              )}
              {detail.schedule_impact_days !== null && detail.schedule_impact_days !== undefined && (
                <p>工期影響: {detail.schedule_impact_days} 日</p>
              )}
              {detail.cumulative_after_jpy !== null && detail.cumulative_after_jpy !== undefined && (
                <p>変更後累積金額: {formatCurrency(detail.cumulative_after_jpy)}</p>
              )}
              {detail.forfeiture_warning && (
                <p className="flex items-center gap-1 text-destructive">
                  <AlertTriangle className="h-4 w-4" />
                  {detail.forfeiture_warning}
                </p>
              )}
              {detail.description && <p className="text-muted-foreground">{detail.description}</p>}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
