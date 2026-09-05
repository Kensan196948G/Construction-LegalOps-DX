"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CalendarClock,
  CheckCircle2,
  Loader2,
  Plus,
  RefreshCw,
  XCircle,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import { contractsApi, obligationsApi } from "@/lib/api";
import type { Contract, Obligation, RenewalCheck } from "@/lib/api/schemas";

const TYPE_LABELS: Record<string, string> = {
  report: "報告",
  notice: "通知",
  submit: "提出",
  insurance: "保険",
  renewal: "更新",
  condition: "条件成就",
  closing: "終了処理",
  other: "その他",
};

const STATUS_LABELS: Record<string, string> = {
  open: "未着手",
  in_progress: "進行中",
  completed: "完了",
  waived: "放棄",
};

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  open: "outline",
  in_progress: "secondary",
  completed: "default",
  waived: "secondary",
};

const BUCKET_LABELS: Record<string, string> = {
  all: "すべての期限",
  overdue: "期限切れ",
  within_30: "30日以内",
  within_60: "60日以内",
  future: "将来",
};

const RENEWAL_STATE_LABELS: Record<string, string> = {
  notice_overdue: "通知期限超過",
  upcoming: "通知期限が近い",
  ok: "期限内",
  expired: "契約満了",
};

interface ObligationsPageProps {
  /** 契約詳細などから遷移した際に絞り込む契約 ID */
  initialContractId?: string | null;
}

