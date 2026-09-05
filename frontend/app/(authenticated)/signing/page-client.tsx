"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Eye,
  History,
  Loader2,
  PenLine,
  Plus,
  RefreshCw,
  Send,
  ShieldCheck,
} from "lucide-react";

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
import { contractsApi, signingApi } from "@/lib/api";
import type { Contract, SigningEnvelope, SigningEvent } from "@/lib/api/schemas";

const STATUS_LABELS: Record<string, string> = {
  draft: "下書き",
  sent: "送信済",
  viewed: "閲覧済",
  signed: "署名済",
  completed: "締結完了",
  cancelled: "取消",
};

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  draft: "outline",
  sent: "secondary",
  viewed: "secondary",
  signed: "default",
  completed: "default",
  cancelled: "destructive",
};

const METHOD_LABELS: Record<string, string> = {
  electronic: "電磁的方法",
  paper: "書面",
};

const PROVIDER_LABELS: Record<string, string> = {
  demo: "デモ",
  manual: "手動",
  cloudsign: "CloudSign",
  docusign: "DocuSign",
};

const EVENT_LABELS: Record<string, string> = {
  created: "作成",
  sent: "送信",
  consent_received: "承諾受領",
  viewed: "閲覧",
  signed: "署名",
  completed: "締結完了",
  cancelled: "取消",
};

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString("ja-JP", { dateStyle: "medium", timeStyle: "short" });
  } catch {
    return value;
  }
}

interface SigningPageProps {
  /** 契約詳細などから遷移した際にプリセットされる対象契約 ID */
  initialContractId?: string | null;
}

