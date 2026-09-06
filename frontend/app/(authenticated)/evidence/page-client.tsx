"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Download,
  FileSearch,
  Loader2,
  Lock,
  Mail,
  Plus,
  RefreshCw,
  ShieldCheck,
  ShieldOff,
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { evidenceApi } from "@/lib/api";
import type {
  Evidence,
  EvidenceCustodyEvent,
  EvidenceTimelineItem,
} from "@/lib/api/schemas";

const SOURCE_TYPE_LABELS: Record<string, string> = {
  upload: "アップロード",
  email: "メール",
  photo: "写真",
  scan: "スキャン",
  other: "その他",
};

const RELEVANCE_LABELS: Record<string, string> = {
  unclassified: "未分類",
  relevant: "関連あり",
  not_relevant: "関連なし",
  privileged: "秘匿特権の疑い",
};

const RELEVANCE_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  unclassified: "outline",
  relevant: "default",
  not_relevant: "secondary",
  privileged: "destructive",
};

const CUSTODY_ACTION_LABELS: Record<string, string> = {
  collected: "収集",
  received: "受領",
  transferred: "移管",
  analyzed: "分析",
  copied: "複製",
  returned: "返却",
  destroyed: "廃棄",
  hold_applied: "Legal Hold 紐付け",
  hold_released: "Legal Hold 解除",
};

