"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowLeft,
  Copy,
  FileText,
  Gavel,
  RefreshCw,
  ShieldCheck,
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
import { Progress } from "@/components/ui/progress";
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
import { AiDisclaimerBanner } from "@/components/layout/ai-disclaimer-banner";
import { disputesExtApi } from "@/lib/api";
import type {
  DisputeArgumentPosition,
  DisputeChronologyEntry,
  DisputeClaimNotice,
  DisputeDelayEvent,
  DisputeDelaySummary,
  DisputeEvidenceScore,
  DisputeProceedingStage,
  DisputeSettlementCompareItem,
  DisputeSettlementOption,
  DisputeTimeBarAlert,
} from "@/lib/api/schemas";
import { formatCurrency } from "@/lib/utils/format-currency";

const CAUSE_LABELS: Record<string, string> = {
  owner_caused: "発注者起因",
  contractor_caused: "請負者起因",
  weather: "天候",
  third_party: "第三者起因",
  force_majeure: "不可抗力",
  design_change: "設計変更",
  other: "その他",
};

const SEVERITY_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  expired: "destructive",
  critical: "destructive",
  warning: "secondary",
  info: "outline",
  ok: "outline",
};

const SEVERITY_LABELS: Record<string, string> = {
  expired: "期限徒過",
  critical: "危険（30日以内）",
  warning: "注意（90日以内）",
  info: "情報（180日以内）",
  ok: "余裕あり",
};

const STAGE_LABELS: Record<string, string> = {
  negotiation: "交渉",
  mediation: "調停",
  arbitration_filed: "仲裁申立",
  arbitration_hearing: "仲裁審理",
  arbitration_award: "仲裁判断",
  lawsuit_filed: "訴訟提起",
  first_instance: "第一審",
  appeal: "控訴審",
  final_judgment: "確定判決",
  settled: "和解成立",
};

interface DisputeDetailPageProps {
  disputeId: string;
}

