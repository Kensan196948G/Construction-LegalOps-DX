"use client";

import * as React from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  History,
  Loader2,
  RefreshCw,
  Send,
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
import { contractsApi, negotiationsApi } from "@/lib/api";
import type {
  Clause,
  ClauseNegotiationState,
  Contract,
  NegotiationEvent,
} from "@/lib/api/schemas";

const NEG_STATUS_LABELS: Record<string, string> = {
  accepted: "合意",
  rejected: "拒否",
  negotiating: "交渉中",
};

const OWNER_LABELS: Record<string, string> = {
  法務: "法務",
  工事: "工事",
  営業: "営業",
  購買: "購買",
  その他: "その他",
};

const ACTION_LABELS: Record<string, string> = {
  redline: "Redline 修正提案",
  demand: "要求",
  concession: "譲歩",
  comment: "コメント",
};

function formatDateTime(value: string): string {
  try {
    return new Date(value).toLocaleString("ja-JP", { dateStyle: "medium", timeStyle: "short" });
  } catch {
    return value;
  }
}

interface NegotiationsPageProps {
  /** 契約詳細などから遷移した際に自動選択する契約 ID */
  initialContractId?: string | null;
}

export default function NegotiationsPage({ initialContractId = null }: NegotiationsPageProps) {
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [selectedContractId, setSelectedContractId] = useState(initialContractId ?? "");
  const [clauses, setClauses] = useState<Clause[]>([]);
  // 条項別の交渉状態（ステータス/オーナー更新 API の結果を保持）
  const [clauseStates, setClauseStates] = useState<Record<string, ClauseNegotiationState>>({});
  const [events, setEvents] = useState<NegotiationEvent[]>([]);
  const [, setLoading] = useState(true); // 契約一覧の初回読込中フラグ
  const [detailLoading, setDetailLoading] = useState(false);
  const [offline, setOffline] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  // 交渉イベント記録
  const [eventOpen, setEventOpen] = useState(false);
  const [eventForm, setEventForm] = useState({
    action: "comment",
    clause_id: "",
    round_no: "",
    note: "",
    proposed_text: "",
  });
  const [sending, setSending] = useState(false);

  const loadContracts = useCallback(async () => {
    setLoading(true);
    try {
      const result = await contractsApi.list({ page: 1, page_size: 200 });
      setContracts(result.items);
      setOffline(false);
      return result.items;
    } catch {
      setContracts([]);
      setOffline(true);
      return [] as Contract[];
    } finally {
      setLoading(false);
    }
  }, []);

  const loadDetail = useCallback(
    async (contractId: string) => {
      setDetailLoading(true);
      setClauseStates({});
      try {
        const [clauseResult, eventResult] = await Promise.all([
          contractsApi.clauses(contractId),
          negotiationsApi.list(contractId, { page: 1, size: 100 }),
        ]);
        setClauses(clauseResult);
        setEvents(eventResult.items);
      } catch {
        setClauses([]);
        setEvents([]);
      } finally {
        setDetailLoading(false);
      }
    },
    []
  );

  // 初回ロード: 契約一覧取得後に initialContractId があれば自動選択
  const initialAppliedRef = React.useRef(false);
  useEffect(() => {
    void (async () => {
      const loaded = await loadContracts();
      if (initialContractId && !initialAppliedRef.current) {
        initialAppliedRef.current = true;
        const exists = loaded.some((c) => String(c.id) === initialContractId);
        if (exists) {
          setSelectedContractId(initialContractId);
          await loadDetail(initialContractId);
        }
      }
    })();
  }, [loadContracts, initialContractId, loadDetail]);

  const selectedContract = useMemo(
    () => contracts.find((c) => String(c.id) === selectedContractId) ?? null,
    [contracts, selectedContractId]
  );

  const selectContract = (value: string) => {
    setSelectedContractId(value);
    if (value) void loadDetail(value);
  };

  const refreshEvents = useCallback(async () => {
    if (!selectedContractId) return;
    try {
      const eventResult = await negotiationsApi.list(selectedContractId, { page: 1, size: 100 });
      setEvents(eventResult.items);
    } catch {
      /* ignore */
    }
  }, [selectedContractId]);

  const applyClauseState = useCallback(
    (state: ClauseNegotiationState) => {
      setClauseStates((prev) => ({ ...prev, [String(state.id)]: state }));
    },
    []
  );

  const setClauseStatus = async (clauseId: number | string, status: string) => {
    if (!selectedContractId) return;
    setActionError(null);
    try {
      const updated = await negotiationsApi.setClauseStatus(selectedContractId, clauseId, {
        status,
      });
      applyClauseState(updated);
      await refreshEvents();
    } catch (err) {
      setActionError(
        err instanceof Error ? `条項ステータス更新に失敗しました: ${err.message}` : "更新に失敗しました。"
      );
    }
  };

  const setClauseOwner = async (clauseId: number | string, owner: string) => {
    if (!selectedContractId) return;
    setActionError(null);
    try {
      const updated = await negotiationsApi.setClauseOwner(selectedContractId, clauseId, {
        owner,
      });
      applyClauseState(updated);
      await refreshEvents();
    } catch (err) {
      setActionError(
        err instanceof Error ? `オーナー割当に失敗しました: ${err.message}` : "割当に失敗しました。"
      );
    }
  };

  const sendEvent = async () => {
    if (!selectedContractId || sending) return;
    setSending(true);
    setActionError(null);
    try {
      await negotiationsApi.add(selectedContractId, {
        action: eventForm.action,
        clause_id: eventForm.clause_id || null,
        round_no: eventForm.round_no ? Number(eventForm.round_no) : null,
        note: eventForm.note || null,
        proposed_text: eventForm.action === "redline" ? eventForm.proposed_text || null : null,
      });
      setEventOpen(false);
      setEventForm({
        action: "comment",
        clause_id: "",
        round_no: "",
        note: "",
        proposed_text: "",
      });
      await refreshEvents();
    } catch (err) {
      setActionError(
        err instanceof Error ? `記録に失敗しました: ${err.message}` : "記録に失敗しました。"
      );
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">契約交渉・Redline</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            条項単位の交渉ステータス・担当オーナー・Redline 修正案を管理します
          </p>
        </div>
        {selectedContract && (
          <Button
            onClick={() => {
              setActionError(null);
              setEventOpen(true);
            }}
            className="gap-2"
          >
            <Send className="h-4 w-4" aria-hidden="true" />
            交渉イベントを記録
          </Button>
        )}
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

      {/* 契約選択 */}
      <Card>
        <CardContent className="flex flex-wrap items-center gap-3 pt-6">
          <Label htmlFor="contract-select" className="whitespace-nowrap text-sm font-semibold">
            対象契約
          </Label>
          <Select value={selectedContractId} onValueChange={selectContract}>
            <SelectTrigger id="contract-select" className="min-w-[320px] flex-1" aria-label="対象契約">
              <SelectValue placeholder="契約を選択して交渉管理を開始" />
            </SelectTrigger>
            <SelectContent>
              {contracts.map((c) => (
                <SelectItem key={String(c.id)} value={String(c.id)}>
                  {c.title}（{c.contract_no ?? `ID ${c.id}`}）
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {selectedContractId && (
            <Button
              variant="outline"
              size="icon"
              onClick={() => void loadDetail(selectedContractId)}
              aria-label="再読み込み"
            >
              <RefreshCw className="h-4 w-4" />
            </Button>
          )}
        </CardContent>
      </Card>

      {!selectedContract ? (
        <Card>
          <CardContent className="py-14 text-center text-sm text-muted-foreground">
            交渉対象の契約を選択してください。
          </CardContent>
        </Card>
      ) : detailLoading ? (
        <Card>
          <CardContent className="flex items-center justify-center py-14">
            <Loader2 className="h-6 w-6 animate-spin" aria-hidden="true" />
          </CardContent>
        </Card>
      ) : (
        <>
          {/* 条項一覧 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">条項一覧（ステータス・オーナー）</CardTitle>
            </CardHeader>
            <CardContent>
              {clauses.length === 0 ? (
                <p className="py-6 text-center text-sm text-muted-foreground">
                  条項が抽出されていません。
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-16">No</TableHead>
                      <TableHead>条項</TableHead>
                      <TableHead className="w-32">ステータス</TableHead>
                      <TableHead className="w-36">オーナー</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {clauses.map((clause) => {
                      const state = clauseStates[String(clause.id)];
                      return (
                        <TableRow key={String(clause.id)}>
                          <TableCell className="text-sm text-muted-foreground">
                            {clause.seq}
                          </TableCell>
                          <TableCell className="max-w-[420px]">
                            <p className="text-sm font-medium">{clause.title ?? "（無題）"}</p>
                            <p className="line-clamp-2 text-xs text-muted-foreground">
                              {clause.text}
                            </p>
                            {state?.negotiated_text && (
                              <p className="mt-1 rounded bg-amber-50 p-1 text-xs text-amber-800 dark:bg-amber-950/30 dark:text-amber-200">
                                修正案: {state.negotiated_text}
                              </p>
                            )}
                          </TableCell>
                          <TableCell>
                            <Select
                              value={state?.negotiation_status ?? "unset"}
                              onValueChange={(v) => {
                                if (v !== "unset") void setClauseStatus(clause.id, v);
                              }}
                            >
                              <SelectTrigger
                                className="h-8 w-28"
                                aria-label={`条項 ${clause.seq} のステータス`}
                              >
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="unset">未設定</SelectItem>
                                {Object.entries(NEG_STATUS_LABELS).map(([value, label]) => (
                                  <SelectItem key={value} value={value}>
                                    {label}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </TableCell>
                          <TableCell>
                            <Select
                              value={state?.clause_owner ?? "unset"}
                              onValueChange={(v) => {
                                if (v !== "unset") void setClauseOwner(clause.id, v);
                              }}
                            >
                              <SelectTrigger
                                className="h-8 w-28"
                                aria-label={`条項 ${clause.seq} のオーナー`}
                              >
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="unset">未割当</SelectItem>
                                {Object.entries(OWNER_LABELS).map(([value, label]) => (
                                  <SelectItem key={value} value={value}>
                                    {label}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          {/* 交渉履歴 */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <History className="h-4 w-4 text-primary" aria-hidden="true" />
                交渉履歴タイムライン
              </CardTitle>
            </CardHeader>
            <CardContent>
              {events.length === 0 ? (
                <p className="py-6 text-center text-sm text-muted-foreground">
                  交渉イベントがありません。
                </p>
              ) : (
                <ol className="space-y-3">
                  {events.map((event) => (
                    <li key={String(event.id)} className="rounded-md border p-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="outline">
                          {ACTION_LABELS[event.action] ?? event.action}
                        </Badge>
                        {event.round_no && (
                          <Badge variant="secondary">ラウンド {event.round_no}</Badge>
                        )}
                        {event.clause_id && (
                          <Badge variant="outline">条項 #{event.clause_id}</Badge>
                        )}
                        <span className="ml-auto text-xs text-muted-foreground">
                          {formatDateTime(event.created_at)}
                        </span>
                      </div>
                      {event.note && (
                        <p className="mt-1 text-sm text-muted-foreground">{event.note}</p>
                      )}
                      {event.proposed_text && (
                        <pre className="mt-2 overflow-x-auto rounded bg-muted/40 p-2 text-xs">
                          {event.proposed_text}
                        </pre>
                      )}
                    </li>
                  ))}
                </ol>
              )}
            </CardContent>
          </Card>
        </>
      )}

      {/* 交渉イベント記録ダイアログ */}
      <Dialog open={eventOpen} onOpenChange={setEventOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>交渉イベントを記録</DialogTitle>
            <DialogDescription>
              {selectedContract?.title ?? ""} — 要求・譲歩・コメント・Redline 修正案を証跡として残します
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="neg-action">種別</Label>
              <Select
                value={eventForm.action}
                onValueChange={(v) => setEventForm((f) => ({ ...f, action: v }))}
              >
                <SelectTrigger id="neg-action" aria-label="種別">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(ACTION_LABELS).map(([value, label]) => (
                    <SelectItem key={value} value={value}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="neg-clause">対象条項（任意）</Label>
                <Select
                  value={eventForm.clause_id}
                  onValueChange={(v) => setEventForm((f) => ({ ...f, clause_id: v }))}
                >
                  <SelectTrigger id="neg-clause" aria-label="対象条項">
                    <SelectValue placeholder="条項を選択" />
                  </SelectTrigger>
                  <SelectContent>
                    {clauses.map((clause) => (
                      <SelectItem key={String(clause.id)} value={String(clause.id)}>
                        {clause.seq}: {clause.title ?? "（無題）"}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="neg-round">ラウンド（任意）</Label>
                <Input
                  id="neg-round"
                  type="number"
                  min={1}
                  value={eventForm.round_no}
                  onChange={(e) => setEventForm((f) => ({ ...f, round_no: e.target.value }))}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="neg-note">メモ（要求内容・背景等）</Label>
              <Textarea
                id="neg-note"
                value={eventForm.note}
                onChange={(e) => setEventForm((f) => ({ ...f, note: e.target.value }))}
                rows={3}
              />
            </div>
            {eventForm.action === "redline" && (
              <div className="space-y-2">
                <Label htmlFor="neg-text">修正提案テキスト（Redline）</Label>
                <Textarea
                  id="neg-text"
                  value={eventForm.proposed_text}
                  onChange={(e) => setEventForm((f) => ({ ...f, proposed_text: e.target.value }))}
                  rows={5}
                  placeholder="修正後の条項文面を記載"
                />
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEventOpen(false)}>
              キャンセル
            </Button>
            <Button onClick={() => void sendEvent()} disabled={sending}>
              {sending && <Loader2 className="mr-1 h-4 w-4 animate-spin" aria-hidden="true" />}
              記録
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
