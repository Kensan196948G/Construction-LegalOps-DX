"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  History,
  Loader2,
  Plus,
  RefreshCw,
  Scale,
  Unlink,
} from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
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
import { Alert, AlertDescription } from "@/components/ui/alert";
import { mattersApi, usersApi } from "@/lib/api";
import type { Matter, MatterContract, MatterEvent, User } from "@/lib/api/schemas";

const TYPE_LABELS: Record<string, string> = {
  contract: "契約",
  dispute: "紛争",
  compliance: "コンプライアンス",
  labor: "労務",
  regulatory: "規制対応",
  other: "その他",
};

const STATUS_LABELS: Record<string, string> = {
  open: "未着手",
  in_progress: "対応中",
  waiting: "待機中",
  on_hold: "保留",
  closed: "クローズ",
};

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  open: "outline",
  in_progress: "default",
  waiting: "secondary",
  on_hold: "secondary",
  closed: "destructive",
};

const PRIORITY_LABELS: Record<string, string> = {
  low: "低",
  medium: "中",
  high: "高",
  critical: "重大",
};

const PRIORITY_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  low: "outline",
  medium: "secondary",
  high: "default",
  critical: "destructive",
};

const EVENT_LABELS: Record<string, string> = {
  created: "作成",
  assigned: "担当アサイン",
  status_changed: "状態変更",
  contract_linked: "契約リンク",
  contract_unlinked: "契約リンク解除",
  legal_hold_linked: "Legal Hold 連動",
  legal_hold_unlinked: "Legal Hold 解除",
  note: "メモ",
};

function formatDateTime(value: string): string {
  try {
    return new Date(value).toLocaleString("ja-JP", { dateStyle: "medium", timeStyle: "short" });
  } catch {
    return value;
  }
}

