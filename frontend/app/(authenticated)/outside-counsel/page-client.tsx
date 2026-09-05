"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Building2,
  CheckCircle2,
  Loader2,
  Plus,
  RefreshCw,
  Scale,
  UserRound,
  XCircle,
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { engagementsApi, lawFirmsApi } from "@/lib/api";
import type { CounselLawyer, Engagement, LawFirm } from "@/lib/api/schemas";

const ENG_STATUS_LABELS: Record<string, string> = {
  open: "依頼中",
  answered: "回答済",
  confirmed: "確認済",
  cancelled: "取消",
};

const ENG_STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  open: "outline",
  answered: "secondary",
  confirmed: "default",
  cancelled: "destructive",
};

function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleDateString("ja-JP", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
  } catch {
    return value;
  }
}

export default function OutsideCounselPage() {
  const [tab, setTab] = useState("engagements");

  // 依頼
  const [engagements, setEngagements] = useState<Engagement[]>([]);
  const [firms, setFirms] = useState<LawFirm[]>([]);
  const [lawyers, setLawyers] = useState<CounselLawyer[]>([]);
  const [lawyerCache, setLawyerCache] = useState<Record<string, CounselLawyer[]>>({});
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("all");

  // 依頼起票
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    firm_id: "",
    lawyer_id: "",
    title: "",
    question: "",
    due_date: "",
    confidential: false,
    conflict_of_interest: false,
    fee_estimate_jpy: "",
  });

  // 事務所・弁護士登録
  const [firmOpen, setFirmOpen] = useState(false);
  const [firmForm, setFirmForm] = useState({
    firm_name: "",
    contact_email: "",
    phone: "",
    address: "",
    notes: "",
  });
  const [lawyerOpen, setLawyerOpen] = useState(false);
  const [lawyerForm, setLawyerForm] = useState({
    firm_id: "",
    lawyer_name: "",
    email: "",
    bar_number: "",
    specialties: "",
  });
  const [saving, setSaving] = useState(false);

  // 回答
  const [answerTarget, setAnswerTarget] = useState<Engagement | null>(null);
  const [answerText, setAnswerText] = useState("");
  const [running, setRunning] = useState(false);

  const loadFirms = useCallback(async () => {
    try {
      const result = await lawFirmsApi.list({ page: 1, size: 200 });
      setFirms(result.items);
      return result.items;
    } catch {
      setFirms([]);
      return [] as LawFirm[];
    }
  }, []);

  const loadEngagements = useCallback(async () => {
    try {
      const result = await engagementsApi.list({ page: 1, size: 100 });
      setEngagements(result.items);
      return true;
    } catch {
      setEngagements([]);
      return false;
    }
  }, []);

  const loadLawyers = useCallback(async (firmId?: string) => {
    try {
      if (firmId) {
        const result = await lawFirmsApi.lawyers(firmId, { page: 1, size: 200 });
        const rows = result.items;
        setLawyerCache((prev) => ({ ...prev, [firmId]: rows }));
        setLawyers(rows);
      } else {
        setLawyers([]);
      }
    } catch {
      if (firmId) setLawyerCache((prev) => ({ ...prev, [firmId]: [] }));
      setLawyers([]);
    }
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    const ok = await loadEngagements();
    setOffline(!ok);
    await loadFirms();
    setLoading(false);
  }, [loadEngagements, loadFirms]);

  useEffect(() => {
    void load();
  }, [load]);

  const firmName = useMemo(() => {
    const map = new Map(firms.map((f) => [String(f.id), f.firm_name]));
    return (id: number | string | null | undefined) =>
      id === null || id === undefined ? "—" : (map.get(String(id)) ?? `事務所 ID ${id}`);
  }, [firms]);

  const filteredEngagements = useMemo(
    () =>
      statusFilter === "all"
        ? engagements
        : engagements.filter((e) => e.status === statusFilter),
    [engagements, statusFilter]
  );

  const refreshEngagements = async () => {
    await loadEngagements();
  };

  // ---- 依頼起票 ----
  const createEngagement = async () => {
    if (!form.firm_id || !form.title.trim() || !form.question.trim() || creating) return;
    setCreating(true);
    setActionError(null);
    try {
      const created = await engagementsApi.create({
        firm_id: form.firm_id,
        lawyer_id: form.lawyer_id || null,
        title: form.title.trim(),
        question: form.question.trim(),
        due_date: form.due_date || null,
        confidential: form.confidential,
        conflict_of_interest: form.conflict_of_interest,
        fee_estimate_jpy: form.fee_estimate_jpy ? Number(form.fee_estimate_jpy) : null,
      });
      setEngagements((prev) => [created, ...prev]);
      setCreateOpen(false);
      setForm({
        firm_id: "",
        lawyer_id: "",
        title: "",
        question: "",
        due_date: "",
        confidential: false,
        conflict_of_interest: false,
        fee_estimate_jpy: "",
      });
    } catch (err) {
      setActionError(
        err instanceof Error ? `依頼起票に失敗しました: ${err.message}` : "依頼起票に失敗しました。"
      );
    } finally {
      setCreating(false);
    }
  };

  // ---- 事務所登録 ----
  const createFirm = async () => {
    if (!firmForm.firm_name.trim() || saving) return;
    setSaving(true);
    setActionError(null);
    try {
      const created = await lawFirmsApi.create({
        firm_name: firmForm.firm_name.trim(),
        contact_email: firmForm.contact_email || null,
        phone: firmForm.phone || null,
        address: firmForm.address || null,
        notes: firmForm.notes || null,
      });
      setFirms((prev) => [...prev, created]);
      setFirmOpen(false);
      setFirmForm({ firm_name: "", contact_email: "", phone: "", address: "", notes: "" });
    } catch (err) {
      setActionError(
        err instanceof Error ? `事務所登録に失敗しました: ${err.message}` : "事務所登録に失敗しました。"
      );
    } finally {
      setSaving(false);
    }
  };

  // ---- 弁護士登録 ----
  const createLawyer = async () => {
    if (!lawyerForm.firm_id || !lawyerForm.lawyer_name.trim() || saving) return;
    setSaving(true);
    setActionError(null);
    try {
      const created = await lawFirmsApi.createLawyer(lawyerForm.firm_id, {
        firm_id: lawyerForm.firm_id,
        lawyer_name: lawyerForm.lawyer_name.trim(),
        email: lawyerForm.email || null,
        bar_number: lawyerForm.bar_number || null,
        specialties: lawyerForm.specialties || null,
      });
      setLawyers((prev) => [...prev, created]);
      setLawyerOpen(false);
      setLawyerForm({
        firm_id: "",
        lawyer_name: "",
        email: "",
        bar_number: "",
        specialties: "",
      });
    } catch (err) {
      setActionError(
        err instanceof Error ? `弁護士登録に失敗しました: ${err.message}` : "弁護士登録に失敗しました。"
      );
    } finally {
      setSaving(false);
    }
  };

  // ---- 回答 ----
  const submitAnswer = async () => {
    if (!answerTarget || !answerText.trim() || running) return;
    setRunning(true);
    setActionError(null);
    try {
      const updated = await engagementsApi.answer(answerTarget.id, {
        answer: answerText.trim(),
      });
      setEngagements((prev) =>
        prev.map((e) => (String(e.id) === String(answerTarget.id) ? updated : e))
      );
      setAnswerTarget(null);
      setAnswerText("");
    } catch (err) {
      setActionError(
        err instanceof Error ? `回答登録に失敗しました: ${err.message}` : "回答登録に失敗しました。"
      );
    } finally {
      setRunning(false);
    }
  };

  const confirmEngagement = async (engagement: Engagement) => {
    setActionError(null);
    try {
      const updated = await engagementsApi.confirm(engagement.id);
      setEngagements((prev) =>
        prev.map((e) => (String(e.id) === String(engagement.id) ? updated : e))
      );
    } catch (err) {
      setActionError(
        err instanceof Error ? `確認に失敗しました: ${err.message}` : "確認に失敗しました。"
      );
    }
  };

  const cancelEngagement = async (engagement: Engagement) => {
    setActionError(null);
    try {
      const updated = await engagementsApi.cancel(engagement.id, {
        reason: "依頼側の都合による取消",
      });
      setEngagements((prev) =>
        prev.map((e) => (String(e.id) === String(engagement.id) ? updated : e))
      );
    } catch (err) {
      setActionError(
        err instanceof Error ? `取消に失敗しました: ${err.message}` : "取消に失敗しました。"
      );
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">顧問弁護士</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            法律事務所・担当弁護士の台帳と、依頼・回答・確認を管理します
          </p>
        </div>
        <Button
          onClick={() => {
            setActionError(null);
            setCreateOpen(true);
            void loadFirms();
          }}
          className="gap-2"
        >
          <Plus className="h-4 w-4" aria-hidden="true" />
          依頼を起票
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

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="engagements">依頼・回答</TabsTrigger>
          <TabsTrigger value="firms">法律事務所</TabsTrigger>
          <TabsTrigger value="lawyers">担当弁護士</TabsTrigger>
        </TabsList>

        {/* ---- 依頼・回答 ---- */}
        <TabsContent value="engagements">
          <Card>
            <div className="flex items-center justify-between border-b px-6 py-4">
              <p className="text-sm font-semibold">依頼一覧（依頼 → 回答 → 確認）</p>
              <div className="flex items-center gap-2">
                <Select value={statusFilter} onValueChange={setStatusFilter}>
                  <SelectTrigger className="w-36" aria-label="状態で絞り込み">
                    <SelectValue placeholder="状態" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">すべての状態</SelectItem>
                    {Object.entries(ENG_STATUS_LABELS).map(([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => void refreshEngagements()}
                  aria-label="再読み込み"
                >
                  <RefreshCw className="h-4 w-4" />
                </Button>
              </div>
            </div>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-32">依頼 No</TableHead>
                  <TableHead>依頼内容</TableHead>
                  <TableHead className="w-36">事務所</TableHead>
                  <TableHead className="w-24">状態</TableHead>
                  <TableHead className="w-24">回答期限</TableHead>
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
                ) : filteredEngagements.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="py-10 text-center text-sm text-muted-foreground">
                      依頼がありません。「依頼を起票」から登録してください。
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredEngagements.map((engagement) => (
                    <TableRow key={String(engagement.id)}>
                      <TableCell className="whitespace-nowrap font-mono text-sm">
                        {engagement.engagement_no}
                      </TableCell>
                      <TableCell className="max-w-[220px]">
                        <p className="truncate text-sm font-medium">{engagement.title}</p>
                        <p className="line-clamp-1 text-xs text-muted-foreground">
                          {engagement.question}
                        </p>
                        {engagement.confidential && (
                          <Badge variant="secondary" className="mt-1 text-xs">
                            Confidential
                          </Badge>
                        )}
                        {engagement.conflict_of_interest && (
                          <Badge variant="destructive" className="mt-1 text-xs">
                            利益相反要確認
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-sm">{firmName(engagement.firm_id)}</TableCell>
                      <TableCell>
                        <Badge variant={ENG_STATUS_VARIANT[engagement.status] ?? "outline"}>
                          {ENG_STATUS_LABELS[engagement.status] ?? engagement.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="whitespace-nowrap text-sm">
                        {formatDate(engagement.due_date)}
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {engagement.status === "open" && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                setAnswerTarget(engagement);
                                setAnswerText("");
                              }}
                            >
                              回答を登録
                            </Button>
                          )}
                          {engagement.status === "answered" && (
                            <Button
                              size="sm"
                              onClick={() => void confirmEngagement(engagement)}
                            >
                              <CheckCircle2 className="mr-1 h-3 w-3" aria-hidden="true" />
                              確認
                            </Button>
                          )}
                          {(engagement.status === "open" ||
                            engagement.status === "answered") && (
                            <Button
                              size="sm"
                              variant="ghost"
                              className="text-destructive"
                              onClick={() => void cancelEngagement(engagement)}
                            >
                              <XCircle className="mr-1 h-3 w-3" aria-hidden="true" />
                              取消
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </Card>
        </TabsContent>

        {/* ---- 法律事務所 ---- */}
        <TabsContent value="firms">
          <Card>
            <div className="flex items-center justify-between border-b px-6 py-4">
              <p className="text-sm font-semibold">法律事務所台帳</p>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setActionError(null);
                  setFirmOpen(true);
                }}
                className="gap-2"
              >
                <Building2 className="h-4 w-4" aria-hidden="true" />
                事務所を登録
              </Button>
            </div>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>事務所名</TableHead>
                  <TableHead className="w-48">連絡先メール</TableHead>
                  <TableHead className="w-32">電話</TableHead>
                  <TableHead className="w-20">状態</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {firms.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={4} className="py-10 text-center text-sm text-muted-foreground">
                      事務所が登録されていません。
                    </TableCell>
                  </TableRow>
                ) : (
                  firms.map((firm) => (
                    <TableRow key={String(firm.id)}>
                      <TableCell className="text-sm font-medium">{firm.firm_name}</TableCell>
                      <TableCell className="text-sm">{firm.contact_email ?? "—"}</TableCell>
                      <TableCell className="text-sm">{firm.phone ?? "—"}</TableCell>
                      <TableCell>
                        <Badge variant={firm.is_active ? "default" : "outline"}>
                          {firm.is_active ? "有効" : "停止"}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </Card>
        </TabsContent>

        {/* ---- 担当弁護士 ---- */}
        <TabsContent value="lawyers">
          <Card>
            <div className="flex flex-wrap items-center justify-between gap-2 border-b px-6 py-4">
              <p className="text-sm font-semibold">担当弁護士</p>
              <div className="flex items-center gap-2">
                <Select
                  value={lawyerForm.firm_id || "all"}
                  onValueChange={(v) => {
                    if (v === "all") {
                      setLawyerForm((f) => ({ ...f, firm_id: "" }));
                      setLawyers([]);
                    } else {
                      setLawyerForm((f) => ({ ...f, firm_id: v }));
                      void loadLawyers(v);
                    }
                  }}
                >
                  <SelectTrigger className="w-56" aria-label="事務所で絞り込み">
                    <SelectValue placeholder="事務所を選択" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">すべての事務所</SelectItem>
                    {firms.map((f) => (
                      <SelectItem key={String(f.id)} value={String(f.id)}>
                        {f.firm_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setActionError(null);
                    setLawyerOpen(true);
                    void loadFirms();
                  }}
                  className="gap-2"
                >
                  <UserRound className="h-4 w-4" aria-hidden="true" />
                  弁護士を登録
                </Button>
              </div>
            </div>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>弁護士名</TableHead>
                  <TableHead className="w-40">事務所</TableHead>
                  <TableHead className="w-44">メール</TableHead>
                  <TableHead className="w-28">弁護士番号</TableHead>
                  <TableHead>専門分野</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {lawyers.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="py-10 text-center text-sm text-muted-foreground">
                      事務所を選択するか、弁護士を登録してください。
                    </TableCell>
                  </TableRow>
                ) : (
                  lawyers.map((lawyer) => (
                    <TableRow key={String(lawyer.id)}>
                      <TableCell className="text-sm font-medium">{lawyer.lawyer_name}</TableCell>
                      <TableCell className="text-sm">{firmName(lawyer.firm_id)}</TableCell>
                      <TableCell className="text-sm">{lawyer.email ?? "—"}</TableCell>
                      <TableCell className="text-sm">{lawyer.bar_number ?? "—"}</TableCell>
                      <TableCell className="text-sm">{lawyer.specialties ?? "—"}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </Card>
        </TabsContent>
      </Tabs>

      {/* ---- 依頼起票ダイアログ ---- */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Scale className="h-5 w-5 text-primary" aria-hidden="true" />
              顧問弁護士へ依頼を起票
            </DialogTitle>
            <DialogDescription>
              法律事務所と質問内容を指定します。ID は LEG-YYYY-NNNNNN 形式で採番されます。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="eng-firm">法律事務所（必須）</Label>
              <Select
                value={form.firm_id}
                onValueChange={(v) => {
                  setForm((f) => ({ ...f, firm_id: v, lawyer_id: "" }));
                  void loadLawyers(v);
                }}
              >
                <SelectTrigger id="eng-firm" aria-label="法律事務所">
                  <SelectValue placeholder="事務所を選択" />
                </SelectTrigger>
                <SelectContent>
                  {firms.map((f) => (
                    <SelectItem key={String(f.id)} value={String(f.id)}>
                      {f.firm_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="eng-lawyer">担当弁護士（任意）</Label>
              <Select
                value={form.lawyer_id}
                onValueChange={(v) => setForm((f) => ({ ...f, lawyer_id: v }))}
              >
                <SelectTrigger id="eng-lawyer" aria-label="担当弁護士">
                  <SelectValue placeholder="選択（未指定で可）" />
                </SelectTrigger>
                <SelectContent>
                  {(lawyerCache[form.firm_id] ?? []).map((l) => (
                    <SelectItem key={String(l.id)} value={String(l.id)}>
                      {l.lawyer_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="eng-title">依頼タイトル（必須）</Label>
              <Input
                id="eng-title"
                value={form.title}
                onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                placeholder="例: ◯◯工事のクレーム対応についての法的助言"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="eng-question">質問内容（必須）</Label>
              <Textarea
                id="eng-question"
                value={form.question}
                onChange={(e) => setForm((f) => ({ ...f, question: e.target.value }))}
                rows={4}
                placeholder="事実関係と論点を記載してください"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="eng-due">回答期限</Label>
                <Input
                  id="eng-due"
                  type="date"
                  value={form.due_date}
                  onChange={(e) => setForm((f) => ({ ...f, due_date: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="eng-fee">費用見込み（円・任意）</Label>
                <Input
                  id="eng-fee"
                  type="number"
                  min={0}
                  value={form.fee_estimate_jpy}
                  onChange={(e) => setForm((f) => ({ ...f, fee_estimate_jpy: e.target.value }))}
                />
              </div>
            </div>
            <div className="flex items-center gap-6">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.confidential}
                  onChange={(e) => setForm((f) => ({ ...f, confidential: e.target.checked }))}
                />
                Confidential（秘匿案件）
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.conflict_of_interest}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, conflict_of_interest: e.target.checked }))
                  }
                />
                利益相反の可能性
              </label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              キャンセル
            </Button>
            <Button
              onClick={() => void createEngagement()}
              disabled={!form.firm_id || !form.title.trim() || !form.question.trim() || creating}
            >
              {creating && <Loader2 className="mr-1 h-4 w-4 animate-spin" aria-hidden="true" />}
              起票
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ---- 回答ダイアログ ---- */}
      <Dialog
        open={answerTarget !== null}
        onOpenChange={(open) => {
          if (!open) setAnswerTarget(null);
        }}
      >
        <DialogContent className="max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>回答を登録</DialogTitle>
            <DialogDescription>
              {answerTarget?.engagement_no} — {answerTarget?.title}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <p className="text-xs font-semibold text-muted-foreground">依頼内容</p>
              <p className="mt-1 whitespace-pre-wrap rounded-md border bg-muted/40 p-3 text-sm">
                {answerTarget?.question}
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="answer-text">回答内容（必須）</Label>
              <Textarea
                id="answer-text"
                value={answerText}
                onChange={(e) => setAnswerText(e.target.value)}
                rows={8}
                placeholder="法的助言の回答を記載してください（最終判断は社内で行います）"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAnswerTarget(null)}>
              キャンセル
            </Button>
            <Button onClick={() => void submitAnswer()} disabled={!answerText.trim() || running}>
              {running && <Loader2 className="mr-1 h-4 w-4 animate-spin" aria-hidden="true" />}
              回答を登録
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ---- 事務所登録ダイアログ ---- */}
      <Dialog open={firmOpen} onOpenChange={setFirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>法律事務所を登録</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="firm-name">事務所名（必須）</Label>
              <Input
                id="firm-name"
                value={firmForm.firm_name}
                onChange={(e) => setFirmForm((f) => ({ ...f, firm_name: e.target.value }))}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="firm-email">連絡先メール</Label>
                <Input
                  id="firm-email"
                  type="email"
                  value={firmForm.contact_email}
                  onChange={(e) => setFirmForm((f) => ({ ...f, contact_email: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="firm-phone">電話</Label>
                <Input
                  id="firm-phone"
                  value={firmForm.phone}
                  onChange={(e) => setFirmForm((f) => ({ ...f, phone: e.target.value }))}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="firm-address">所在地</Label>
              <Input
                id="firm-address"
                value={firmForm.address}
                onChange={(e) => setFirmForm((f) => ({ ...f, address: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="firm-notes">メモ</Label>
              <Textarea
                id="firm-notes"
                value={firmForm.notes}
                onChange={(e) => setFirmForm((f) => ({ ...f, notes: e.target.value }))}
                rows={2}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setFirmOpen(false)}>
              キャンセル
            </Button>
            <Button onClick={() => void createFirm()} disabled={!firmForm.firm_name.trim() || saving}>
              {saving && <Loader2 className="mr-1 h-4 w-4 animate-spin" aria-hidden="true" />}
              登録
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ---- 弁護士登録ダイアログ ---- */}
      <Dialog open={lawyerOpen} onOpenChange={setLawyerOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>担当弁護士を登録</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="law-firm">所属事務所（必須）</Label>
              <Select
                value={lawyerForm.firm_id}
                onValueChange={(v) => setLawyerForm((f) => ({ ...f, firm_id: v }))}
              >
                <SelectTrigger id="law-firm" aria-label="所属事務所">
                  <SelectValue placeholder="事務所を選択" />
                </SelectTrigger>
                <SelectContent>
                  {firms.map((f) => (
                    <SelectItem key={String(f.id)} value={String(f.id)}>
                      {f.firm_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="law-name">弁護士名（必須）</Label>
              <Input
                id="law-name"
                value={lawyerForm.lawyer_name}
                onChange={(e) => setLawyerForm((f) => ({ ...f, lawyer_name: e.target.value }))}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="law-email">メール</Label>
                <Input
                  id="law-email"
                  type="email"
                  value={lawyerForm.email}
                  onChange={(e) => setLawyerForm((f) => ({ ...f, email: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="law-bar">弁護士番号</Label>
                <Input
                  id="law-bar"
                  value={lawyerForm.bar_number}
                  onChange={(e) => setLawyerForm((f) => ({ ...f, bar_number: e.target.value }))}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="law-spec">専門分野</Label>
              <Input
                id="law-spec"
                value={lawyerForm.specialties}
                onChange={(e) => setLawyerForm((f) => ({ ...f, specialties: e.target.value }))}
                placeholder="例: 建設紛争・労務"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setLawyerOpen(false)}>
              キャンセル
            </Button>
            <Button
              onClick={() => void createLawyer()}
              disabled={!lawyerForm.firm_id || !lawyerForm.lawyer_name.trim() || saving}
            >
              {saving && <Loader2 className="mr-1 h-4 w-4 animate-spin" aria-hidden="true" />}
              登録
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
