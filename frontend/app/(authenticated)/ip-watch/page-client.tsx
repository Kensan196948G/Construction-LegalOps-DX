"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BellRing,
  Building2,
  Plus,
  RefreshCw,
  Search,
  UserRound,
} from "lucide-react";

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
import { ipWatchEventsApi, ipWatchTargetsApi, ipDashboardApi } from "@/lib/api";
import type { IpDashboard, IpWatchEvent, IpWatchTarget } from "@/lib/api/schemas";
import { AiDisclaimerBanner } from "@/components/layout/ai-disclaimer-banner";

const EVENT_TYPE_LABELS: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  new_application: { label: "新規出願", variant: "secondary" },
  status_change: { label: "ステータス変化", variant: "default" },
  new_progress: { label: "新規手続", variant: "outline" },
  registration: { label: "登録", variant: "default" },
  publication: { label: "公開", variant: "secondary" },
};

interface MockTarget {
  id: string;
  name: string;
  applicant_code?: string;
  status: string;
  asset_count: number;
}

const MOCK_TARGETS: MockTarget[] = [
  { id: "1", name: "さくら土木(株)", applicant_code: "000000002", status: "active", asset_count: 2 },
  { id: "2", name: "(株)つばさ組", status: "active", asset_count: 0 },
];

function toMockTarget(t: MockTarget): IpWatchTarget {
  return {
    id: t.id,
    name: t.name,
    applicant_code: t.applicant_code,
    status: t.status as IpWatchTarget["status"],
    ip_types: ["patent"],
    asset_count: t.asset_count,
    unread_event_count: 0,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
}

export default function IpWatchPage() {
  const [targets, setTargets] = useState<IpWatchTarget[]>(() => MOCK_TARGETS.map(toMockTarget));
  const [events, setEvents] = useState<IpWatchEvent[]>([]);
  const [dashboard, setDashboard] = useState<IpDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [search, setSearch] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState({
    name: "",
    applicant_code: "",
    ip_types: "patent",
    notes: "",
  });
  const [busyId, setBusyId] = useState<string | number | null>(null);
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [targetsRes, eventsRes, dash] = await Promise.all([
        ipWatchTargetsApi.list({ page: 1, size: 100 }),
        ipWatchEventsApi.list({ page: 1, size: 50 }),
        ipDashboardApi.get(),
      ]);
      setTargets(targetsRes.items);
      setEvents(eventsRes.items);
      setDashboard(dash);
      setOffline(false);
    } catch {
      setTargets(MOCK_TARGETS.map(toMockTarget));
      setOffline(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const filtered = useMemo(
    () => targets.filter((t) => !search || t.name.includes(search)),
    [targets, search]
  );

  const createTarget = async () => {
    if (!form.name.trim()) return;
    try {
      const created = await ipWatchTargetsApi.create({
        name: form.name.trim(),
        applicant_code: form.applicant_code.trim() || undefined,
        ip_types: [form.ip_types as IpWatchTarget["ip_types"][number]],
        status: "active",
        notes: form.notes || undefined,
      });
      setTargets((prev) => [created, ...prev]);
      setCreateOpen(false);
      setForm({ name: "", applicant_code: "", ip_types: "patent", notes: "" });
      setMessage("ウォッチ対象を登録しました");
      setTimeout(() => setMessage(""), 5000);
    } catch {
      setOffline(true);
    }
  };

  const syncTarget = async (target: IpWatchTarget) => {
    setBusyId(target.id);
    try {
      const result = await ipWatchTargetsApi.sync(target.id);
      await load();
      setMessage(result.message);
      setTimeout(() => setMessage(""), 5000);
    } catch {
      setOffline(true);
    } finally {
      setBusyId(null);
    }
  };

  const markRead = async (event: IpWatchEvent) => {
    try {
      await ipWatchEventsApi.markRead(event.id);
      setEvents((prev) => prev.map((e) => (e.id === event.id ? { ...e, is_read: true } : e)));
    } catch {
      // 既読化失敗は無視（再読込で復元される）
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-foreground">競合出願ウォッチ</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            競合企業の出願・審査経過の変化を検知し、タイムリーに把握します
          </p>
        </div>
        <div className="flex items-center gap-2">
          {dashboard && (
            <Badge variant="outline">JPO API: {dashboard.api_configured ? "live 接続" : "デモモード"}</Badge>
          )}
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="mr-2 h-4 w-4" /> ウォッチ対象登録
          </Button>
        </div>
      </header>

      <AiDisclaimerBanner variant="inline" />

      {offline && (
        <Badge variant="outline" className="border-amber-400 bg-amber-50 text-amber-800 dark:bg-amber-950">
          オフライン表示（モックデータ）
        </Badge>
      )}
      {message && (
        <Badge variant="outline" className="border-emerald-400 bg-emerald-50 text-emerald-800 dark:bg-emerald-950">
          {message}
        </Badge>
      )}

      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardContent className="flex items-center gap-3 pt-4">
            <Building2 className="h-8 w-8 text-primary" />
            <div>
              <p className="text-2xl font-bold">{loading ? "—" : dashboard?.total_watch_targets ?? targets.length}</p>
              <p className="text-sm text-muted-foreground">ウォッチ対象</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 pt-4">
            <BellRing className="h-8 w-8 text-primary" />
            <div>
              <p className="text-2xl font-bold">{loading ? "—" : dashboard?.unread_events ?? 0}</p>
              <p className="text-sm text-muted-foreground">未読イベント</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 pt-4">
            <UserRound className="h-8 w-8 text-primary" />
            <div>
              <p className="text-2xl font-bold">{loading ? "—" : dashboard?.active_watch_targets ?? 0}</p>
              <p className="text-sm text-muted-foreground">稼働中対象</p>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">ウォッチ対象</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                className="pl-8"
                placeholder="企業名で検索"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>企業名</TableHead>
                  <TableHead>申請人コード</TableHead>
                  <TableHead>対象出願</TableHead>
                  <TableHead>状態</TableHead>
                  <TableHead className="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((t) => (
                  <TableRow key={t.id}>
                    <TableCell className="font-medium">{t.name}</TableCell>
                    <TableCell className="font-mono text-xs">{t.applicant_code ?? "未取得"}</TableCell>
                    <TableCell>{t.asset_count} 件</TableCell>
                    <TableCell>
                      <Badge variant={t.status === "active" ? "default" : "outline"}>
                        {t.status === "active" ? "監視中" : "一時停止"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => void syncTarget(t)}
                        disabled={busyId === t.id}
                      >
                        <RefreshCw className={`mr-1 h-3 w-3 ${busyId === t.id ? "animate-spin" : ""}`} />
                        同期
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
                {filtered.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={5} className="py-6 text-center text-muted-foreground">
                      ウォッチ対象がありません
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">検知イベント</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {events.length === 0 && (
              <p className="py-6 text-center text-sm text-muted-foreground">
                イベントがありません。ウォッチ対象を「同期」して出願の変化を検知してください
              </p>
            )}
            {events.map((e) => {
              const meta = EVENT_TYPE_LABELS[e.event_type] ?? {
                label: e.event_type,
                variant: "outline" as const,
              };
              return (
                <div
                  key={e.id}
                  className={`rounded-md border p-3 ${e.is_read ? "opacity-60" : ""}`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <Badge variant={meta.variant}>{meta.label}</Badge>
                      <span className="font-mono text-xs text-muted-foreground">
                        {e.application_number ?? ""}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground">
                        {new Date(e.detected_at).toLocaleString("ja-JP")}
                      </span>
                      {!e.is_read && (
                        <Button variant="ghost" size="sm" onClick={() => void markRead(e)}>
                          既読
                        </Button>
                      )}
                    </div>
                  </div>
                  <p className="mt-1 text-sm">{e.description ?? ""}</p>
                </div>
              );
            })}
          </CardContent>
        </Card>
      </div>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>ウォッチ対象の登録</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="name">企業名</Label>
              <Input
                id="name"
                placeholder="例: さくら土木(株)"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="applicant_code">申請人コード（任意）</Label>
              <Input
                id="applicant_code"
                placeholder="JPO API から取得したコード"
                value={form.applicant_code}
                onChange={(e) => setForm({ ...form, applicant_code: e.target.value })}
              />
            </div>
            <div>
              <Label>対象区分</Label>
              <Select
                value={form.ip_types}
                onValueChange={(v) => setForm({ ...form, ip_types: v })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="区分" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="patent">特許</SelectItem>
                  <SelectItem value="design">意匠</SelectItem>
                  <SelectItem value="trademark">商標</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="notes">メモ（任意）</Label>
              <Input
                id="notes"
                placeholder="監視の目的など"
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              キャンセル
            </Button>
            <Button onClick={() => void createTarget()}>登録</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
