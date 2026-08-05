"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, RefreshCw, Search, Swords } from "lucide-react";

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
import { disputesApi } from "@/lib/api";
import type { Dispute, DisputeDetail, DisputeExposure } from "@/lib/api/schemas";
import { AiDisclaimerBanner } from "@/components/layout/ai-disclaimer-banner";
import { DISPUTES, type DisputeStatus } from "@/lib/mock-data";
import { formatCurrency } from "@/lib/utils/format-currency";

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  open: "destructive",
  investigating: "secondary",
  escalated: "destructive",
  resolved: "default",
  closed: "outline",
};

const STATUS_LABELS: Record<string, string> = {
  open: "対応中",
  investigating: "調査中",
  escalated: "エスカレーション",
  resolved: "解決済み",
  closed: "クローズ",
};

const TYPE_LABELS: Record<string, string> = {
  claim: "クレーム",
  defect: "瑕疵",
  delay: "遅延",
  payment: "支払",
  labor: "労務",
  accident: "事故",
  other: "その他",
};

const PRIORITY_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  高: "destructive",
  中: "secondary",
  低: "outline",
};

interface DisputeRow {
  id: string;
  title: string;
  counterparty: string;
  status: string;
  priority: string;
  amount: number | null;
  registeredAt: string;
  disputeType?: string;
}

function toRow(d: Dispute): DisputeRow {
  return {
    id: String(d.id),
    title: d.title,
    counterparty: d.counterparty ?? "—",
    status: d.status,
    priority: d.priority,
    amount: d.amount_claimed_jpy ?? null,
    registeredAt: d.created_at.slice(0, 10),
    disputeType: d.dispute_type,
  };
}

function toMockRow(d: (typeof DISPUTES)[number]): DisputeRow {
  return {
    id: d.id,
    title: d.title,
    counterparty: d.counterparty,
    status: d.status,
    priority: d.priority,
    amount: d.amount ?? null,
    registeredAt: d.registeredAt,
  };
}