export default function DisputeDetailPage({ disputeId }: DisputeDetailPageProps) {
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);

  const [timeBar, setTimeBar] = useState<DisputeTimeBarAlert | null>(null);
  const [evidenceScore, setEvidenceScore] = useState<DisputeEvidenceScore | null>(null);
  const [chronology, setChronology] = useState<DisputeChronologyEntry[]>([]);
  const [delayEvents, setDelayEvents] = useState<DisputeDelayEvent[]>([]);
  const [delaySummary, setDelaySummary] = useState<DisputeDelaySummary | null>(null);
  const [argumentsList, setArgumentsList] = useState<DisputeArgumentPosition[]>([]);
  const [settlementOptions, setSettlementOptions] = useState<DisputeSettlementOption[]>([]);
  const [settlementCompare, setSettlementCompare] = useState<DisputeSettlementCompareItem[]>([]);
  const [stages, setStages] = useState<DisputeProceedingStage[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [tb, es, ch, de, ds, args, so, sc, st] = await Promise.all([
        disputesExtApi.timeBarStatus(disputeId),
        disputesExtApi.evidenceScore(disputeId),
        disputesExtApi.chronology(disputeId),
        disputesExtApi.listDelayEvents(disputeId),
        disputesExtApi.delaySummary(disputeId),
        disputesExtApi.listArguments(disputeId),
        disputesExtApi.listSettlementOptions(disputeId),
        disputesExtApi.compareSettlementOptions(disputeId),
        disputesExtApi.listStages(disputeId),
      ]);
      setTimeBar(tb);
      setEvidenceScore(es);
      setChronology(ch);
      setDelayEvents(de);
      setDelaySummary(ds);
      setArgumentsList(args);
      setSettlementOptions(so);
      setSettlementCompare(sc);
      setStages(st);
      setOffline(false);
    } catch {
      setOffline(true);
    } finally {
      setLoading(false);
    }
  }, [disputeId]);

  useEffect(() => {
    void load();
  }, [load]);

  // --- #97/#98 通知書生成・通知期限自動判定 ---------------------------------
  const [noticeOpen, setNoticeOpen] = useState(false);
  const [noticeResult, setNoticeResult] = useState<DisputeClaimNotice | null>(null);
  const [noticeForm, setNoticeForm] = useState({ sender_name: "", recipient_name: "", extra_note: "" });

  const generateNotice = async () => {
    if (!noticeForm.sender_name) return;
    try {
      const result = await disputesExtApi.generateClaimNotice(disputeId, {
        sender_name: noticeForm.sender_name,
        recipient_name: noticeForm.recipient_name || undefined,
        extra_note: noticeForm.extra_note || undefined,
      });
      setNoticeResult(result);
    } catch {
      setOffline(true);
    }
  };

  const [judgeOpen, setJudgeOpen] = useState(false);
  const [judgeForm, setJudgeForm] = useState({ event_date: "", override_days: "", apply: false });
  const judgeNoticeDeadline = async () => {
    if (!judgeForm.event_date) return;
    try {
      await disputesExtApi.autoJudgeNoticeDeadline(disputeId, {
        event_date: judgeForm.event_date,
        override_days: judgeForm.override_days ? Number(judgeForm.override_days) : undefined,
        apply: judgeForm.apply,
      });
      setJudgeOpen(false);
      await load();
    } catch {
      setOffline(true);
    }
  };

  // --- #100〜#104 遅延事象 ---------------------------------------------------
  const [delayOpen, setDelayOpen] = useState(false);
  const [delayForm, setDelayForm] = useState({
    cause_category: "owner_caused",
    title: "",
    occurred_from: "",
    occurred_to: "",
    delay_days: "0",
    additional_cost_jpy: "",
    eot_days_requested: "",
  });
  const addDelayEvent = async () => {
    if (!delayForm.title || !delayForm.occurred_from) return;
    try {
      await disputesExtApi.addDelayEvent(disputeId, {
        cause_category: delayForm.cause_category as DisputeDelayEvent["cause_category"],
        title: delayForm.title,
        occurred_from: delayForm.occurred_from,
        occurred_to: delayForm.occurred_to || undefined,
        delay_days: Number(delayForm.delay_days || 0),
        additional_cost_jpy: delayForm.additional_cost_jpy
          ? Number(delayForm.additional_cost_jpy)
          : undefined,
        eot_days_requested: delayForm.eot_days_requested
          ? Number(delayForm.eot_days_requested)
          : undefined,
      });
      setDelayOpen(false);
      setDelayForm({
        cause_category: "owner_caused",
        title: "",
        occurred_from: "",
        occurred_to: "",
        delay_days: "0",
        additional_cost_jpy: "",
        eot_days_requested: "",
      });
      await load();
    } catch {
      setOffline(true);
    }
  };

  const decideEot = async (
    delayEventId: string | number,
    eotStatus: "approved" | "partial" | "rejected",
  ) => {
    const daysStr = eotStatus === "rejected" ? "0" : window.prompt("認容日数を入力してください", "0");
    if (daysStr === null) return;
    const trimmed = daysStr.trim();
    const days = trimmed === "" ? 0 : Number(trimmed);
    if (!Number.isInteger(days) || days < 0) {
      window.alert("認容日数は 0 以上の整数を入力してください。");
      return;
    }
    try {
      await disputesExtApi.updateDelayEventEot(delayEventId, {
        eot_status: eotStatus,
        eot_days_granted: days,
      });
      await load();
    } catch {
      setOffline(true);
    }
  };

  // --- #109 主張・反論マトリクス --------------------------------------------
  const [argOpen, setArgOpen] = useState(false);
  const [argForm, setArgForm] = useState({
    issue_no: "1",
    issue_title: "",
    party: "ours",
    stance: "claim",
    content: "",
  });
  const addArgument = async () => {
    if (!argForm.issue_title || !argForm.content) return;
    try {
      await disputesExtApi.addArgument(disputeId, {
        issue_no: Number(argForm.issue_no || 1),
        issue_title: argForm.issue_title,
        party: argForm.party as DisputeArgumentPosition["party"],
        stance: argForm.stance as DisputeArgumentPosition["stance"],
        content: argForm.content,
      });
      setArgOpen(false);
      setArgForm({ issue_no: "1", issue_title: "", party: "ours", stance: "claim", content: "" });
      await load();
    } catch {
      setOffline(true);
    }
  };

  // --- #110 和解案比較 --------------------------------------------------------
  const [settlementOpen, setSettlementOpen] = useState(false);
  const [settlementForm, setSettlementForm] = useState({
    option_no: "1",
    title: "",
    settlement_amount_jpy: "",
    probability_score: "",
  });
  const addSettlementOption = async () => {
    if (!settlementForm.title) return;
    try {
      await disputesExtApi.addSettlementOption(disputeId, {
        option_no: Number(settlementForm.option_no || 1),
        title: settlementForm.title,
        settlement_amount_jpy: settlementForm.settlement_amount_jpy
          ? Number(settlementForm.settlement_amount_jpy)
          : undefined,
        probability_score: settlementForm.probability_score
          ? Number(settlementForm.probability_score)
          : undefined,
      });
      setSettlementOpen(false);
      setSettlementForm({ option_no: "1", title: "", settlement_amount_jpy: "", probability_score: "" });
      await load();
    } catch {
      setOffline(true);
    }
  };

  const updateSettlementStatus = async (
    optionId: string | number,
    status: DisputeSettlementOption["status"],
  ) => {
    try {
      await disputesExtApi.updateSettlementOption(optionId, { status });
      await load();
    } catch {
      setOffline(true);
    }
  };

  // --- #111 訴訟・ADR ステージ管理 --------------------------------------------
  const [stageOpen, setStageOpen] = useState(false);
  const [stageForm, setStageForm] = useState({ stage: "negotiation", started_at: "" });
  const addStage = async () => {
    if (!stageForm.started_at) return;
    try {
      await disputesExtApi.addStage(disputeId, {
        stage: stageForm.stage as DisputeProceedingStage["stage"],
        started_at: stageForm.started_at,
      });
      setStageOpen(false);
      setStageForm({ stage: "negotiation", started_at: "" });
      await load();
    } catch {
      setOffline(true);
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Button asChild variant="ghost" size="sm" className="-ml-2 mb-1">
            <Link href="/disputes">
              <ArrowLeft className="mr-1 h-4 w-4" aria-hidden="true" />
              紛争・クレーム一覧へ戻る
            </Link>
          </Button>
          <h1 className="text-2xl font-bold text-foreground">紛争・クレーム詳細管理</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            案件 ID: {disputeId} — 遅延事象・証拠充足度・主張反論・和解案・訴訟ステージを一元管理します
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={() => setJudgeOpen(true)}>
            通知期限自動判定
          </Button>
          <Button variant="outline" size="sm" onClick={() => setNoticeOpen(true)}>
            <FileText className="mr-1 h-4 w-4" aria-hidden="true" />
            通知書生成
          </Button>
          <Button variant="ghost" size="sm" onClick={() => void load()} disabled={loading}>
            <RefreshCw className={`mr-1 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            更新
          </Button>
        </div>
      </header>

      <AiDisclaimerBanner variant="inline" />

      {offline && (
        <Badge variant="outline" className="border-amber-400 bg-amber-50 text-amber-800 dark:bg-amber-950">
          データ取得に失敗しました（オフラインまたは未認証の可能性があります）
        </Badge>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardContent className="flex items-center gap-3 pt-4">
            <AlertTriangle className="h-8 w-8 text-destructive" aria-hidden="true" />
            <div>
              <div className="flex items-center gap-2">
                <Badge variant={SEVERITY_VARIANT[timeBar?.severity ?? "ok"] ?? "outline"}>
                  {SEVERITY_LABELS[timeBar?.severity ?? "ok"] ?? timeBar?.severity ?? "—"}
                </Badge>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                消滅時効: {timeBar?.statute_days_remaining ?? "—"} 日 / 通知期限:{" "}
                {timeBar?.notice_days_remaining ?? "—"} 日
              </p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 pt-4">
            <ShieldCheck className="h-8 w-8 text-emerald-600" aria-hidden="true" />
            <div className="w-full">
              <p className="text-sm font-medium">証拠充足度スコア: {evidenceScore?.score ?? 0} / 100</p>
              <Progress value={evidenceScore?.score ?? 0} className="mt-1" />
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="delay">
        <TabsList className="flex-wrap">
          <TabsTrigger value="delay">遅延事象</TabsTrigger>
          <TabsTrigger value="evidence">証拠・時系列</TabsTrigger>
          <TabsTrigger value="arguments">主張・反論</TabsTrigger>
          <TabsTrigger value="settlement">和解案比較</TabsTrigger>
          <TabsTrigger value="stages">訴訟・ADR ステージ</TabsTrigger>
        </TabsList>

        {/* #100〜#104 遅延事象 */}
        <TabsContent value="delay" className="space-y-4">
          {delaySummary && (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Card>
                <CardContent className="pt-4 text-sm">
                  <p className="text-muted-foreground">総遅延日数</p>
                  <p className="text-xl font-bold">{delaySummary.total_delay_days} 日</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-4 text-sm">
                  <p className="text-muted-foreground">追加費用積上げ</p>
                  <p className="text-xl font-bold">
                    {formatCurrency(delaySummary.total_additional_cost_jpy)}
                  </p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-4 text-sm">
                  <p className="text-muted-foreground">損害額</p>
                  <p className="text-xl font-bold">
                    {formatCurrency(delaySummary.total_damage_amount_jpy)}
                  </p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-4 text-sm">
                  <p className="text-muted-foreground">EOT 認容日数</p>
                  <p className="text-xl font-bold">{delaySummary.total_eot_days_granted} 日</p>
                </CardContent>
              </Card>
            </div>
          )}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0">
              <CardTitle>遅延事象台帳</CardTitle>
              <Button size="sm" onClick={() => setDelayOpen(true)}>
                遅延事象を登録
              </Button>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>原因</TableHead>
                    <TableHead>件名</TableHead>
                    <TableHead>期間</TableHead>
                    <TableHead className="text-right">遅延日数</TableHead>
                    <TableHead className="text-right">追加費用</TableHead>
                    <TableHead>EOT</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {delayEvents.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7} className="py-8 text-center text-sm text-muted-foreground">
                        遅延事象が登録されていません
                      </TableCell>
                    </TableRow>
                  ) : (
                    delayEvents.map((ev) => (
                      <TableRow key={String(ev.id)}>
                        <TableCell className="text-sm">
                          {CAUSE_LABELS[ev.cause_category] ?? ev.cause_category}
                        </TableCell>
                        <TableCell className="max-w-[200px] truncate text-sm">{ev.title}</TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {ev.occurred_from} 〜 {ev.occurred_to ?? "継続中"}
                        </TableCell>
                        <TableCell className="text-right text-sm">{ev.delay_days}</TableCell>
                        <TableCell className="text-right text-sm">
                          {ev.additional_cost_jpy != null ? formatCurrency(ev.additional_cost_jpy) : "—"}
                        </TableCell>
                        <TableCell>
                          <Badge variant={ev.eot_status === "pending" ? "outline" : "secondary"}>
                            {ev.eot_status}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          {ev.eot_status === "pending" && (
                            <div className="flex gap-1">
                              <Button size="sm" variant="ghost" onClick={() => void decideEot(ev.id, "approved")}>
                                認容
                              </Button>
                              <Button size="sm" variant="ghost" onClick={() => void decideEot(ev.id, "partial")}>
                                一部
                              </Button>
                              <Button size="sm" variant="ghost" onClick={() => void decideEot(ev.id, "rejected")}>
                                却下
                              </Button>
                            </div>
                          )}
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* #105〜#108 証拠充足度・Chronology */}
        <TabsContent value="evidence" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>証拠充足度・不足検知（ルールベース・AI 不使用）</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <p>必須証拠: {evidenceScore?.required_types.join("、") || "—"}</p>
              <p>登録済み: {evidenceScore?.present_types.join("、") || "—"}</p>
              {evidenceScore && evidenceScore.recommendations.length > 0 && (
                <ul className="list-disc space-y-1 pl-5 text-amber-700 dark:text-amber-400">
                  {evidenceScore.recommendations.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Claim Chronology（写真・議事録・メール・遅延事象の時系列統合）</CardTitle>
            </CardHeader>
            <CardContent>
              {chronology.length === 0 ? (
                <p className="text-sm text-muted-foreground">時系列データがありません</p>
              ) : (
                <ol className="space-y-2 border-l pl-4">
                  {chronology.map((entry, i) => (
                    <li key={i} className="relative text-sm">
                      <span className="absolute -left-[21px] top-1.5 h-2 w-2 rounded-full bg-primary" />
                      <p className="font-medium">
                        {entry.title}{" "}
                        {entry.estimated && (
                          <Badge variant="outline" className="ml-1 text-[10px]">推定日</Badge>
                        )}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {new Date(entry.occurred_at).toLocaleString("ja-JP")} / {entry.source_type}
                      </p>
                      {entry.description && <p className="mt-0.5">{entry.description}</p>}
                    </li>
                  ))}
                </ol>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* #109 主張・反論マトリクス */}
        <TabsContent value="arguments" className="space-y-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0">
              <CardTitle>主張・反論マトリクス</CardTitle>
              <Button size="sm" onClick={() => setArgOpen(true)}>
                主張・反論を追加
              </Button>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-16">争点</TableHead>
                    <TableHead>争点名</TableHead>
                    <TableHead className="w-24">当事者</TableHead>
                    <TableHead className="w-28">立場</TableHead>
                    <TableHead>内容</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {argumentsList.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={5} className="py-8 text-center text-sm text-muted-foreground">
                        主張・反論が登録されていません
                      </TableCell>
                    </TableRow>
                  ) : (
                    argumentsList.map((a) => (
                      <TableRow key={String(a.id)}>
                        <TableCell className="text-sm">{a.issue_no}</TableCell>
                        <TableCell className="text-sm">{a.issue_title}</TableCell>
                        <TableCell className="text-sm">{a.party === "ours" ? "自社" : "相手方"}</TableCell>
                        <TableCell className="text-sm">
                          {a.stance === "claim" ? "主張" : a.stance === "rebuttal" ? "反論" : "再反論"}
                        </TableCell>
                        <TableCell className="max-w-[320px] text-sm">{a.content}</TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* #110 和解案比較 */}
        <TabsContent value="settlement" className="space-y-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0">
              <CardTitle>和解案比較（期待値順・最有力案を推奨表示）</CardTitle>
              <Button size="sm" onClick={() => setSettlementOpen(true)}>
                和解案を追加
              </Button>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>案</TableHead>
                    <TableHead className="text-right">和解金額</TableHead>
                    <TableHead className="text-right">確度</TableHead>
                    <TableHead className="text-right">期待値</TableHead>
                    <TableHead>状態</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {settlementCompare.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="py-8 text-center text-sm text-muted-foreground">
                        和解案が登録されていません
                      </TableCell>
                    </TableRow>
                  ) : (
                    settlementCompare.map((o) => (
                      <TableRow key={String(o.id)} className={o.recommended ? "bg-emerald-50 dark:bg-emerald-950/30" : ""}>
                        <TableCell className="text-sm">
                          {o.title} {o.recommended && <Badge className="ml-1">推奨</Badge>}
                        </TableCell>
                        <TableCell className="text-right text-sm">
                          {o.settlement_amount_jpy != null ? formatCurrency(o.settlement_amount_jpy) : "—"}
                        </TableCell>
                        <TableCell className="text-right text-sm">
                          {o.probability_score != null ? `${o.probability_score}%` : "—"}
                        </TableCell>
                        <TableCell className="text-right text-sm font-medium">
                          {o.expected_value_jpy != null ? formatCurrency(o.expected_value_jpy) : "—"}
                        </TableCell>
                        <TableCell>
                          <Select
                            value={o.status}
                            onValueChange={(v) =>
                              void updateSettlementStatus(o.id, v as DisputeSettlementOption["status"])
                            }
                          >
                            <SelectTrigger className="h-8 w-28">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="draft">検討中</SelectItem>
                              <SelectItem value="proposed">提案済み</SelectItem>
                              <SelectItem value="accepted">合意</SelectItem>
                              <SelectItem value="rejected">拒否</SelectItem>
                              <SelectItem value="withdrawn">撤回</SelectItem>
                            </SelectContent>
                          </Select>
                        </TableCell>
                        <TableCell />
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
              <p className="mt-2 text-xs text-muted-foreground">
                登録済み案件数: {settlementOptions.length}
              </p>
            </CardContent>
          </Card>
        </TabsContent>

        {/* #111 訴訟・ADR ステージ管理 */}
        <TabsContent value="stages" className="space-y-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0">
              <CardTitle>
                <Gavel className="mr-1 inline h-4 w-4" aria-hidden="true" />
                訴訟・ADR ステージ履歴
              </CardTitle>
              <Button size="sm" onClick={() => setStageOpen(true)}>
                ステージを追加
              </Button>
            </CardHeader>
            <CardContent>
              {stages.length === 0 ? (
                <p className="text-sm text-muted-foreground">ステージが登録されていません</p>
              ) : (
                <ol className="space-y-2 border-l pl-4">
                  {stages.map((s) => (
                    <li key={String(s.id)} className="relative text-sm">
                      <span
                        className={`absolute -left-[21px] top-1.5 h-2 w-2 rounded-full ${
                          s.status === "active" ? "bg-primary" : "bg-muted-foreground"
                        }`}
                      />
                      <p className="font-medium">
                        {STAGE_LABELS[s.stage] ?? s.stage}{" "}
                        <Badge variant={s.status === "active" ? "default" : "outline"} className="ml-1">
                          {s.status === "active" ? "進行中" : "完了"}
                        </Badge>
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {s.started_at} 〜 {s.ended_at ?? "継続中"}
                      </p>
                    </li>
                  ))}
                </ol>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* 通知書生成ダイアログ (#97) */}
      <Dialog open={noticeOpen} onOpenChange={(v) => { setNoticeOpen(v); if (!v) setNoticeResult(null); }}>
        <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>クレーム通知書生成（決定論的テンプレート処理・AI 不使用）</DialogTitle>
          </DialogHeader>
          {!noticeResult ? (
            <div className="grid gap-3">
              <div>
                <Label htmlFor="notice-sender-name">差出人名 *</Label>
                <Input
                  id="notice-sender-name"
                  value={noticeForm.sender_name}
                  onChange={(e) => setNoticeForm({ ...noticeForm, sender_name: e.target.value })}
                />
              </div>
              <div>
                <Label htmlFor="notice-recipient-name">宛先（未入力時は相手方名を使用）</Label>
                <Input
                  id="notice-recipient-name"
                  value={noticeForm.recipient_name}
                  onChange={(e) => setNoticeForm({ ...noticeForm, recipient_name: e.target.value })}
                />
              </div>
              <div>
                <Label htmlFor="notice-extra-note">備考</Label>
                <Textarea
                  id="notice-extra-note"
                  value={noticeForm.extra_note}
                  onChange={(e) => setNoticeForm({ ...noticeForm, extra_note: e.target.value })}
                />
              </div>
            </div>
          ) : (
            <div className="space-y-2">
              <Textarea readOnly value={noticeResult.formatted_text} className="h-72 font-mono text-xs" />
              <Button
                variant="outline"
                size="sm"
                onClick={() => void navigator.clipboard.writeText(noticeResult.formatted_text)}
              >
                <Copy className="mr-1 h-4 w-4" aria-hidden="true" />
                コピー
              </Button>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setNoticeOpen(false)}>
              閉じる
            </Button>
            {!noticeResult && (
              <Button onClick={() => void generateNotice()} disabled={!noticeForm.sender_name}>
                生成
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 通知期限自動判定ダイアログ (#98) */}
      <Dialog open={judgeOpen} onOpenChange={setJudgeOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>通知期限自動判定（決定論的既定日数テーブル）</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3">
            <div>
              <Label htmlFor="judge-event-date">起算日（事象発生日）*</Label>
              <Input
                id="judge-event-date"
                type="date"
                value={judgeForm.event_date}
                onChange={(e) => setJudgeForm({ ...judgeForm, event_date: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="judge-override-days">通知期間（日数・未入力なら種別の既定値）</Label>
              <Input
                id="judge-override-days"
                type="number"
                value={judgeForm.override_days}
                onChange={(e) => setJudgeForm({ ...judgeForm, override_days: e.target.value })}
              />
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={judgeForm.apply}
                onChange={(e) => setJudgeForm({ ...judgeForm, apply: e.target.checked })}
              />
              算定結果を案件の通知期限へ反映する
            </label>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setJudgeOpen(false)}>
              キャンセル
            </Button>
            <Button onClick={() => void judgeNoticeDeadline()} disabled={!judgeForm.event_date}>
              判定
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 遅延事象登録ダイアログ (#100〜#104) */}
      <Dialog open={delayOpen} onOpenChange={setDelayOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>遅延事象を登録</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3">
            <div>
              <Label htmlFor="delay-cause-category">原因分類</Label>
              <Select
                value={delayForm.cause_category}
                onValueChange={(v) => setDelayForm({ ...delayForm, cause_category: v })}
              >
                <SelectTrigger id="delay-cause-category"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {Object.entries(CAUSE_LABELS).map(([v, l]) => (
                    <SelectItem key={v} value={v}>{l}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="delay-title">件名 *</Label>
              <Input
                id="delay-title"
                value={delayForm.title}
                onChange={(e) => setDelayForm({ ...delayForm, title: e.target.value })}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="delay-occurred-from">開始日 *</Label>
                <Input
                  id="delay-occurred-from"
                  type="date"
                  value={delayForm.occurred_from}
                  onChange={(e) => setDelayForm({ ...delayForm, occurred_from: e.target.value })}
                />
              </div>
              <div>
                <Label htmlFor="delay-occurred-to">終了日</Label>
                <Input
                  id="delay-occurred-to"
                  type="date"
                  value={delayForm.occurred_to}
                  onChange={(e) => setDelayForm({ ...delayForm, occurred_to: e.target.value })}
                />
              </div>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <Label htmlFor="delay-days">遅延日数</Label>
                <Input
                  id="delay-days"
                  type="number"
                  value={delayForm.delay_days}
                  onChange={(e) => setDelayForm({ ...delayForm, delay_days: e.target.value })}
                />
              </div>
              <div>
                <Label htmlFor="delay-additional-cost">追加費用（円）</Label>
                <Input
                  id="delay-additional-cost"
                  type="number"
                  value={delayForm.additional_cost_jpy}
                  onChange={(e) => setDelayForm({ ...delayForm, additional_cost_jpy: e.target.value })}
                />
              </div>
              <div>
                <Label htmlFor="delay-eot-days-requested">EOT 申請日数</Label>
                <Input
                  id="delay-eot-days-requested"
                  type="number"
                  value={delayForm.eot_days_requested}
                  onChange={(e) => setDelayForm({ ...delayForm, eot_days_requested: e.target.value })}
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDelayOpen(false)}>
              キャンセル
            </Button>
            <Button onClick={() => void addDelayEvent()} disabled={!delayForm.title || !delayForm.occurred_from}>
              登録
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 主張・反論登録ダイアログ (#109) */}
      <Dialog open={argOpen} onOpenChange={setArgOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>主張・反論を追加</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3">
            <div className="grid grid-cols-3 gap-3">
              <div>
                <Label htmlFor="arg-issue-no">争点番号</Label>
                <Input
                  id="arg-issue-no"
                  type="number"
                  value={argForm.issue_no}
                  onChange={(e) => setArgForm({ ...argForm, issue_no: e.target.value })}
                />
              </div>
              <div>
                <Label htmlFor="arg-party">当事者</Label>
                <Select value={argForm.party} onValueChange={(v) => setArgForm({ ...argForm, party: v })}>
                  <SelectTrigger id="arg-party"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="ours">自社</SelectItem>
                    <SelectItem value="counterparty">相手方</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label htmlFor="arg-stance">立場</Label>
                <Select value={argForm.stance} onValueChange={(v) => setArgForm({ ...argForm, stance: v })}>
                  <SelectTrigger id="arg-stance"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="claim">主張</SelectItem>
                    <SelectItem value="rebuttal">反論</SelectItem>
                    <SelectItem value="counter_rebuttal">再反論</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div>
              <Label htmlFor="arg-issue-title">争点名 *</Label>
              <Input
                id="arg-issue-title"
                value={argForm.issue_title}
                onChange={(e) => setArgForm({ ...argForm, issue_title: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="arg-content">内容 *</Label>
              <Textarea
                id="arg-content"
                value={argForm.content}
                onChange={(e) => setArgForm({ ...argForm, content: e.target.value })}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setArgOpen(false)}>
              キャンセル
            </Button>
            <Button onClick={() => void addArgument()} disabled={!argForm.issue_title || !argForm.content}>
              追加
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 和解案登録ダイアログ (#110) */}
      <Dialog open={settlementOpen} onOpenChange={setSettlementOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>和解案を追加</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3">
            <div>
              <Label htmlFor="settlement-title">案の名称 *</Label>
              <Input
                id="settlement-title"
                value={settlementForm.title}
                onChange={(e) => setSettlementForm({ ...settlementForm, title: e.target.value })}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="settlement-amount">和解金額（円）</Label>
                <Input
                  id="settlement-amount"
                  type="number"
                  value={settlementForm.settlement_amount_jpy}
                  onChange={(e) =>
                    setSettlementForm({ ...settlementForm, settlement_amount_jpy: e.target.value })
                  }
                />
              </div>
              <div>
                <Label htmlFor="settlement-probability">成立確度（%）</Label>
                <Input
                  id="settlement-probability"
                  type="number"
                  min={0}
                  max={100}
                  value={settlementForm.probability_score}
                  onChange={(e) =>
                    setSettlementForm({ ...settlementForm, probability_score: e.target.value })
                  }
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSettlementOpen(false)}>
              キャンセル
            </Button>
            <Button onClick={() => void addSettlementOption()} disabled={!settlementForm.title}>
              追加
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ステージ追加ダイアログ (#111) */}
      <Dialog open={stageOpen} onOpenChange={setStageOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>訴訟・ADR ステージを追加</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3">
            <div>
              <Label htmlFor="stage-name">ステージ</Label>
              <Select value={stageForm.stage} onValueChange={(v) => setStageForm({ ...stageForm, stage: v })}>
                <SelectTrigger id="stage-name"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {Object.entries(STAGE_LABELS).map(([v, l]) => (
                    <SelectItem key={v} value={v}>{l}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="stage-started-at">開始日 *</Label>
              <Input
                id="stage-started-at"
                type="date"
                value={stageForm.started_at}
                onChange={(e) => setStageForm({ ...stageForm, started_at: e.target.value })}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setStageOpen(false)}>
              キャンセル
            </Button>
            <Button onClick={() => void addStage()} disabled={!stageForm.started_at}>
              追加
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