export default function ObligationsPage({ initialContractId = null }: ObligationsPageProps) {
  const [rows, setRows] = useState<Obligation[]>([]);
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [renewals, setRenewals] = useState<RenewalCheck[]>([]);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [bucket, setBucket] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const [contractFilter, setContractFilter] = useState(initialContractId ?? "all");
  const [form, setForm] = useState({
    contract_id: initialContractId ?? "",
    obligation_type: "report",
    title: "",
    description: "",
    due_date: "",
    assignee_id: "",
  });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [obligationResult, contractResult, renewalResult] = await Promise.all([
        obligationsApi.list({ page: 1, size: 200 }),
        contractsApi.list({ page: 1, page_size: 200 }),
        obligationsApi.renewalCheck({}),
      ]);
      setRows(obligationResult.items);
      setContracts(contractResult.items);
      setRenewals(renewalResult);
      setOffline(false);
    } catch {
      setRows([]);
      setContracts([]);
      setRenewals([]);
      setOffline(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const contractTitle = useMemo(() => {
    const map = new Map(contracts.map((c) => [String(c.id), c.title]));
    return (contractId: number | string) =>
      map.get(String(contractId)) ?? `契約 ID ${contractId}`;
  }, [contracts]);

  const bucketOf = useCallback((obligation: Obligation): string => {
    if (obligation.status !== "open" && obligation.status !== "in_progress") {
      return "";
    }
    if (!obligation.due_date) return "future";
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const due = new Date(`${obligation.due_date}T00:00:00+09:00`);
    const diffDays = Math.round((due.getTime() - today.getTime()) / 86_400_000);
    if (diffDays < 0) return "overdue";
    if (diffDays <= 30) return "within_30";
    if (diffDays <= 60) return "within_60";
    return "future";
  }, []);

  const filtered = useMemo(
    () =>
      rows.filter((r) => {
        if (contractFilter !== "all" && String(r.contract_id) !== contractFilter) {
          return false;
        }
        if (typeFilter !== "all" && r.obligation_type !== typeFilter) return false;
        if (bucket !== "all" && bucketOf(r) !== bucket) return false;
        return true;
      }),
    [rows, typeFilter, bucket, contractFilter, bucketOf]
  );

  const counts = useMemo(() => {
    const c: Record<string, number> = { all: rows.length };
    for (const b of ["overdue", "within_30", "within_60", "future"]) {
      c[b] = rows.filter((r) => bucketOf(r) === b).length;
    }
    return c;
  }, [rows, bucketOf]);

  const createObligation = async () => {
    if (!form.contract_id || !form.title.trim() || creating) return;
    setCreating(true);
    setActionError(null);
    try {
      const created = await obligationsApi.createForContract(form.contract_id, {
        obligation_type: form.obligation_type,
        title: form.title.trim(),
        description: form.description || null,
        due_date: form.due_date || null,
        assignee_id: form.assignee_id || null,
      });
      setRows((prev) => [...prev, created]);
      setCreateOpen(false);
      setForm({
        contract_id: "",
        obligation_type: "report",
        title: "",
        description: "",
        due_date: "",
        assignee_id: "",
      });
    } catch (err) {
      setActionError(
        err instanceof Error ? `登録に失敗しました: ${err.message}` : "登録に失敗しました。"
      );
    } finally {
      setCreating(false);
    }
  };

  const runAction = async (obligation: Obligation, action: "complete" | "waive") => {
    setActionError(null);
    try {
      const updated =
        action === "complete"
          ? await obligationsApi.complete(obligation.id)
          : await obligationsApi.waive(obligation.id);
      setRows((prev) =>
        prev.map((r) => (String(r.id) === String(obligation.id) ? updated : r))
      );
    } catch (err) {
      setActionError(
        err instanceof Error
          ? `${action === "complete" ? "完了" : "放棄"}処理に失敗しました: ${err.message}`
          : "処理に失敗しました。"
      );
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">契約義務</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            報告・通知・提出・保険・更新などの契約義務を、期限カレンダーで管理します
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)} className="gap-2">
          <Plus className="h-4 w-4" aria-hidden="true" />
          義務を登録
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

      {/* 期限バケット統計 */}
      <div className="grid grid-cols-4 gap-4">
        {(["overdue", "within_30", "within_60", "future"] as const).map((key) => (
          <Card
            key={key}
            className={
              key === "overdue" && counts[key] > 0
                ? "border-red-300 bg-red-50 dark:border-red-800 dark:bg-red-950/30"
                : ""
            }
          >
            <CardContent className="flex items-center gap-3 pt-4">
              <CalendarClock
                className={`h-8 w-8 ${
                  key === "overdue" && counts[key] > 0
                    ? "text-destructive"
                    : "text-muted-foreground"
                }`}
                aria-hidden="true"
              />
              <div>
                <p className="text-2xl font-bold">{counts[key]}</p>
                <p className="text-sm text-muted-foreground">{BUCKET_LABELS[key]}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-2 border-b px-6 py-4">
          <p className="text-sm font-semibold">義務一覧（未完了を期限順に判定）</p>
          <div className="flex flex-wrap items-center gap-2">
            <Select value={contractFilter} onValueChange={setContractFilter}>
              <SelectTrigger className="w-48" aria-label="契約で絞り込み">
                <SelectValue placeholder="契約" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">すべての契約</SelectItem>
                {contracts.map((c) => (
                  <SelectItem key={String(c.id)} value={String(c.id)}>
                    {c.title}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={bucket} onValueChange={setBucket}>
              <SelectTrigger className="w-40" aria-label="期限で絞り込み">
                <SelectValue placeholder="期限" />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(BUCKET_LABELS).map(([value, label]) => (
                  <SelectItem key={value} value={value}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={typeFilter} onValueChange={setTypeFilter}>
              <SelectTrigger className="w-36" aria-label="種別で絞り込み">
                <SelectValue placeholder="種別" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">すべての種別</SelectItem>
                {Object.entries(TYPE_LABELS).map(([value, label]) => (
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
              <TableHead className="w-24">種別</TableHead>
              <TableHead>義務</TableHead>
              <TableHead>契約</TableHead>
              <TableHead className="w-28">期限</TableHead>
              <TableHead className="w-20">状態</TableHead>
              <TableHead className="w-40">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={6} className="py-10 text-center text-sm text-muted-foreground">
                  <Loader2 className="mx-auto h-6 w-6 animate-spin" aria-hidden="true" />
                  読み込み中…
                </TableCell>
              </TableRow>
            ) : filtered.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="py-10 text-center text-sm text-muted-foreground">
                  該当する義務がありません。「義務を登録」から追加してください。
                </TableCell>
              </TableRow>
            ) : (
              filtered.map((obligation) => {
                const isOpen = obligation.status === "open" || obligation.status === "in_progress";
                const isOverdue =
                  isOpen && obligation.due_date && bucketOf(obligation) === "overdue";
                return (
                  <TableRow key={String(obligation.id)} className={isOverdue ? "bg-red-50/50 dark:bg-red-950/20" : ""}>
                    <TableCell>
                      <Badge variant="outline">
                        {TYPE_LABELS[obligation.obligation_type] ?? obligation.obligation_type}
                      </Badge>
                    </TableCell>
                    <TableCell className="max-w-[220px]">
                      <p className="truncate text-sm font-medium">{obligation.title}</p>
                      {obligation.description && (
                        <p className="line-clamp-1 text-xs text-muted-foreground">
                          {obligation.description}
                        </p>
                      )}
                    </TableCell>
                    <TableCell className="max-w-[180px]">
                      <p className="truncate text-sm">{contractTitle(obligation.contract_id)}</p>
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-sm">
                      {obligation.due_date ?? "—"}
                      {obligation.due_date && isOpen && (
                        <span className="ml-1 text-xs text-muted-foreground">
                          （{BUCKET_LABELS[bucketOf(obligation)]}）
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="whitespace-nowrap">
                      <Badge variant={STATUS_VARIANT[obligation.status] ?? "outline"}>
                        {STATUS_LABELS[obligation.status] ?? obligation.status}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        {isOpen && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => void runAction(obligation, "complete")}
                          >
                            <CheckCircle2 className="mr-1 h-3 w-3" aria-hidden="true" />
                            完了
                          </Button>
                        )}
                        {isOpen && (
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-muted-foreground"
                            onClick={() => void runAction(obligation, "waive")}
                          >
                            <XCircle className="mr-1 h-3 w-3" aria-hidden="true" />
                            放棄
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </Card>

      {/* 自動更新・解約通知期限チェック */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <RefreshCw className="h-4 w-4 text-primary" aria-hidden="true" />
            自動更新・解約通知期限チェック
          </CardTitle>
        </CardHeader>
        <CardContent>
          {renewals.length === 0 ? (
            <p className="py-4 text-center text-sm text-muted-foreground">
              自動更新付き契約がありません。
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>契約</TableHead>
                  <TableHead className="w-28">満了日</TableHead>
                  <TableHead className="w-28">通知期限</TableHead>
                  <TableHead className="w-24">残日数</TableHead>
                  <TableHead className="w-28">判定</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {renewals.map((row) => (
                  <TableRow key={String(row.contract_id)}>
                    <TableCell>
                      <p className="text-sm font-medium">{row.title}</p>
                      <p className="text-xs text-muted-foreground">{row.contract_no}</p>
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-sm">{row.end_date ?? "—"}</TableCell>
                    <TableCell className="whitespace-nowrap text-sm">
                      {row.notice_deadline ?? "—"}
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-sm">
                      {row.days_left !== null && row.days_left !== undefined
                        ? `${row.days_left} 日`
                        : "—"}
                    </TableCell>
                    <TableCell className="whitespace-nowrap">
                      <Badge
                        variant={
                          row.state === "notice_overdue"
                            ? "destructive"
                            : row.state === "upcoming"
                              ? "secondary"
                              : "outline"
                        }
                      >
                        {RENEWAL_STATE_LABELS[row.state] ?? row.state}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* 登録ダイアログ */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>契約義務を登録</DialogTitle>
            <DialogDescription>
              対象契約と義務の種別・期限を指定します。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="ob-contract">対象契約（必須）</Label>
              <Select
                value={form.contract_id}
                onValueChange={(v) => setForm((f) => ({ ...f, contract_id: v }))}
              >
                <SelectTrigger id="ob-contract" aria-label="対象契約">
                  <SelectValue placeholder="契約を選択" />
                </SelectTrigger>
                <SelectContent>
                  {contracts.map((c) => (
                    <SelectItem key={String(c.id)} value={String(c.id)}>
                      {c.title}（{c.contract_no ?? `ID ${c.id}`}）
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="ob-type">種別</Label>
              <Select
                value={form.obligation_type}
                onValueChange={(v) => setForm((f) => ({ ...f, obligation_type: v }))}
              >
                <SelectTrigger id="ob-type" aria-label="種別">
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
              <Label htmlFor="ob-title">義務名（必須）</Label>
              <Input
                id="ob-title"
                value={form.title}
                onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                placeholder="例: 工事経歴書の提出"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="ob-due">期限</Label>
              <Input
                id="ob-due"
                type="date"
                value={form.due_date}
                onChange={(e) => setForm((f) => ({ ...f, due_date: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="ob-desc">説明（任意）</Label>
              <Textarea
                id="ob-desc"
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                rows={2}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              キャンセル
            </Button>
            <Button
              onClick={() => void createObligation()}
              disabled={!form.contract_id || !form.title.trim() || creating}
            >
              {creating && <Loader2 className="mr-1 h-4 w-4 animate-spin" aria-hidden="true" />}
              登録
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