async function sha256Hex(text: string): Promise<string> {
  const data = new TextEncoder().encode(text);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

export default function EvidencePage() {
  const [rows, setRows] = useState<Evidence[]>([]);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [relevanceFilter, setRelevanceFilter] = useState("all");

  // 詳細
  const [detail, setDetail] = useState<Evidence | null>(null);
  const [custody, setCustody] = useState<EvidenceCustodyEvent[]>([]);
  const [timeline, setTimeline] = useState<EvidenceTimelineItem[]>([]);
  const [duplicates, setDuplicates] = useState<Evidence[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);

  // 登録ダイアログ
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    title: "",
    description: "",
    source_type: "upload",
    content_text: "",
    checksum_sha256: "",
    collected_by_name: "",
  });

  // メール取込ダイアログ
  const [emailOpen, setEmailOpen] = useState(false);
  const [emailSaving, setEmailSaving] = useState(false);
  const [emailForm, setEmailForm] = useState({ raw_eml: "", collected_by_name: "" });

  // Chain of Custody 追記ダイアログ
  const [custodyOpen, setCustodyOpen] = useState(false);
  const [custodySaving, setCustodySaving] = useState(false);
  const [custodyForm, setCustodyForm] = useState({
    action: "transferred",
    to_custodian: "",
    notes: "",
  });

  // Legal Hold 解除申請ダイアログ
  const [holdReleaseOpen, setHoldReleaseOpen] = useState(false);
  const [holdReleaseSaving, setHoldReleaseSaving] = useState(false);
  const [holdReleaseReason, setHoldReleaseReason] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await evidenceApi.list({ page: 1, size: 100 });
      setRows(result.items);
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

  const filtered = useMemo(
    () =>
      relevanceFilter === "all" ? rows : rows.filter((r) => r.relevance === relevanceFilter),
    [rows, relevanceFilter],
  );

  const openDetail = useCallback(async (evidence: Evidence) => {
    setDetail(evidence);
    setDetailLoading(true);
    try {
      const [custodyRows, timelineRows, dupRows] = await Promise.all([
        evidenceApi.custody(evidence.id),
        evidenceApi.timeline(evidence.id),
        evidenceApi.duplicates(evidence.id),
      ]);
      setCustody(custodyRows);
      setTimeline(timelineRows);
      setDuplicates(dupRows);
    } catch {
      setCustody([]);
      setTimeline([]);
      setDuplicates([]);
    } finally {
      setDetailLoading(false);
    }
  }, []);

  const refreshDetail = useCallback(async (id: number | string) => {
    try {
      const [updated, custodyRows, timelineRows] = await Promise.all([
        evidenceApi.get(id),
        evidenceApi.custody(id),
        evidenceApi.timeline(id),
      ]);
      setDetail(updated);
      setCustody(custodyRows);
      setTimeline(timelineRows);
      setRows((prev) => prev.map((r) => (String(r.id) === String(id) ? updated : r)));
    } catch {
      /* ignore */
    }
  }, []);

  const createEvidence = async () => {
    if (!form.title.trim() || creating) return;
    setCreating(true);
    setActionError(null);
    try {
      const useText = form.content_text.trim().length > 0;
      await evidenceApi.create({
        title: form.title.trim(),
        description: form.description || null,
        source_type: form.source_type,
        collected_by_name: form.collected_by_name || null,
        ...(useText
          ? {
              file_content_base64: btoa(unescape(encodeURIComponent(form.content_text))),
              mime_type: "text/plain",
            }
          : { checksum_sha256: form.checksum_sha256.trim().toLowerCase() }),
      });
      setCreateOpen(false);
      setForm({
        title: "",
        description: "",
        source_type: "upload",
        content_text: "",
        checksum_sha256: "",
        collected_by_name: "",
      });
      await load();
    } catch (err) {
      setActionError(
        err instanceof Error ? `登録に失敗しました: ${err.message}` : "登録に失敗しました。",
      );
    } finally {
      setCreating(false);
    }
  };

  const computeHashFromText = async () => {
    if (!form.content_text.trim()) return;
    const hash = await sha256Hex(form.content_text);
    setForm((f) => ({ ...f, checksum_sha256: hash }));
  };

  const ingestEmail = async () => {
    if (!emailForm.raw_eml.trim() || emailSaving) return;
    setEmailSaving(true);
    setActionError(null);
    try {
      await evidenceApi.emailIngest({
        raw_eml: emailForm.raw_eml,
        collected_by_name: emailForm.collected_by_name || null,
      });
      setEmailOpen(false);
      setEmailForm({ raw_eml: "", collected_by_name: "" });
      await load();
    } catch (err) {
      setActionError(
        err instanceof Error ? `メール取込に失敗しました: ${err.message}` : "取込に失敗しました。",
      );
    } finally {
      setEmailSaving(false);
    }
  };

  const addCustodyEvent = async () => {
    if (!detail || custodySaving) return;
    setCustodySaving(true);
    setActionError(null);
    try {
      await evidenceApi.addCustodyEvent(detail.id, {
        action: custodyForm.action,
        to_custodian: custodyForm.to_custodian || null,
        notes: custodyForm.notes || null,
      });
      setCustodyOpen(false);
      setCustodyForm({ action: "transferred", to_custodian: "", notes: "" });
      await refreshDetail(detail.id);
    } catch (err) {
      setActionError(
        err instanceof Error ? `記録に失敗しました: ${err.message}` : "記録に失敗しました。",
      );
    } finally {
      setCustodySaving(false);
    }
  };

  const requestHoldRelease = async () => {
    if (!detail || !detail.legal_hold_id || !holdReleaseReason.trim() || holdReleaseSaving) return;
    setHoldReleaseSaving(true);
    setActionError(null);
    try {
      await evidenceApi.requestHoldRelease({
        legal_hold_id: detail.legal_hold_id,
        reason: holdReleaseReason.trim(),
        evidence_id: detail.id,
      });
      setHoldReleaseOpen(false);
      setHoldReleaseReason("");
      await refreshDetail(detail.id);
    } catch (err) {
      setActionError(
        err instanceof Error ? `解除申請に失敗しました: ${err.message}` : "解除申請に失敗しました。",
      );
    } finally {
      setHoldReleaseSaving(false);
    }
  };

  const exportEvidence = async () => {
    if (!detail) return;
    setActionError(null);
    try {
      const bundle = await evidenceApi.export(detail.id);
      const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${detail.evidence_code}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      // Firefox 等でダウンロード開始前に URL が破棄されるのを避けるため遅延する。
      setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch (err) {
      setActionError(
        err instanceof Error ? `Export に失敗しました: ${err.message}` : "Export に失敗しました。",
      );
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">証拠管理</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            証拠保管庫・SHA-256 ハッシュ・Chain of Custody・タイムライン・Legal Hold
            解除承認を管理します
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setEmailOpen(true)} className="gap-2">
            <Mail className="h-4 w-4" aria-hidden="true" />
            メール証拠取込
          </Button>
          <Button onClick={() => setCreateOpen(true)} className="gap-2">
            <Plus className="h-4 w-4" aria-hidden="true" />
            証拠を登録
          </Button>
        </div>
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
          <p className="text-sm font-semibold">証拠保管庫（Evidence Repository）</p>
          <div className="flex items-center gap-2">
            <Select value={relevanceFilter} onValueChange={setRelevanceFilter}>
              <SelectTrigger className="w-40" aria-label="関連性で絞り込み">
                <SelectValue placeholder="関連性" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">すべての関連性</SelectItem>
                {Object.entries(RELEVANCE_LABELS).map(([value, label]) => (
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
              <TableHead className="w-40">証拠 ID</TableHead>
              <TableHead>タイトル</TableHead>
              <TableHead className="w-24">入手経路</TableHead>
              <TableHead className="w-28">関連性</TableHead>
              <TableHead className="w-20">重複</TableHead>
              <TableHead className="w-20">Hold</TableHead>
              <TableHead className="w-20">操作</TableHead>
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
                  証拠が登録されていません。「証拠を登録」から作成してください。
                </TableCell>
              </TableRow>
            ) : (
              filtered.map((ev) => (
                <TableRow key={String(ev.id)}>
                  <TableCell className="whitespace-nowrap font-mono text-sm">
                    {ev.evidence_code}
                  </TableCell>
                  <TableCell className="max-w-[280px]">
                    <p className="truncate text-sm font-medium">{ev.title}</p>
                  </TableCell>
                  <TableCell className="text-sm">
                    {SOURCE_TYPE_LABELS[ev.source_type] ?? ev.source_type}
                  </TableCell>
                  <TableCell>
                    <Badge variant={RELEVANCE_VARIANT[ev.relevance] ?? "outline"}>
                      {RELEVANCE_LABELS[ev.relevance] ?? ev.relevance}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {ev.is_duplicate ? (
                      <Badge variant="destructive">重複</Badge>
                    ) : (
                      <span className="text-xs text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell>
                    {ev.is_under_hold ? (
                      <Lock className="h-4 w-4 text-destructive" aria-label="Legal Hold 中" />
                    ) : (
                      <span className="text-xs text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <Button variant="ghost" size="sm" onClick={() => void openDetail(ev)}>
                      詳細
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Card>

      {/* 証拠登録ダイアログ */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>証拠を登録</DialogTitle>
            <DialogDescription>
              Evidence ID は EVD-YYYY-NNNNNN 形式で自動採番され、SHA-256 ハッシュが記録されます。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="ev-title">タイトル（必須）</Label>
              <Input
                id="ev-title"
                value={form.title}
                onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                placeholder="例: 現場写真（支払遅延の証拠）"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="ev-desc">説明（任意）</Label>
              <Textarea
                id="ev-desc"
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                rows={2}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="ev-source">入手経路</Label>
                <Select
                  value={form.source_type}
                  onValueChange={(v) => setForm((f) => ({ ...f, source_type: v }))}
                >
                  <SelectTrigger id="ev-source" aria-label="入手経路">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(SOURCE_TYPE_LABELS).map(([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="ev-collector">収集者（任意）</Label>
                <Input
                  id="ev-collector"
                  value={form.collected_by_name}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, collected_by_name: e.target.value }))
                  }
                />
              </div>
            </div>
            <div className="space-y-2 rounded-md border p-3">
              <Label htmlFor="ev-content">証拠内容（テキストで保持する場合・任意）</Label>
              <Textarea
                id="ev-content"
                value={form.content_text}
                onChange={(e) => setForm((f) => ({ ...f, content_text: e.target.value }))}
                rows={3}
                placeholder="現場報告メモ等をそのまま貼り付けると、内容から SHA-256 を自動計算します。"
              />
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => void computeHashFromText()}
                  disabled={!form.content_text.trim()}
                >
                  内容から SHA-256 を計算
                </Button>
                <span className="text-xs text-muted-foreground">
                  または下欄へ既存の SHA-256 を直接入力
                </span>
              </div>
              <Label htmlFor="ev-checksum">SHA-256 ハッシュ（64 桁 16 進数）</Label>
              <Input
                id="ev-checksum"
                value={form.checksum_sha256}
                onChange={(e) => setForm((f) => ({ ...f, checksum_sha256: e.target.value }))}
                placeholder="64 桁の 16 進数"
                className="font-mono text-xs"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              キャンセル
            </Button>
            <Button
              onClick={() => void createEvidence()}
              disabled={
                !form.title.trim() ||
                creating ||
                (!form.content_text.trim() && form.checksum_sha256.trim().length !== 64)
              }
            >
              {creating && <Loader2 className="mr-1 h-4 w-4 animate-spin" aria-hidden="true" />}
              登録
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* メール証拠取込ダイアログ */}
      <Dialog open={emailOpen} onOpenChange={setEmailOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>メール証拠取込</DialogTitle>
            <DialogDescription>
              RFC 822（.eml）形式のメール本文をそのまま貼り付けてください。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="ev-eml">.eml 本文（必須）</Label>
              <Textarea
                id="ev-eml"
                value={emailForm.raw_eml}
                onChange={(e) => setEmailForm((f) => ({ ...f, raw_eml: e.target.value }))}
                rows={8}
                className="font-mono text-xs"
                placeholder={"From: ...\nTo: ...\nSubject: ...\nDate: ...\n\n本文"}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="ev-eml-collector">収集者（任意）</Label>
              <Input
                id="ev-eml-collector"
                value={emailForm.collected_by_name}
                onChange={(e) =>
                  setEmailForm((f) => ({ ...f, collected_by_name: e.target.value }))
                }
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEmailOpen(false)}>
              キャンセル
            </Button>
            <Button
              onClick={() => void ingestEmail()}
              disabled={!emailForm.raw_eml.trim() || emailSaving}
            >
              {emailSaving && <Loader2 className="mr-1 h-4 w-4 animate-spin" aria-hidden="true" />}
              取込
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 証拠詳細ダイアログ */}
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
                  <FileSearch className="h-5 w-5 text-primary" aria-hidden="true" />
                  {detail.title}
                </DialogTitle>
                <DialogDescription className="flex flex-wrap items-center gap-2">
                  <span className="font-mono">{detail.evidence_code}</span>
                  <Badge variant={RELEVANCE_VARIANT[detail.relevance] ?? "outline"}>
                    {RELEVANCE_LABELS[detail.relevance] ?? detail.relevance}
                  </Badge>
                  {detail.is_duplicate && <Badge variant="destructive">重複</Badge>}
                  {detail.is_under_hold && (
                    <Badge variant="destructive" className="gap-1">
                      <Lock className="h-3 w-3" aria-hidden="true" />
                      Legal Hold 中
                    </Badge>
                  )}
                </DialogDescription>
              </DialogHeader>

              <div className="flex flex-wrap gap-2">
                <Button size="sm" variant="outline" onClick={() => setCustodyOpen(true)}>
                  受け渡し記録を追加
                </Button>
                <Button size="sm" variant="outline" onClick={() => void exportEvidence()} className="gap-1">
                  <Download className="h-3 w-3" aria-hidden="true" />
                  Export
                </Button>
                {detail.is_under_hold && detail.legal_hold_id && (
                  <Button size="sm" variant="outline" onClick={() => setHoldReleaseOpen(true)} className="gap-1">
                    <ShieldOff className="h-3 w-3" aria-hidden="true" />
                    Legal Hold 解除申請
                  </Button>
                )}
              </div>

              <div className="rounded-md border p-3 text-xs">
                <p className="mb-1 font-semibold text-muted-foreground">SHA-256</p>
                <p className="break-all font-mono">{detail.sha256_hash}</p>
              </div>

              {detailLoading ? (
                <div className="flex items-center justify-center py-6">
                  <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
                </div>
              ) : (
                <Tabs defaultValue="custody">
                  <TabsList>
                    <TabsTrigger value="custody">Chain of Custody</TabsTrigger>
                    <TabsTrigger value="timeline">タイムライン</TabsTrigger>
                    <TabsTrigger value="duplicates">重複候補</TabsTrigger>
                  </TabsList>
                  <TabsContent value="custody" className="space-y-2">
                    {custody.length === 0 ? (
                      <p className="text-sm text-muted-foreground">記録がありません。</p>
                    ) : (
                      <ul className="space-y-1">
                        {custody.map((c) => (
                          <li key={String(c.id)} className="rounded-md border px-3 py-2 text-sm">
                            <div className="flex items-center justify-between">
                              <span className="font-medium">
                                {CUSTODY_ACTION_LABELS[c.action] ?? c.action}
                              </span>
                              <span className="text-xs text-muted-foreground">
                                {new Date(c.occurred_at).toLocaleString("ja-JP")}
                              </span>
                            </div>
                            {(c.to_custodian || c.notes) && (
                              <p className="mt-1 text-xs text-muted-foreground">
                                {c.to_custodian && <>移管先: {c.to_custodian} </>}
                                {c.notes}
                              </p>
                            )}
                            <p className="mt-1 truncate font-mono text-[10px] text-muted-foreground">
                              hash: {c.hash_chain}
                            </p>
                          </li>
                        ))}
                      </ul>
                    )}
                  </TabsContent>
                  <TabsContent value="timeline" className="space-y-2">
                    {timeline.length === 0 ? (
                      <p className="text-sm text-muted-foreground">記録がありません。</p>
                    ) : (
                      <ul className="space-y-1">
                        {timeline.map((item, idx) => (
                          <li
                            key={`${item.action}-${idx}`}
                            className="flex items-center justify-between rounded-md border px-3 py-2 text-sm"
                          >
                            <span className="flex items-center gap-2">
                              <Badge variant={item.type === "custody" ? "default" : "outline"}>
                                {item.type === "custody" ? "受け渡し" : "監査ログ"}
                              </Badge>
                              {CUSTODY_ACTION_LABELS[item.action] ?? item.action}
                            </span>
                            <span className="text-xs text-muted-foreground">
                              {new Date(item.occurred_at).toLocaleString("ja-JP")}
                            </span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </TabsContent>
                  <TabsContent value="duplicates" className="space-y-2">
                    {duplicates.length === 0 ? (
                      <p className="flex items-center gap-1 text-sm text-muted-foreground">
                        <ShieldCheck className="h-4 w-4" aria-hidden="true" />
                        同一ハッシュの重複は検出されていません。
                      </p>
                    ) : (
                      <ul className="space-y-1">
                        {duplicates.map((d) => (
                          <li key={String(d.id)} className="rounded-md border px-3 py-2 text-sm">
                            <span className="font-mono">{d.evidence_code}</span> — {d.title}
                          </li>
                        ))}
                      </ul>
                    )}
                  </TabsContent>
                </Tabs>
              )}
            </>
          )}
        </DialogContent>
      </Dialog>

      {/* Chain of Custody 追記ダイアログ */}
      <Dialog open={custodyOpen} onOpenChange={setCustodyOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>受け渡し記録を追加</DialogTitle>
            <DialogDescription>誰が・いつ・どう扱ったかを追記します（追記専用）。</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="cust-action">アクション</Label>
              <Select
                value={custodyForm.action}
                onValueChange={(v) => setCustodyForm((f) => ({ ...f, action: v }))}
              >
                <SelectTrigger id="cust-action" aria-label="アクション">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(CUSTODY_ACTION_LABELS).map(([value, label]) => (
                    <SelectItem key={value} value={value}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="cust-to">移管先（任意）</Label>
              <Input
                id="cust-to"
                value={custodyForm.to_custodian}
                onChange={(e) => setCustodyForm((f) => ({ ...f, to_custodian: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="cust-notes">備考（任意）</Label>
              <Textarea
                id="cust-notes"
                value={custodyForm.notes}
                onChange={(e) => setCustodyForm((f) => ({ ...f, notes: e.target.value }))}
                rows={2}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCustodyOpen(false)}>
              キャンセル
            </Button>
            <Button onClick={() => void addCustodyEvent()} disabled={custodySaving}>
              {custodySaving && <Loader2 className="mr-1 h-4 w-4 animate-spin" aria-hidden="true" />}
              記録
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Legal Hold 解除申請ダイアログ */}
      <Dialog open={holdReleaseOpen} onOpenChange={setHoldReleaseOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Legal Hold 解除申請</DialogTitle>
            <DialogDescription>
              申請者本人は決裁できません（職務分掌）。承認権限を持つ別の担当者が決裁します。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="hold-reason">解除理由（必須）</Label>
            <Textarea
              id="hold-reason"
              value={holdReleaseReason}
              onChange={(e) => setHoldReleaseReason(e.target.value)}
              rows={3}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setHoldReleaseOpen(false)}>
              キャンセル
            </Button>
            <Button
              onClick={() => void requestHoldRelease()}
              disabled={!holdReleaseReason.trim() || holdReleaseSaving}
            >
              {holdReleaseSaving && (
                <Loader2 className="mr-1 h-4 w-4 animate-spin" aria-hidden="true" />
              )}
              申請
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
