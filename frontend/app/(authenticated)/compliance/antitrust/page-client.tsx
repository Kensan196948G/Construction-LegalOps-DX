"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  GraduationCap,
  Loader2,
  MessageCircleQuestion,
  Plus,
  RefreshCw,
  ShieldAlert,
  XCircle,
} from "lucide-react";

import { AiDisclaimerInline } from "@/components/legal/ai-disclaimer-inline";
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
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { antitrustApi } from "@/lib/api";
import type {
  AntitrustApplication,
  AntitrustCheck,
  AntitrustConsultation,
  ComplianceTraining,
} from "@/lib/api/schemas";

const CHECK_TYPE_LABELS: Record<string, string> = {
  general: "独禁法チェック（一般）",
  bid_rigging: "入札談合リスクチェック",
  price_exchange: "価格情報交換禁止チェック",
  jv_formation: "JV 形成時競争法チェック",
  joint_research: "競合との共同研究チェック",
};

const SEVERITY_LABELS: Record<string, string> = {
  info: "問題なし",
  warn: "要確認",
  block: "重大リスク",
};

const SEVERITY_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  info: "outline",
  warn: "secondary",
  block: "destructive",
};

const APPLICATION_TYPE_LABELS: Record<string, string> = {
  competitor_contact: "競合他社接触記録",
  meeting_social: "会合・懇親会事前申請",
  entertainment_gift: "贈収賄・接待管理",
  public_official_contact: "公務員接触記録",
  donation_sponsorship: "寄付・協賛審査",
};

const APPLICATION_STATUS_LABELS: Record<string, string> = {
  submitted: "申請中",
  approved: "承認済み",
  rejected: "却下",
  completed: "実施済み",
  cancelled: "取下げ",
};

const APPLICATION_STATUS_VARIANT: Record<
  string,
  "default" | "secondary" | "destructive" | "outline"
> = {
  submitted: "outline",
  approved: "default",
  rejected: "destructive",
  completed: "secondary",
  cancelled: "destructive",
};