export default function MattersPage() {
  const [rows, setRows] = useState<Matter[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [statusFilter, setStatusFilter] = useState("all");
  const [actionError, setActionError] = useState<string | null>(null);

  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    title: "",
    matter_type: "contract",
    priority: "medium",
    description: "",
    assignee_id: "",
  });

  // 詳細
  const [detail, setDetail] = useState<Matter | null>(null);
  const [detailContracts, setDetailContracts] = useState<MatterContract[]>([]);
  const [detailEvents, setDetailEvents] = useState<MatterEvent[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const [noteText, setNoteText] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const matterResult = await mattersApi.list({ page: 1, size: 100 });
      setRows(matterResult.items);
      setOffline(false);
    } catch {
      setRows([]);
      setOffline(true);
    } finally {
      setLoading(false);
    }
    // 担当者名表示用（admin/auditor 以外は 403 → 空のまま ID 表示にフォールバック）
    try {
      const userResult = await usersApi.list({ page: 1, page_size: 200 });
      setUsers(userResult.items);
    } catch {
      setUsers([]);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const userName = useMemo(() => {
    const map = new Map(users.map((u) => [String(u.id), u.display_name ?? u.email ?? "不明"]));
    return (id: number | string | null | undefined) =>
      id === null || id === undefined ? "未アサイン" : (map.get(String(id)) ?? `ユーザー ${id}`);
  }, [users]);

  const filtered = useMemo(
    () =>
      statusFilter === "all" ? rows : rows.filter((m) => m.status === statusFilter),
    [rows, statusFilter]
  );

  const openDetail = async (matter: Matter) => {
    setDetail(matter);
    setDetailLoading(true);
    setNoteText("");
    setDetailContracts([]);
    setDetailEvents([]);
    try {
      const [contracts, events] = await Promise.all([
        mattersApi.contracts(matter.id),
        mattersApi.events(matter.id),
      ]);
      setDetailContracts(contracts);
      setDetailEvents(events);
    } catch {
      /* 個別取得失敗時は空のまま表示 */
    } finally {
      setDetailLoading(false);
    }
  };

  const refreshDetail = useCallback(async (matterId: number | string) => {
    try {
      const [updated, contracts, events] = await Promise.all([
        mattersApi.get(matterId),
        mattersApi.contracts(matterId),
        mattersApi.events(matterId),
      ]);
      setDetail(updated);
      setRows((prev) =>
        prev.map((m) => (String(m.id) === String(matterId) ? updated : m))
      );
      setDetailContracts(contracts);
      setDetailEvents(events);
    } catch {
      /* ignore */
    }
  }, []);

  const createMatter = async () => {
    if (!form.title.trim() || creating) return;
    setCreating(true);
    setActionError(null);
    try {
      const created = await mattersApi.create({
        title: form.title.trim(),
        matter_type: form.matter_type,
        priority: form.priority,
        description: form.description || null,
        assignee_id: form.assignee_id || null,
      });
      setRows((prev) => [created, ...prev]);
      setCreateOpen(false);
      setForm({
        title: "",
        matter_type: "contract",
        priority: "medium",
        description: "",
        assignee_id: "",
      });
    } catch (err) {
      setActionError(
        err instanceof Error ? `作成に失敗しました: ${err.message}` : "作成に失敗しました。"
      );
    } finally {
      setCreating(false);
    }
  };

  const changeStatus = async (matter: Matter, status: string) => {
    setActionError(null);
    try {
      await mattersApi.setStatus(matter.id, { status });
      await refreshDetail(matter.id);
    } catch (err) {
      setActionError(
        err instanceof Error ? `状態変更に失敗しました: ${err.message}` : "状態変更に失敗しました。"
      );
    }
  };

  const assign = async (matter: Matter, assigneeId: string) => {
    setActionError(null);
    try {
      await mattersApi.assign(matter.id, { assignee_id: assigneeId || null });
      await refreshDetail(matter.id);
    } catch (err) {
      setActionError(
        err instanceof Error ? `アサインに失敗しました: ${err.message}` : "アサインに失敗しました。"
      );
    }
  };

  const addNote = async (matterId: number | string) => {
    if (!noteText.trim()) return;
    setActionError(null);
    try {
      await mattersApi.addNote(matterId, { note: noteText.trim() });
      setNoteText("");
      await refreshDetail(matterId);
    } catch (err) {
      setActionError(
        err instanceof Error ? `メモ追記に失敗しました: ${err.message}` : "メモ追記に失敗しました。"
      );
    }
  };

  const unlinkContract = async (matter: Matter, contractId: number | string) => {
    setActionError(null);
    try {
      await mattersApi.unlinkContract(matter.id, contractId);
      await refreshDetail(matter.id);
    } catch (err) {
      setActionError(
        err instanceof Error ? `契約リンク解除に失敗しました: ${err.message}` : "リンク解除に失敗しました。"
      );
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">法務案件</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            契約を越えた法務案件（Matter）を台帳・タイムライン・契約リンクで管理します
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)} className="gap-2">
          <Plus className="h-4 w-4" aria-hidden="true" />
          Matter 作成
        </Button>
      </header>

      {offline && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" aria-hidden="true" />
          <AlertDescription>
            データを取得できませんでした。バックエンド API の起動を確認してください。
          </AlertDescription>
        </Alert>
      )}
      {actionError && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" aria-hidden="true" />
          <AlertDescription>{actionError}</AlertDescription>
        </Alert>
      )}

      <Card>
        <div className="flex items-center justify-between border-b px-6 py-4">
          <p className="text-sm font-semibold">Matter 台帳</p>
          <div className="flex items-center gap-2">
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-40" aria-label="状態で絞り込み">
                <SelectValue placeholder="状態" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">すべての状態</SelectItem>
                {Object.entries(STATUS_LABELS).map(([value, label]) => (
                  <SelectItem key={value} value={value}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button variant="outline" size="icon" onClick={() => void load()} aria-label="再読み込み">
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-36">Matter No</TableHead>
              <TableHead>案件名</TableHead>
              <TableHead className="w-20">種別</TableHead>
              <TableHead className="w-20">優先度</TableHead>
              <TableHead className="w-24">状態</TableHead>
              <TableHead className="w-32">担当</TableHead>
              <TableHead className="w-24"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={7} className="py-10 text-center text-sm text-muted-foreground">
                  <Loader2 className="mx-auto h-6 w-6 animate-spin" aria-hidden="true" />
                  読み込み中…
                </TableCell>
              </TableRow>
            ) : filtered.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="py-10 text-center text-sm text-muted-foreground">
                  案件がありません。「Matter 作成」から登録してください。
                </TableCell>
              </TableRow>
            ) : (
              filtered.map((matter) => (
                <TableRow key={String(matter.id)}>
                  <TableCell className="whitespace-nowrap font-mono text-sm">
                    {matter.matter_no}
                  </TableCell>
                  <TableCell className="max-w-[240px]">
                    <p className="truncate text-sm font-medium">{matter.title}</p>
                    {matter.source_type && (
                      <p className="text-xs text-muted-foreground">
                        昇格元: {matter.source_type}
                        {matter.source_id ? ` #${matter.source_id}` : ""}
                      </p>
                    )}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">
                      {TYPE_LABELS[matter.matter_type] ?? matter.matter_type}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant={PRIORITY_VARIANT[matter.priority] ?? "outline"}>
                      {PRIORITY_LABELS[matter.priority] ?? matter.priority}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant={STATUS_VARIANT[matter.status] ?? "outline"}>
                      {STATUS_LABELS[matter.status] ?? matter.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {userName(matter.assignee_id)}
                  </TableCell>
                  <TableCell>
                    <Button variant="ghost" size="sm" onClick={() => void openDetail(matter)}>
                      詳細
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Card>

      {/* 作成ダイアログ */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Matter 作成</DialogTitle>
            <DialogDescription>
              法務案件を登録します。ID は MT-YYYY-NNNNNN 形式で自動採番されます。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="mt-title">案件名（必須）</Label>
              <Input
                id="mt-title"
                value={form.title}
                onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                placeholder="例: ◯◯工事のクレーム対応"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="mt-type">種別</Label>
                <Select
                  value={form.matter_type}
                  onValueChange={(v) => setForm((f) => ({ ...f, matter_type: v }))}
                >
                  <SelectTrigger id="mt-type" aria-label="種別">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(TYPE_LABELS).map(([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="mt-priority">優先度</Label>
                <Select
                  value={form.priority}
                  onValueChange={(v) => setForm((f) => ({ ...f, priority: v }))}
                >
                  <SelectTrigger id="mt-priority" aria-label="優先度">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="low">低</SelectItem>
                    <SelectItem value="medium">中</SelectItem>
                    <SelectItem value="high">高</SelectItem>
                    <SelectItem value="critical">重大</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="mt-assignee">担当法務（任意）</Label>
              <Select
                value={form.assignee_id}
                onValueChange={(v) => setForm((f) => ({ ...f, assignee_id: v }))}
              >
                <SelectTrigger id="mt-assignee" aria-label="担当法務">
                  <SelectValue placeholder="選択（未指定で可）" />
                </SelectTrigger>
                <SelectContent>
                  {users.map((u) => (
                    <SelectItem key={String(u.id)} value={String(u.id)}>
                      {u.display_name ?? u.email ?? `ID ${u.id}`}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="mt-desc">概要（任意）</Label>
              <Textarea
                id="mt-desc"
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              キャンセル
            </Button>
            <Button
              onClick={() => void createMatter()}
              disabled={!form.title.trim() || creating}
            >
              {creating && <Loader2 className="mr-1 h-4 w-4 animate-spin" aria-hidden="true" />}
              作成
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 詳細ダイアログ */}
      <Dialog
        open={detail !== null}
        onOpenChange={(open) => {
          if (!open) setDetail(null);
        }}
      >
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-3xl">
          {detail && (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <Scale className="h-5 w-5 text-primary" aria-hidden="true" />
                  {detail.title}
                </DialogTitle>
                <DialogDescription>
                  {detail.matter_no} /{" "}
                  {TYPE_LABELS[detail.matter_type] ?? detail.matter_type} /{" "}
                  {STATUS_LABELS[detail.status] ?? detail.status}
                  {detail.legal_hold_case_id && " / 🔒 Legal Hold 連動中"}
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-5">
                {detail.description && (
                  <p className="text-sm text-muted-foreground">{detail.description}</p>
                )}

                {/* 状態遷移 */}
                <div className="flex flex-wrap items-center gap-2 rounded-md border p-3">
                  <span className="text-xs font-semibold text-muted-foreground">状態:</span>
                  {Object.entries(STATUS_LABELS).map(([value, label]) => (
                    <Button
                      key={value}
                      size="sm"
                      variant={detail.status === value ? "default" : "outline"}
                      onClick={() => void changeStatus(detail, value)}
                      disabled={detail.status === value}
                    >
                      {label}
                    </Button>
                  ))}
                </div>

                {/* 担当アサイン */}
                <div className="flex items-center gap-3 rounded-md border p-3">
                  <span className="text-xs font-semibold text-muted-foreground">担当:</span>
                  <Select
                    value={detail.assignee_id ? String(detail.assignee_id) : ""}
                    onValueChange={(v) => void assign(detail, v)}
                  >
                    <SelectTrigger className="w-56" aria-label="担当法務">
                      <SelectValue placeholder="担当を選択" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="">未アサイン</SelectItem>
                      {users.map((u) => (
                        <SelectItem key={String(u.id)} value={String(u.id)}>
                          {u.display_name ?? u.email ?? `ID ${u.id}`}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* 関係契約 */}
                <div>
                  <p className="mb-2 text-sm font-semibold">関係契約</p>
                  {detailContracts.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      リンクされた契約はありません（契約詳細画面からリンクできます）。
                    </p>
                  ) : (
                    <ul className="space-y-1">
                      {detailContracts.map((c) => (
                        <li key={String(c.contract_id)} className="flex items-center gap-2">
                          <Link
                            href={`/contracts/${c.contract_id}`}
                            className="text-sm text-primary hover:underline"
                          >
                            {c.title}
                          </Link>
                          <span className="text-xs text-muted-foreground">{c.contract_no}</span>
                          <Button
                            size="icon"
                            variant="ghost"
                            className="ml-auto h-6 w-6"
                            onClick={() => void unlinkContract(detail, c.contract_id)}
                            aria-label={`契約 ${c.title} のリンクを解除`}
                          >
                            <Unlink className="h-3.5 w-3.5" />
                          </Button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                {/* タイムライン */}
                <div>
                  <p className="mb-2 flex items-center gap-1 text-sm font-semibold">
                    <History className="h-4 w-4" aria-hidden="true" />
                    タイムライン（追記専用）
                  </p>
                  {detailLoading ? (
                    <div className="flex items-center justify-center py-6">
                      <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
                    </div>
                  ) : (
                    <ol className="space-y-2">
                      {detailEvents.length === 0 && (
                        <li className="text-sm text-muted-foreground">イベントがありません。</li>
                      )}
                      {detailEvents.map((event) => (
                        <li key={String(event.id)} className="rounded-md border p-3 text-sm">
                          <div className="flex items-center gap-2">
                            <Badge variant="outline">
                              {EVENT_LABELS[event.event_type] ?? event.event_type}
                            </Badge>
                            <span className="ml-auto text-xs text-muted-foreground">
                              {formatDateTime(event.created_at)}
                            </span>
                          </div>
                          {event.note && (
                            <p className="mt-1 text-muted-foreground">{event.note}</p>
                          )}
                        </li>
                      ))}
                    </ol>
                  )}
                  <div className="mt-3 flex gap-2">
                    <Textarea
                      value={noteText}
                      onChange={(e) => setNoteText(e.target.value)}
                      placeholder="進捗メモを追記…"
                      rows={2}
                      className="flex-1"
                    />
                    <Button
                      variant="outline"
                      onClick={() => void addNote(detail.id)}
                      disabled={!noteText.trim()}
                    >
                      追記
                    </Button>
                  </div>
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