export default function DisputesPage() {
  const [rows, setRows] = useState<DisputeRow[]>(() => DISPUTES.map(toMockRow));
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | DisputeStatus>("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [detail, setDetail] = useState<DisputeDetail | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  const [form, setForm] = useState({
    title: "",
    dispute_type: "claim",
    status: "open",
    priority: "中",
    counterparty: "",
    amount_claimed_jpy: "",
    reserve_amount_jpy: "",
    statute_limitations_date: "",
    notice_deadline: "",
    description: "",
  });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [list, exposure] = await Promise.all([
        disputesApi.list({ page: 1, size: 100 }),
        disputesApi.exposure(),
      ]);
      setRows(list.items.map(toRow));
      setExposure(exposure);
      setOffline(false);
    } catch {
      setRows(DISPUTES.map(toMockRow));
      setOffline(true);
    } finally {
      setLoading(false);
    }
  }, []);

  const [exposure, setExposure] = useState<DisputeExposure | null>(null);

  useEffect(() => {
    void load();
  }, [load]);

  const filtered = useMemo(() => {
    return rows.filter((d) => {
      if (search && !d.title.includes(search) && !d.counterparty.includes(search)) return false;
      if (statusFilter !== "all" && d.status !== statusFilter) return false;
      if (typeFilter !== "all" && d.disputeType && d.disputeType !== typeFilter) return false;
      return true;
    });
  }, [rows, search, statusFilter, typeFilter]);

  const openCount = rows.filter((d) => d.status === "open" || d.status === "investigating").length;
  const escalatedCount = rows.filter((d) => d.status === "escalated").length;
  const totalAmount = rows.reduce((sum, d) => sum + (d.amount ?? 0), 0);

  const openDetail = async (id: string) => {
    try {
      const item = await disputesApi.get(id);
      setDetail(item);
    } catch {
      setDetail(null);
    }
  };

  const createDispute = async () => {
    try {
      const created = await disputesApi.create({
        title: form.title,
        dispute_type: form.dispute_type as Dispute["dispute_type"],
        status: form.status as Dispute["status"],
        priority: form.priority as "高" | "中" | "低",
        counterparty: form.counterparty || undefined,
        amount_claimed_jpy: form.amount_claimed_jpy ? Number(form.amount_claimed_jpy) : undefined,
        reserve_amount_jpy: form.reserve_amount_jpy ? Number(form.reserve_amount_jpy) : undefined,
        statute_limitations_date: form.statute_limitations_date || undefined,
        notice_deadline: form.notice_deadline || undefined,
        description: form.description || undefined,
      });
      setRows((prev) => [toRow(created), ...prev]);
      setCreateOpen(false);
      setForm({
        title: "",
        dispute_type: "claim",
        status: "open",
        priority: "中",
        counterparty: "",
        amount_claimed_jpy: "",
        reserve_amount_jpy: "",
        statute_limitations_date: "",
        notice_deadline: "",
        description: "",
      });
    } catch {
      setOffline(true);
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-foreground">紛争・クレーム管理</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            工事に関する紛争・クレームの記録と対応状況を管理します
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>新規案件登録</Button>
      </header>

      <AiDisclaimerBanner variant="inline" />

      {offline && (
        <Badge variant="outline" className="border-amber-400 bg-amber-50 text-amber-800 dark:bg-amber-950">
          オフライン表示（モックデータ）
        </Badge>
      )}

      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardContent className="flex items-center gap-3 pt-4">
            <Swords className="h-8 w-8 text-destructive" />
            <div>
              <p className="text-2xl font-bold">{loading ? "—" : openCount}</p>
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
              <p className="text-2xl font-bold">{loading ? "—" : escalatedCount}</p>
              <p className="text-sm text-muted-foreground">エスカレーション</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 pt-4">
            <AlertTriangle className="h-8 w-8 text-amber-500" />
            <div>
              <p className="text-2xl font-bold">
                {loading ? "—" : formatCurrency(exposure?.total_claimed_jpy ?? totalAmount)}
              </p>
              <p className="text-sm text-muted-foreground">争議金額合計（申告分）</p>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle>紛争・クレーム一覧</CardTitle>
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
                {Object.entries(TYPE_LABELS).map(([v, l]) => (
                  <SelectItem key={v} value={v}>{l}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={statusFilter}
              onValueChange={(v) => setStatusFilter(v as "all" | DisputeStatus)}
            >
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
                  <TableHead className="w-32">ID</TableHead>
                  <TableHead className="w-28">種別</TableHead>
                  <TableHead>案件名</TableHead>
                  <TableHead className="w-36">相手方</TableHead>
                  <TableHead className="w-24">状態</TableHead>
                  <TableHead className="w-16">優先度</TableHead>
                  <TableHead className="w-28 text-right">争議金額</TableHead>
                  <TableHead className="w-24">登録日</TableHead>
                  <TableHead className="w-16" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={9} className="py-10 text-center text-sm text-muted-foreground">
                      該当する紛争・クレームがありません
                    </TableCell>
                  </TableRow>
                ) : (
                  filtered.map((d) => (
                    <TableRow key={d.id}>
                      <TableCell className="font-mono text-xs">{d.id}</TableCell>
                      <TableCell className="text-sm">
                        {d.disputeType ? TYPE_LABELS[d.disputeType] ?? d.disputeType : "—"}
                      </TableCell>
                      <TableCell className="max-w-[240px]">
                        <p className="truncate text-sm font-medium">{d.title}</p>
                      </TableCell>
                      <TableCell className="text-sm">{d.counterparty}</TableCell>
                      <TableCell>
                        <Badge variant={STATUS_VARIANT[d.status] ?? "outline"}>
                          {STATUS_LABELS[d.status] ?? d.status}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant={PRIORITY_VARIANT[d.priority] ?? "outline"}>{d.priority}</Badge>
                      </TableCell>
                      <TableCell className="text-right text-sm tabular-nums">
                        {d.amount === null ? "—" : formatCurrency(d.amount)}
                      </TableCell>
                      <TableCell className="text-sm">{d.registeredAt}</TableCell>
                      <TableCell>
                        <Button variant="ghost" size="sm" onClick={() => void openDetail(d.id)}>
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

      {/* 新規案件登録 */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>紛争・クレーム新規登録</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3">
            <div>
              <Label>案件名 *</Label>
              <Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>種別</Label>
                <Select value={form.dispute_type} onValueChange={(v) => setForm({ ...form, dispute_type: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {Object.entries(TYPE_LABELS).map(([v, l]) => (
                      <SelectItem key={v} value={v}>{l}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
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
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>優先度</Label>
                <Select value={form.priority} onValueChange={(v) => setForm({ ...form, priority: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="高">高</SelectItem>
                    <SelectItem value="中">中</SelectItem>
                    <SelectItem value="低">低</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>相手方</Label>
                <Input value={form.counterparty} onChange={(e) => setForm({ ...form, counterparty: e.target.value })} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>争議金額（円）</Label>
                <Input type="number" value={form.amount_claimed_jpy} onChange={(e) => setForm({ ...form, amount_claimed_jpy: e.target.value })} />
              </div>
              <div>
                <Label>引当額（円）</Label>
                <Input type="number" value={form.reserve_amount_jpy} onChange={(e) => setForm({ ...form, reserve_amount_jpy: e.target.value })} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>消滅時効日</Label>
                <Input type="date" value={form.statute_limitations_date} onChange={(e) => setForm({ ...form, statute_limitations_date: e.target.value })} />
              </div>
              <div>
                <Label>通知期限</Label>
                <Input type="date" value={form.notice_deadline} onChange={(e) => setForm({ ...form, notice_deadline: e.target.value })} />
              </div>
            </div>
            <div>
              <Label>概要</Label>
              <Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>キャンセル</Button>
            <Button onClick={() => void createDispute()} disabled={!form.title}>登録</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 詳細（タイムライン） */}
      <Dialog open={detail !== null} onOpenChange={(v) => !v && setDetail(null)}>
        <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{detail?.title ?? "案件詳細"}</DialogTitle>
          </DialogHeader>
          {detail && (
            <div className="space-y-4">
              <div className="flex flex-wrap gap-2">
                <Badge variant={STATUS_VARIANT[detail.status] ?? "outline"}>
                  {STATUS_LABELS[detail.status] ?? detail.status}
                </Badge>
                <Badge variant="outline">優先度: {detail.priority}</Badge>
                <Badge variant="outline">{detail.dispute_no}</Badge>
                {detail.legal_hold_id && <Badge variant="destructive">Legal Hold</Badge>}
              </div>
              <div className="text-sm text-muted-foreground">
                {detail.counterparty && <p>相手方: {detail.counterparty}</p>}
                {detail.statute_limitations_date && <p>消滅時効日: {detail.statute_limitations_date}</p>}
                {detail.notice_deadline && <p>通知期限: {detail.notice_deadline}</p>}
                {detail.amount_claimed_jpy !== null && detail.amount_claimed_jpy !== undefined && (
                  <p>争議金額: {formatCurrency(detail.amount_claimed_jpy)}</p>
                )}
              </div>
              {detail.description && <p className="text-sm">{detail.description}</p>}
              <div>
                <h3 className="mb-2 text-sm font-semibold">タイムライン</h3>
                {detail.timeline.length === 0 ? (
                  <p className="text-sm text-muted-foreground">記録なし</p>
                ) : (
                  <ol className="space-y-2 border-l pl-4">
                    {detail.timeline.map((ev) => (
                      <li key={String(ev.id)} className="relative text-sm">
                        <span className="absolute -left-[21px] top-1.5 h-2 w-2 rounded-full bg-primary" />
                        <p className="font-medium">{ev.event_type}</p>
                        <p className="text-xs text-muted-foreground">
                          {new Date(ev.occurred_at).toLocaleString("ja-JP")}
                        </p>
                        {ev.description && <p className="mt-0.5">{ev.description}</p>}
                      </li>
                    ))}
                  </ol>
                )}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