export default function AntitrustCompliancePage() {
  const [tab, setTab] = useState("checks");
  const [offline, setOffline] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  // ---- #113/#114/#117/#118/#119 チェック ------------------------------
  const [checks, setChecks] = useState<AntitrustCheck[]>([]);
  const [checksLoading, setChecksLoading] = useState(true);
  const [checkTypeFilter, setCheckTypeFilter] = useState("all");
  const [checkOpen, setCheckOpen] = useState(false);
  const [checkRunning, setCheckRunning] = useState(false);
  const [checkForm, setCheckForm] = useState({
    check_type: "general",
    subject: "",
    text: "",
    is_public_bid: false,
    contacted_competitors: false,
    pre_bid_price_shared: false,
    counterparty_is_competitor: false,
    is_competitor_jv: false,
    scope_covers_pricing: false,
    with_competitor: false,
    covers_pricing_or_output: false,
  });

  const loadChecks = useCallback(async () => {
    setChecksLoading(true);
    try {
      const result = await antitrustApi.listChecks({ page: 1, size: 100 });
      setChecks(result.items);
      setOffline(false);
    } catch {
      setChecks([]);
      setOffline(true);
    } finally {
      setChecksLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadChecks();
  }, [loadChecks]);

  const filteredChecks = useMemo(
    () =>
      checkTypeFilter === "all"
        ? checks
        : checks.filter((c) => c.check_type === checkTypeFilter),
    [checks, checkTypeFilter],
  );

  const buildCheckContext = () => {
    switch (checkForm.check_type) {
      case "bid_rigging":
        return {
          text: checkForm.text || undefined,
          is_public_bid: checkForm.is_public_bid,
          contacted_competitors: checkForm.contacted_competitors,
          pre_bid_price_shared: checkForm.pre_bid_price_shared,
        };
      case "price_exchange":
        return {
          counterparty_is_competitor: checkForm.counterparty_is_competitor,
          exchanged_topics: checkForm.counterparty_is_competitor ? ["price"] : [],
        };
      case "jv_formation":
        return {
          is_competitor_jv: checkForm.is_competitor_jv,
          scope_covers_pricing: checkForm.scope_covers_pricing,
        };
      case "joint_research":
        return {
          with_competitor: checkForm.with_competitor,
          covers_pricing_or_output: checkForm.covers_pricing_or_output,
        };
      default:
        return { text: checkForm.text };
    }
  };

  const runCheck = async () => {
    if (!checkForm.subject.trim() || checkRunning) return;
    setCheckRunning(true);
    setActionError(null);
    try {
      await antitrustApi.runCheck({
        check_type: checkForm.check_type,
        subject: checkForm.subject.trim(),
        context: buildCheckContext(),
      });
      setCheckOpen(false);
      setCheckForm((f) => ({ ...f, subject: "", text: "" }));
      await loadChecks();
    } catch (err) {
      setActionError(
        err instanceof Error ? `チェック実行に失敗しました: ${err.message}` : "チェック実行に失敗しました。",
      );
    } finally {
      setCheckRunning(false);
    }
  };

  // ---- #115/#116/#121/#122/#123 事前申請 -----------------------------
  const [applications, setApplications] = useState<AntitrustApplication[]>([]);
  const [applicationsLoading, setApplicationsLoading] = useState(true);
  const [appStatusFilter, setAppStatusFilter] = useState("all");
  const [appOpen, setAppOpen] = useState(false);
  const [appCreating, setAppCreating] = useState(false);
  const [appForm, setAppForm] = useState({
    application_type: "competitor_contact",
    title: "",
    counterparty_name: "",
    counterparty_organization: "",
    purpose: "",
    amount_jpy: "",
  });
  const [decisionTarget, setDecisionTarget] = useState<AntitrustApplication | null>(null);
  const [decisionNote, setDecisionNote] = useState("");
  const [completeTarget, setCompleteTarget] = useState<AntitrustApplication | null>(null);
  const [outcomeNote, setOutcomeNote] = useState("");
  const [cancelTarget, setCancelTarget] = useState<AntitrustApplication | null>(null);
  const [cancelReason, setCancelReason] = useState("");
  const [appBusy, setAppBusy] = useState(false);

  const loadApplications = useCallback(async () => {
    setApplicationsLoading(true);
    try {
      const result = await antitrustApi.listApplications({ page: 1, size: 100 });
      setApplications(result.items);
    } catch {
      setApplications([]);
    } finally {
      setApplicationsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadApplications();
  }, [loadApplications]);

  const filteredApplications = useMemo(
    () =>
      appStatusFilter === "all"
        ? applications
        : applications.filter((a) => a.status === appStatusFilter),
    [applications, appStatusFilter],
  );

  const createApplication = async () => {
    if (!appForm.title.trim() || appCreating) return;
    setAppCreating(true);
    setActionError(null);
    try {
      await antitrustApi.createApplication({
        application_type: appForm.application_type,
        title: appForm.title.trim(),
        counterparty_name: appForm.counterparty_name || null,
        counterparty_organization: appForm.counterparty_organization || null,
        purpose: appForm.purpose || null,
        amount_jpy: appForm.amount_jpy ? Number(appForm.amount_jpy) : null,
      });
      setAppOpen(false);
      setAppForm({
        application_type: "competitor_contact",
        title: "",
        counterparty_name: "",
        counterparty_organization: "",
        purpose: "",
        amount_jpy: "",
      });
      await loadApplications();
    } catch (err) {
      setActionError(
        err instanceof Error ? `申請登録に失敗しました: ${err.message}` : "申請登録に失敗しました。",
      );
    } finally {
      setAppCreating(false);
    }
  };

  const decide = async (decision: "approved" | "rejected") => {
    if (!decisionTarget || appBusy) return;
    setAppBusy(true);
    setActionError(null);
    try {
      await antitrustApi.decideApplication(decisionTarget.id, {
        decision,
        decision_note: decisionNote || null,
      });
      setDecisionTarget(null);
      setDecisionNote("");
      await loadApplications();
    } catch (err) {
      setActionError(
        err instanceof Error ? `承認処理に失敗しました: ${err.message}` : "承認処理に失敗しました。",
      );
    } finally {
      setAppBusy(false);
    }
  };

  const complete = async () => {
    if (!completeTarget || !outcomeNote.trim() || appBusy) return;
    setAppBusy(true);
    setActionError(null);
    try {
      await antitrustApi.completeApplication(completeTarget.id, {
        outcome_note: outcomeNote.trim(),
      });
      setCompleteTarget(null);
      setOutcomeNote("");
      await loadApplications();
    } catch (err) {
      setActionError(
        err instanceof Error ? `実施記録の登録に失敗しました: ${err.message}` : "実施記録の登録に失敗しました。",
      );
    } finally {
      setAppBusy(false);
    }
  };

  const cancel = async () => {
    if (!cancelTarget || !cancelReason.trim() || appBusy) return;
    setAppBusy(true);
    setActionError(null);
    try {
      await antitrustApi.cancelApplication(cancelTarget.id, {
        cancel_reason: cancelReason.trim(),
      });
      setCancelTarget(null);
      setCancelReason("");
      await loadApplications();
    } catch (err) {
      setActionError(
        err instanceof Error ? `取下げに失敗しました: ${err.message}` : "取下げに失敗しました。",
      );
    } finally {
      setAppBusy(false);
    }
  };

  // ---- #120 競争法 AI 相談 --------------------------------------------
  const [consultations, setConsultations] = useState<AntitrustConsultation[]>([]);
  const [consultQuery, setConsultQuery] = useState("");
  const [consultRunning, setConsultRunning] = useState(false);
  const [latestAnswer, setLatestAnswer] = useState<AntitrustConsultation | null>(null);

  const loadConsultations = useCallback(async () => {
    try {
      const result = await antitrustApi.listConsultations({ page: 1, size: 50 });
      setConsultations(result.items);
    } catch {
      setConsultations([]);
    }
  }, []);

  useEffect(() => {
    void loadConsultations();
  }, [loadConsultations]);

  const askConsultation = async () => {
    if (!consultQuery.trim() || consultRunning) return;
    setConsultRunning(true);
    setActionError(null);
    try {
      const result = await antitrustApi.consult({ query_text: consultQuery.trim() });
      setLatestAnswer(result);
      setConsultQuery("");
      await loadConsultations();
    } catch (err) {
      setActionError(
        err instanceof Error ? `相談の送信に失敗しました: ${err.message}` : "相談の送信に失敗しました。",
      );
    } finally {
      setConsultRunning(false);
    }
  };

  // ---- #124 コンプライアンス研修履歴 -----------------------------------
  const [trainings, setTrainings] = useState<ComplianceTraining[]>([]);
  const [trainingOpen, setTrainingOpen] = useState(false);
  const [trainingSaving, setTrainingSaving] = useState(false);
  const [trainingForm, setTrainingForm] = useState({
    training_title: "",
    attendee_name: "",
    category: "antitrust",
    completed_at: "",
    score: "",
  });

  const loadTrainings = useCallback(async () => {
    try {
      const result = await antitrustApi.listTrainings({ page: 1, size: 100 });
      setTrainings(result.items);
    } catch {
      setTrainings([]);
    }
  }, []);

  useEffect(() => {
    void loadTrainings();
  }, [loadTrainings]);

  const createTraining = async () => {
    if (!trainingForm.training_title.trim() || !trainingForm.completed_at || trainingSaving) return;
    setTrainingSaving(true);
    setActionError(null);
    try {
      await antitrustApi.createTraining({
        training_title: trainingForm.training_title.trim(),
        completed_at: trainingForm.completed_at,
        attendee_name: trainingForm.attendee_name || null,
        category: trainingForm.category,
        score: trainingForm.score ? Number(trainingForm.score) : null,
      });
      setTrainingOpen(false);
      setTrainingForm({
        training_title: "",
        attendee_name: "",
        category: "antitrust",
        completed_at: "",
        score: "",
      });
      await loadTrainings();
    } catch (err) {
      setActionError(
        err instanceof Error ? `研修履歴の登録に失敗しました: ${err.message}` : "研修履歴の登録に失敗しました。",
      );
    } finally {
      setTrainingSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <header>
        <h1 className="flex items-center gap-2 text-2xl font-bold text-foreground">
          <ShieldAlert className="h-6 w-6 text-primary" aria-hidden="true" />
          独禁法・入札談合コンプライアンス
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          独禁法・入札談合リスクの機械チェック、競合接触・接待・寄付等の事前申請ワークフロー、
          競争法 AI 相談、研修履歴を一元管理します（Issue #122）。
        </p>
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
          <TabsTrigger value="checks">チェック実行</TabsTrigger>
          <TabsTrigger value="applications">事前申請</TabsTrigger>
          <TabsTrigger value="consultations">AI 相談</TabsTrigger>
          <TabsTrigger value="trainings">研修履歴</TabsTrigger>
        </TabsList>

        {/* ---- チェック実行 ---- */}
        <TabsContent value="checks">
          <Card>
            <div className="flex flex-wrap items-center justify-between gap-2 border-b px-6 py-4">
              <p className="text-sm font-semibold">
                独禁法・入札談合等チェック（決定論的ルールベース・AI 不使用）
              </p>
              <div className="flex items-center gap-2">
                <Select value={checkTypeFilter} onValueChange={setCheckTypeFilter}>
                  <SelectTrigger className="w-56" aria-label="チェック種別で絞り込み">
                    <SelectValue placeholder="チェック種別" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">すべての種別</SelectItem>
                    {Object.entries(CHECK_TYPE_LABELS).map(([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button variant="outline" size="icon" onClick={() => void loadChecks()} aria-label="再読み込み">
                  <RefreshCw className="h-4 w-4" />
                </Button>
                <Button onClick={() => setCheckOpen(true)} className="gap-2">
                  <Plus className="h-4 w-4" aria-hidden="true" />
                  チェックを実行
                </Button>
              </div>
            </div>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-32">チェック No</TableHead>
                  <TableHead className="w-48">種別</TableHead>
                  <TableHead>対象</TableHead>
                  <TableHead className="w-28">結果</TableHead>
                  <TableHead className="w-40">実施日時</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {checksLoading ? (
                  <TableRow>
                    <TableCell colSpan={5} className="py-10 text-center text-sm text-muted-foreground">
                      <Loader2 className="mx-auto h-6 w-6 animate-spin" aria-hidden="true" />
                      読み込み中…
                    </TableCell>
                  </TableRow>
                ) : filteredChecks.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="py-10 text-center text-sm text-muted-foreground">
                      チェック結果がありません。「チェックを実行」から開始してください。
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredChecks.map((c) => (
                    <TableRow key={String(c.id)}>
                      <TableCell className="whitespace-nowrap font-mono text-sm">{c.check_no}</TableCell>
                      <TableCell className="text-sm">
                        {CHECK_TYPE_LABELS[c.check_type] ?? c.check_type}
                      </TableCell>
                      <TableCell className="max-w-[280px]">
                        <p className="truncate text-sm">{c.subject}</p>
                      </TableCell>
                      <TableCell>
                        <Badge variant={SEVERITY_VARIANT[c.severity] ?? "outline"}>
                          {SEVERITY_LABELS[c.severity] ?? c.severity}
                        </Badge>
                      </TableCell>
                      <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                        {new Date(c.checked_at).toLocaleString("ja-JP")}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </Card>
        </TabsContent>

        {/* ---- 事前申請 ---- */}
        <TabsContent value="applications">
          <Card>
            <div className="flex flex-wrap items-center justify-between gap-2 border-b px-6 py-4">
              <p className="text-sm font-semibold">
                事前申請（競合接触/会合懇親会/接待/公務員接触/寄付協賛） → 承認 → 記録
              </p>
              <div className="flex items-center gap-2">
                <Select value={appStatusFilter} onValueChange={setAppStatusFilter}>
                  <SelectTrigger className="w-36" aria-label="状態で絞り込み">
                    <SelectValue placeholder="状態" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">すべての状態</SelectItem>
                    {Object.entries(APPLICATION_STATUS_LABELS).map(([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => void loadApplications()}
                  aria-label="再読み込み"
                >
                  <RefreshCw className="h-4 w-4" />
                </Button>
                <Button onClick={() => setAppOpen(true)} className="gap-2">
                  <Plus className="h-4 w-4" aria-hidden="true" />
                  事前申請を登録
                </Button>
              </div>
            </div>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-32">申請 No</TableHead>
                  <TableHead className="w-44">種別</TableHead>
                  <TableHead>内容</TableHead>
                  <TableHead className="w-24">状態</TableHead>
                  <TableHead className="w-56">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {applicationsLoading ? (
                  <TableRow>
                    <TableCell colSpan={5} className="py-10 text-center text-sm text-muted-foreground">
                      <Loader2 className="mx-auto h-6 w-6 animate-spin" aria-hidden="true" />
                      読み込み中…
                    </TableCell>
                  </TableRow>
                ) : filteredApplications.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="py-10 text-center text-sm text-muted-foreground">
                      事前申請がありません。「事前申請を登録」から作成してください。
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredApplications.map((a) => (
                    <TableRow key={String(a.id)}>
                      <TableCell className="whitespace-nowrap font-mono text-sm">
                        {a.application_no}
                      </TableCell>
                      <TableCell className="text-sm">
                        {APPLICATION_TYPE_LABELS[a.application_type] ?? a.application_type}
                      </TableCell>
                      <TableCell className="max-w-[260px]">
                        <p className="truncate text-sm font-medium">{a.title}</p>
                        {a.counterparty_name && (
                          <p className="truncate text-xs text-muted-foreground">
                            相手方: {a.counterparty_name}
                          </p>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge variant={APPLICATION_STATUS_VARIANT[a.status] ?? "outline"}>
                          {APPLICATION_STATUS_LABELS[a.status] ?? a.status}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {a.status === "submitted" && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                setDecisionTarget(a);
                                setDecisionNote("");
                              }}
                            >
                              承認・却下
                            </Button>
                          )}
                          {a.status === "approved" && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                setCompleteTarget(a);
                                setOutcomeNote("");
                              }}
                            >
                              実施記録
                            </Button>
                          )}
                          {(a.status === "submitted" || a.status === "approved") && (
                            <Button
                              size="sm"
                              variant="ghost"
                              className="text-destructive"
                              onClick={() => {
                                setCancelTarget(a);
                                setCancelReason("");
                              }}
                            >
                              取下げ
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

        {/* ---- AI 相談 ---- */}
        <TabsContent value="consultations">
          <div className="space-y-4">
            <AiDisclaimerInline>
              本回答は一次情報コーパスの検索結果に基づく参考情報です。個別事案への当てはめ・
              最終的な法的判断は法務担当者・顧問弁護士が行います。
            </AiDisclaimerInline>
            <Card className="p-6">
              <div className="space-y-3">
                <Label htmlFor="at-consult-query" className="flex items-center gap-1">
                  <MessageCircleQuestion className="h-4 w-4" aria-hidden="true" />
                  競争法に関する質問（#120）
                </Label>
                <Textarea
                  id="at-consult-query"
                  value={consultQuery}
                  onChange={(e) => setConsultQuery(e.target.value)}
                  rows={3}
                  placeholder="例: 業界団体の会合で価格の話題が出た場合の注意点は？"
                />
                <Button
                  onClick={() => void askConsultation()}
                  disabled={!consultQuery.trim() || consultRunning}
                  className="gap-2"
                >
                  {consultRunning && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
                  相談する
                </Button>
              </div>
              {latestAnswer && (
                <div className="mt-4 whitespace-pre-wrap rounded-md border bg-muted/40 p-4 text-sm">
                  {latestAnswer.answer_text}
                </div>
              )}
            </Card>

            <Card>
              <div className="border-b px-6 py-4">
                <p className="text-sm font-semibold">相談履歴</p>
              </div>
              <div className="divide-y">
                {consultations.length === 0 ? (
                  <p className="px-6 py-8 text-center text-sm text-muted-foreground">
                    相談履歴はありません。
                  </p>
                ) : (
                  consultations.map((c) => (
                    <div key={String(c.id)} className="px-6 py-4">
                      <p className="text-sm font-medium">{c.query_text}</p>
                      <p className="mt-1 whitespace-pre-wrap text-xs text-muted-foreground">
                        {c.answer_text}
                      </p>
                    </div>
                  ))
                )}
              </div>
            </Card>
          </div>
        </TabsContent>

        {/* ---- 研修履歴 ---- */}
        <TabsContent value="trainings">
          <Card>
            <div className="flex flex-wrap items-center justify-between gap-2 border-b px-6 py-4">
              <p className="flex items-center gap-2 text-sm font-semibold">
                <GraduationCap className="h-4 w-4 text-primary" aria-hidden="true" />
                コンプライアンス研修履歴（#124）
              </p>
              <div className="flex items-center gap-2">
                <Button variant="outline" size="icon" onClick={() => void loadTrainings()} aria-label="再読み込み">
                  <RefreshCw className="h-4 w-4" />
                </Button>
                <Button onClick={() => setTrainingOpen(true)} className="gap-2">
                  <Plus className="h-4 w-4" aria-hidden="true" />
                  研修履歴を登録
                </Button>
              </div>
            </div>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>研修名</TableHead>
                  <TableHead className="w-40">受講者</TableHead>
                  <TableHead className="w-28">分類</TableHead>
                  <TableHead className="w-32">受講日</TableHead>
                  <TableHead className="w-20">得点</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {trainings.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="py-10 text-center text-sm text-muted-foreground">
                      研修履歴が登録されていません。
                    </TableCell>
                  </TableRow>
                ) : (
                  trainings.map((t) => (
                    <TableRow key={String(t.id)}>
                      <TableCell className="max-w-[280px] truncate text-sm">{t.training_title}</TableCell>
                      <TableCell className="text-sm">{t.attendee_name ?? "—"}</TableCell>
                      <TableCell>
                        <Badge variant="outline">{t.category}</Badge>
                      </TableCell>
                      <TableCell className="whitespace-nowrap text-sm">{t.completed_at}</TableCell>
                      <TableCell className="text-sm">
                        {t.score !== null && t.score !== undefined ? t.score : "—"}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </Card>
        </TabsContent>
      </Tabs>

      {/* ---- チェック実行ダイアログ ---- */}
      <Dialog open={checkOpen} onOpenChange={setCheckOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>チェックを実行</DialogTitle>
            <DialogDescription>
              決定論的なルールベース判定です（AI による最終法的判断は行いません）。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="ck-type">チェック種別</Label>
              <Select
                value={checkForm.check_type}
                onValueChange={(v) => setCheckForm((f) => ({ ...f, check_type: v }))}
              >
                <SelectTrigger id="ck-type" aria-label="チェック種別">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(CHECK_TYPE_LABELS).map(([value, label]) => (
                    <SelectItem key={value} value={value}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="ck-subject">対象（必須）</Label>
              <Input
                id="ck-subject"
                value={checkForm.subject}
                onChange={(e) => setCheckForm((f) => ({ ...f, subject: e.target.value }))}
                placeholder="例: ◯◯工事 入札対応の事前確認"
              />
            </div>
            {(checkForm.check_type === "general" || checkForm.check_type === "bid_rigging") && (
              <div className="space-y-2">
                <Label htmlFor="ck-text">自由記述（契約文面・状況説明）</Label>
                <Textarea
                  id="ck-text"
                  value={checkForm.text}
                  onChange={(e) => setCheckForm((f) => ({ ...f, text: e.target.value }))}
                  rows={4}
                />
              </div>
            )}
            {checkForm.check_type === "bid_rigging" && (
              <div className="space-y-2 rounded-md border p-3 text-sm">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={checkForm.is_public_bid}
                    onChange={(e) => setCheckForm((f) => ({ ...f, is_public_bid: e.target.checked }))}
                  />
                  公共・民間入札に関連する
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={checkForm.contacted_competitors}
                    onChange={(e) =>
                      setCheckForm((f) => ({ ...f, contacted_competitors: e.target.checked }))
                    }
                  />
                  入札前に競合他社と接触した
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={checkForm.pre_bid_price_shared}
                    onChange={(e) =>
                      setCheckForm((f) => ({ ...f, pre_bid_price_shared: e.target.checked }))
                    }
                  />
                  入札前に価格情報を共有した
                </label>
              </div>
            )}
            {checkForm.check_type === "price_exchange" && (
              <div className="space-y-2 rounded-md border p-3 text-sm">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={checkForm.counterparty_is_competitor}
                    onChange={(e) =>
                      setCheckForm((f) => ({ ...f, counterparty_is_competitor: e.target.checked }))
                    }
                  />
                  相手方は競合他社であり、価格情報を交換した
                </label>
              </div>
            )}
            {checkForm.check_type === "jv_formation" && (
              <div className="space-y-2 rounded-md border p-3 text-sm">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={checkForm.is_competitor_jv}
                    onChange={(e) =>
                      setCheckForm((f) => ({ ...f, is_competitor_jv: e.target.checked }))
                    }
                  />
                  競合関係にある企業間の JV である
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={checkForm.scope_covers_pricing}
                    onChange={(e) =>
                      setCheckForm((f) => ({ ...f, scope_covers_pricing: e.target.checked }))
                    }
                  />
                  価格決定・数量調整を JV の業務範囲に含む
                </label>
              </div>
            )}
            {checkForm.check_type === "joint_research" && (
              <div className="space-y-2 rounded-md border p-3 text-sm">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={checkForm.with_competitor}
                    onChange={(e) =>
                      setCheckForm((f) => ({ ...f, with_competitor: e.target.checked }))
                    }
                  />
                  競合他社との共同研究開発である
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={checkForm.covers_pricing_or_output}
                    onChange={(e) =>
                      setCheckForm((f) => ({ ...f, covers_pricing_or_output: e.target.checked }))
                    }
                  />
                  価格・生産数量の調整に及ぶ
                </label>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCheckOpen(false)}>
              キャンセル
            </Button>
            <Button
              onClick={() => void runCheck()}
              disabled={!checkForm.subject.trim() || checkRunning}
            >
              {checkRunning && <Loader2 className="mr-1 h-4 w-4 animate-spin" aria-hidden="true" />}
              実行
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ---- 事前申請登録ダイアログ ---- */}
      <Dialog open={appOpen} onOpenChange={setAppOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>事前申請を登録</DialogTitle>
            <DialogDescription>登録直後は「申請中（submitted）」の状態になります。</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="ap-type">申請種別</Label>
              <Select
                value={appForm.application_type}
                onValueChange={(v) => setAppForm((f) => ({ ...f, application_type: v }))}
              >
                <SelectTrigger id="ap-type" aria-label="申請種別">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(APPLICATION_TYPE_LABELS).map(([value, label]) => (
                    <SelectItem key={value} value={value}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="ap-title">件名（必須）</Label>
              <Input
                id="ap-title"
                value={appForm.title}
                onChange={(e) => setAppForm((f) => ({ ...f, title: e.target.value }))}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="ap-counterparty">相手方（任意）</Label>
                <Input
                  id="ap-counterparty"
                  value={appForm.counterparty_name}
                  onChange={(e) => setAppForm((f) => ({ ...f, counterparty_name: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="ap-org">相手方組織（任意）</Label>
                <Input
                  id="ap-org"
                  value={appForm.counterparty_organization}
                  onChange={(e) =>
                    setAppForm((f) => ({ ...f, counterparty_organization: e.target.value }))
                  }
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="ap-amount">金額（円・接待/贈答/寄付の場合）</Label>
              <Input
                id="ap-amount"
                type="number"
                min={0}
                value={appForm.amount_jpy}
                onChange={(e) => setAppForm((f) => ({ ...f, amount_jpy: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="ap-purpose">目的（任意）</Label>
              <Textarea
                id="ap-purpose"
                value={appForm.purpose}
                onChange={(e) => setAppForm((f) => ({ ...f, purpose: e.target.value }))}
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAppOpen(false)}>
              キャンセル
            </Button>
            <Button onClick={() => void createApplication()} disabled={!appForm.title.trim() || appCreating}>
              {appCreating && <Loader2 className="mr-1 h-4 w-4 animate-spin" aria-hidden="true" />}
              登録
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ---- 承認・却下ダイアログ ---- */}
      <Dialog open={decisionTarget !== null} onOpenChange={(open) => !open && setDecisionTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>承認・却下</DialogTitle>
            <DialogDescription>
              {decisionTarget?.application_no} — {decisionTarget?.title}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="dec-note">コメント（任意）</Label>
            <Textarea
              id="dec-note"
              value={decisionNote}
              onChange={(e) => setDecisionNote(e.target.value)}
              rows={3}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDecisionTarget(null)}>
              閉じる
            </Button>
            <Button variant="destructive" onClick={() => void decide("rejected")} disabled={appBusy}>
              <XCircle className="mr-1 h-4 w-4" aria-hidden="true" />
              却下
            </Button>
            <Button onClick={() => void decide("approved")} disabled={appBusy}>
              <CheckCircle2 className="mr-1 h-4 w-4" aria-hidden="true" />
              承認
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ---- 実施記録ダイアログ ---- */}
      <Dialog open={completeTarget !== null} onOpenChange={(open) => !open && setCompleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>実施記録を登録</DialogTitle>
            <DialogDescription>
              {completeTarget?.application_no} — {completeTarget?.title}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="outcome-note">実施内容・議事メモ（必須）</Label>
            <Textarea
              id="outcome-note"
              value={outcomeNote}
              onChange={(e) => setOutcomeNote(e.target.value)}
              rows={4}
              placeholder="話題になった内容、参加者、結論等を記録してください。"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCompleteTarget(null)}>
              キャンセル
            </Button>
            <Button onClick={() => void complete()} disabled={!outcomeNote.trim() || appBusy}>
              {appBusy && <Loader2 className="mr-1 h-4 w-4 animate-spin" aria-hidden="true" />}
              記録する
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ---- 取下げダイアログ ---- */}
      <Dialog open={cancelTarget !== null} onOpenChange={(open) => !open && setCancelTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>事前申請を取下げ</DialogTitle>
            <DialogDescription>
              {cancelTarget?.application_no} — {cancelTarget?.title}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="cancel-reason">取下げ理由（必須）</Label>
            <Textarea
              id="cancel-reason"
              value={cancelReason}
              onChange={(e) => setCancelReason(e.target.value)}
              rows={2}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCancelTarget(null)}>
              戻る
            </Button>
            <Button variant="destructive" onClick={() => void cancel()} disabled={!cancelReason.trim() || appBusy}>
              {appBusy && <Loader2 className="mr-1 h-4 w-4 animate-spin" aria-hidden="true" />}
              取り下げる
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ---- 研修履歴登録ダイアログ ---- */}
      <Dialog open={trainingOpen} onOpenChange={setTrainingOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>研修履歴を登録</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="tr-title">研修名（必須）</Label>
              <Input
                id="tr-title"
                value={trainingForm.training_title}
                onChange={(e) =>
                  setTrainingForm((f) => ({ ...f, training_title: e.target.value }))
                }
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="tr-attendee">受講者（任意）</Label>
                <Input
                  id="tr-attendee"
                  value={trainingForm.attendee_name}
                  onChange={(e) =>
                    setTrainingForm((f) => ({ ...f, attendee_name: e.target.value }))
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="tr-category">分類</Label>
                <Select
                  value={trainingForm.category}
                  onValueChange={(v) => setTrainingForm((f) => ({ ...f, category: v }))}
                >
                  <SelectTrigger id="tr-category" aria-label="分類">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="antitrust">独占禁止法</SelectItem>
                    <SelectItem value="bribery">贈収賄防止</SelectItem>
                    <SelectItem value="general">一般コンプライアンス</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="tr-date">受講日（必須）</Label>
                <Input
                  id="tr-date"
                  type="date"
                  value={trainingForm.completed_at}
                  onChange={(e) =>
                    setTrainingForm((f) => ({ ...f, completed_at: e.target.value }))
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="tr-score">得点（任意）</Label>
                <Input
                  id="tr-score"
                  type="number"
                  min={0}
                  max={100}
                  value={trainingForm.score}
                  onChange={(e) => setTrainingForm((f) => ({ ...f, score: e.target.value }))}
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setTrainingOpen(false)}>
              キャンセル
            </Button>
            <Button
              onClick={() => void createTraining()}
              disabled={!trainingForm.training_title.trim() || !trainingForm.completed_at || trainingSaving}
            >
              {trainingSaving && <Loader2 className="mr-1 h-4 w-4 animate-spin" aria-hidden="true" />}
              登録
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