export default function SigningPage({ initialContractId = null }: SigningPageProps) {
  const [envelopes, setEnvelopes] = useState<SigningEnvelope[]>([]);
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [statusFilter, setStatusFilter] = useState("all");
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  // 作成フォーム
  const [form, setForm] = useState({
    contract_id: initialContractId ?? "",
    method: "electronic",
    provider: "demo",
    counterparty_name: "",
    counterparty_email: "",
    note: "",
  });

  // 状態遷移モーダル（consent / sign / cancel）
  const [actionTarget, setActionTarget] = useState<{
    envelope: SigningEnvelope;
    kind: "consent" | "sign" | "cancel";
  } | null>(null);
  const [actionForm, setActionForm] = useState({
    name: "",
    email: "",
    note: "",
    reason: "",
  });
  const [runningAction, setRunningAction] = useState(false);

  // イベント履歴
  const [eventsFor, setEventsFor] = useState<SigningEnvelope | null>(null);
  const [events, setEvents] = useState<SigningEvent[]>([]);
  const [eventsLoading, setEventsLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [envelopeResult, contractResult] = await Promise.all([
        signingApi.list({ page: 1, size: 100 }),
        contractsApi.list({ page: 1, page_size: 200 }),
      ]);
      setEnvelopes(envelopeResult.items);
      setContracts(contractResult.items);
      setOffline(false);
    } catch {
      setEnvelopes([]);
      setContracts([]);
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
    return (envelope: SigningEnvelope) =>
      map.get(String(envelope.contract_id)) ?? `契約 ID ${envelope.contract_id}`;
  }, [contracts]);

  const filtered = useMemo(
    () =>
      statusFilter === "all"
        ? envelopes
        : envelopes.filter((e) => e.status === statusFilter),
    [envelopes, statusFilter]
  );

  const createEnvelope = async () => {
    if (!form.contract_id || creating) return;
    setCreating(true);
    setActionError(null);
    try {
      const created = await signingApi.create({
        contract_id: form.contract_id,
        method: form.method,
        provider: form.provider,
        counterparty_name: form.counterparty_name || null,
        counterparty_email: form.counterparty_email || null,
        note: form.note || null,
      });
      setEnvelopes((prev) => [created, ...prev]);
      setCreateOpen(false);
      setForm({
        contract_id: "",
        method: "electronic",
        provider: "demo",
        counterparty_name: "",
        counterparty_email: "",
        note: "",
      });
    } catch (err) {
      setActionError(
        err instanceof Error
          ? `作成に失敗しました: ${err.message}`
          : "作成に失敗しました。"
      );
    } finally {
      setCreating(false);
    }
  };

  /** 状態遷移（ボディ不要のもの: send / view / complete） */
  const runSimpleTransition = async (envelope: SigningEnvelope, action: "send" | "view") => {
    setActionError(null);
    try {
      const updated =
        action === "send"
          ? await signingApi.send(envelope.id)
          : await signingApi.view(envelope.id);
      setEnvelopes((prev) =>
        prev.map((e) => (String(e.id) === String(envelope.id) ? updated : e))
      );
    } catch (err) {
      setActionError(
        err instanceof Error
          ? `${action === "send" ? "送信" : "閲覧記録"}に失敗しました: ${err.message}`
          : "状態遷移に失敗しました。"
      );
    }
  };

  /** 状態遷移（フォーム入力が必要なもの: consent / sign / cancel） */
  const openActionDialog = (
    envelope: SigningEnvelope,
    kind: "consent" | "sign" | "cancel"
  ) => {
    setActionError(null);
    setActionForm({ name: "", email: "", note: "", reason: "" });
    setActionTarget({ envelope, kind });
  };

  const runAction = async () => {
    if (!actionTarget) return;
    const { envelope, kind } = actionTarget;
    setRunningAction(true);
    setActionError(null);
    try {
      let updated: SigningEnvelope;
      if (kind === "consent") {
        updated = await signingApi.consent(envelope.id, {
          consentor_name: actionForm.name || null,
          consentor_email: actionForm.email || null,
          note: actionForm.note || null,
        });
      } else if (kind === "sign") {
        updated = await signingApi.sign(envelope.id, {
          signer_name: actionForm.name || null,
          signer_email: actionForm.email || null,
        });
      } else {
        updated = await signingApi.cancel(envelope.id, {
          reason: actionForm.reason || null,
        });
      }
      setEnvelopes((prev) =>
        prev.map((e) => (String(e.id) === String(envelope.id) ? updated : e))
      );
      setActionTarget(null);
    } catch (err) {
      setActionError(
        err instanceof Error ? `処理に失敗しました: ${err.message}` : "処理に失敗しました。"
      );
    } finally {
      setRunningAction(false);
    }
  };

  const completeEnvelope = async (envelope: SigningEnvelope) => {
    setActionError(null);
    try {
      const updated = await signingApi.complete(envelope.id, {});
      setEnvelopes((prev) =>
        prev.map((e) => (String(e.id) === String(envelope.id) ? updated : e))
      );
    } catch (err) {
      setActionError(
        err instanceof Error ? `締結完了に失敗しました: ${err.message}` : "締結完了に失敗しました。"
      );
    }
  };

  const loadEvents = async (envelope: SigningEnvelope) => {
    setEventsFor(envelope);
    setEventsLoading(true);
    try {
      const result = await signingApi.events(envelope.id);
      setEvents(result);
    } catch {
      setEvents([]);
    } finally {
      setEventsLoading(false);
    }
  };

  const canSend = (s: string) => s === "draft";
  const canConsent = (s: string) => s === "draft" || s === "sent" || s === "viewed";
  const canSign = (s: string) => s === "sent" || s === "viewed";
  const canComplete = (s: string) => s === "signed";
  const canCancel = (s: string) => ["draft", "sent", "viewed"].includes(s);

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">電子契約・署名</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            エンベロープの作成・送付・承諾証跡・署名・締結をルールエンジンで管理します
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)} className="gap-2">
          <Plus className="h-4 w-4" aria-hidden="true" />
          エンベロープ作成
        </Button>
      </header>

      <Alert className="border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-700 dark:bg-amber-950/30 dark:text-amber-100">
        <ShieldCheck className="h-4 w-4" aria-hidden="true" />
        <AlertDescription>
          電磁的方法（electronic）による交付には、建設業法 19 条に基づく相手方の
          <strong>承諾証跡（consent）</strong>の記録が必要です。署名の前に承諾を記録してください。
        </AlertDescription>
      </Alert>

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
          <p className="text-sm font-semibold">エンベロープ一覧</p>
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
              <TableHead className="w-40">エンベロープ No</TableHead>
              <TableHead>契約</TableHead>
              <TableHead className="w-28">方法</TableHead>
              <TableHead className="w-24">状態</TableHead>
              <TableHead className="w-36">承諾証跡</TableHead>
              <TableHead className="w-32">署名日時</TableHead>
              <TableHead className="w-24"></TableHead>
              <TableHead className="w-64">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={8} className="py-10 text-center text-sm text-muted-foreground">
                  <Loader2 className="mx-auto h-6 w-6 animate-spin" aria-hidden="true" />
                  読み込み中…
                </TableCell>
              </TableRow>
            ) : filtered.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} className="py-10 text-center text-sm text-muted-foreground">
                  エンベロープがありません。「エンベロープ作成」から新規作成してください。
                </TableCell>
              </TableRow>
            ) : (
              filtered.map((envelope) => {
                const status = envelope.status ?? "";
                return (
                  <TableRow key={String(envelope.id)}>
                    <TableCell className="whitespace-nowrap font-mono text-sm">
                      {envelope.envelope_no}
                    </TableCell>
                    <TableCell className="max-w-[200px]">
                      <p className="truncate text-sm font-medium">
                        {contractTitle(envelope)}
                      </p>
                      {envelope.counterparty_name && (
                        <p className="text-xs text-muted-foreground">
                          {envelope.counterparty_name}
                        </p>
                      )}
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-sm">
                      {METHOD_LABELS[envelope.method ?? ""] ?? envelope.method}
                      <span className="block text-xs text-muted-foreground">
                        {PROVIDER_LABELS[envelope.provider ?? ""] ?? envelope.provider}
                      </span>
                    </TableCell>
                    <TableCell className="whitespace-nowrap">
                      <Badge variant={STATUS_VARIANT[status] ?? "outline"}>
                        {STATUS_LABELS[status] ?? status}
                      </Badge>
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-sm">
                      {envelope.consent_confirmed_at ? (
                        <span className="inline-flex items-center gap-1 text-green-700 dark:text-green-400">
                          <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
                          {envelope.consentor_name ?? "承諾済"}
                        </span>
                      ) : (
                        <span className="text-muted-foreground">未承諾</span>
                      )}
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-sm text-muted-foreground">
                      {formatDateTime(envelope.signed_at)}
                    </TableCell>
                    <TableCell>
                      <Button variant="ghost" size="sm" onClick={() => void loadEvents(envelope)}>
                        <History className="mr-1 h-3.5 w-3.5" aria-hidden="true" />
                        履歴
                      </Button>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {canSend(status) && (
                          <Button size="sm" onClick={() => void runSimpleTransition(envelope, "send")}>
                            <Send className="mr-1 h-3 w-3" aria-hidden="true" />
                            送信
                          </Button>
                        )}
                        {canConsent(status) && (
                          <Button size="sm" variant="outline" onClick={() => openActionDialog(envelope, "consent")}>
                            <ShieldCheck className="mr-1 h-3 w-3" aria-hidden="true" />
                            承諾記録
                          </Button>
                        )}
                        {status !== "viewed" && (status === "sent") && (
                          <Button size="sm" variant="outline" onClick={() => void runSimpleTransition(envelope, "view")}>
                            <Eye className="mr-1 h-3 w-3" aria-hidden="true" />
                            閲覧
                          </Button>
                        )}
                        {canSign(status) && (
                          <Button size="sm" onClick={() => openActionDialog(envelope, "sign")}>
                            <PenLine className="mr-1 h-3 w-3" aria-hidden="true" />
                            署名
                          </Button>
                        )}
                        {canComplete(status) && (
                          <Button size="sm" onClick={() => void completeEnvelope(envelope)}>
                            <CheckCircle2 className="mr-1 h-3 w-3" aria-hidden="true" />
                            締結完了
                          </Button>
                        )}
                        {canCancel(status) && (
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-destructive"
                            onClick={() => openActionDialog(envelope, "cancel")}
                          >
                            取消
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

      {/* 作成ダイアログ */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>エンベロープ作成</DialogTitle>
            <DialogDescription>
              対象契約を選び、署名方法とプロバイダを指定してください（draft で作成されます）。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="env-contract">対象契約（必須）</Label>
              <Select
                value={form.contract_id}
                onValueChange={(v) => setForm((f) => ({ ...f, contract_id: v }))}
              >
                <SelectTrigger id="env-contract" aria-label="対象契約">
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
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="env-method">署名方法</Label>
                <Select
                  value={form.method}
                  onValueChange={(v) => setForm((f) => ({ ...f, method: v }))}
                >
                  <SelectTrigger id="env-method" aria-label="署名方法">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="electronic">電磁的方法（承諾証跡必須）</SelectItem>
                    <SelectItem value="paper">書面</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="env-provider">プロバイダ</Label>
                <Select
                  value={form.provider}
                  onValueChange={(v) => setForm((f) => ({ ...f, provider: v }))}
                >
                  <SelectTrigger id="env-provider" aria-label="プロバイダ">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="demo">デモ（外部送信なし）</SelectItem>
                    <SelectItem value="manual">手動</SelectItem>
                    <SelectItem value="cloudsign">CloudSign</SelectItem>
                    <SelectItem value="docusign">DocuSign</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="env-cp-name">相手方名（任意）</Label>
              <Input
                id="env-cp-name"
                value={form.counterparty_name}
                onChange={(e) =>
                  setForm((f) => ({ ...f, counterparty_name: e.target.value }))
                }
                placeholder="例: 株式会社◯◯建設"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="env-cp-email">相手方メール（任意）</Label>
              <Input
                id="env-cp-email"
                type="email"
                value={form.counterparty_email}
                onChange={(e) =>
                  setForm((f) => ({ ...f, counterparty_email: e.target.value }))
                }
                placeholder="例: legal@example.com"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="env-note">メモ（任意）</Label>
              <Textarea
                id="env-note"
                value={form.note}
                onChange={(e) => setForm((f) => ({ ...f, note: e.target.value }))}
                rows={2}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              キャンセル
            </Button>
            <Button onClick={() => void createEnvelope()} disabled={!form.contract_id || creating}>
              {creating && <Loader2 className="mr-1 h-4 w-4 animate-spin" aria-hidden="true" />}
              作成（draft）
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 状態遷移ダイアログ（consent / sign / cancel） */}
      <Dialog
        open={actionTarget !== null}
        onOpenChange={(open) => {
          if (!open) setActionTarget(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {actionTarget?.kind === "consent" && "相手方の承諾証跡を記録"}
              {actionTarget?.kind === "sign" && "署名（相手方）を受領"}
              {actionTarget?.kind === "cancel" && "エンベロープを取消"}
            </DialogTitle>
            <DialogDescription>
              {actionTarget?.kind === "consent" &&
                "電磁的方法による交付の承諾を記録します（建設業法 19 条）。"}
              {actionTarget?.kind === "sign" && "署名者情報を記録して signed へ遷移します。"}
              {actionTarget?.kind === "cancel" && "取消理由を記録します（元に戻せません）。"}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            {actionTarget?.kind !== "cancel" && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="action-name">
                    {actionTarget?.kind === "consent" ? "承諾者名" : "署名者名"}
                  </Label>
                  <Input
                    id="action-name"
                    value={actionForm.name}
                    onChange={(e) => setActionForm((f) => ({ ...f, name: e.target.value }))}
                    placeholder="例: 山田 太郎"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="action-email">メール（任意）</Label>
                  <Input
                    id="action-email"
                    type="email"
                    value={actionForm.email}
                    onChange={(e) => setActionForm((f) => ({ ...f, email: e.target.value }))}
                  />
                </div>
              </>
            )}
            <div className="space-y-2">
              <Label htmlFor="action-note">
                {actionTarget?.kind === "cancel" ? "取消理由" : "取得経緯・メモ（証跡・任意）"}
              </Label>
              <Textarea
                id="action-note"
                value={
                  actionTarget?.kind === "cancel" ? actionForm.reason : actionForm.note
                }
                onChange={(e) =>
                  actionTarget?.kind === "cancel"
                    ? setActionForm((f) => ({ ...f, reason: e.target.value }))
                    : setActionForm((f) => ({ ...f, note: e.target.value }))
                }
                rows={2}
              />
            </div>
            {actionError && (
              <p className="text-sm text-destructive">{actionError}</p>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setActionTarget(null)}>
              キャンセル
            </Button>
            <Button onClick={() => void runAction()} disabled={runningAction}>
              {runningAction && <Loader2 className="mr-1 h-4 w-4 animate-spin" aria-hidden="true" />}
              実行
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* イベント履歴ダイアログ */}
      <Dialog
        open={eventsFor !== null}
        onOpenChange={(open) => {
          if (!open) setEventsFor(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>証跡イベント一覧</DialogTitle>
            <DialogDescription>
              {eventsFor?.envelope_no} — 追記専用・読み取りのみ
            </DialogDescription>
          </DialogHeader>
          {eventsLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin" aria-hidden="true" />
            </div>
          ) : events.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">イベントがありません。</p>
          ) : (
            <ol className="space-y-3">
              {events.map((event) => (
                <li key={String(event.id)} className="rounded-md border p-3">
                  <div className="flex items-center gap-2">
                    <Badge variant="outline">
                      {EVENT_LABELS[event.event_type] ?? event.event_type}
                    </Badge>
                    <span className="ml-auto text-xs text-muted-foreground">
                      {formatDateTime(event.created_at)}
                    </span>
                  </div>
                  {event.payload && Object.keys(event.payload).length > 0 && (
                    <pre className="mt-2 overflow-x-auto rounded bg-muted/40 p-2 text-xs">
                      {JSON.stringify(event.payload, null, 2)}
                    </pre>
                  )}
                </li>
              ))}
            </ol>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
