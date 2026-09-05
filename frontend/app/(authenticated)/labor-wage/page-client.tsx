"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  BadgeJapaneseYen,
  CheckCircle2,
  Loader2,
  MessageSquareText,
  Plus,
  RefreshCw,
  Scale,
  Send,
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
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Textarea } from "@/components/ui/textarea";
import { laborWageApi, priceConsultationApi } from "@/lib/api";
import type {
  LaborWageDiscrepancy,
  LaborWageStandard,
  PriceConsultationLog,
} from "@/lib/api/schemas";

const WORK_TYPE_LABELS: Record<string, string> = {
  土木: "土木",
  "とび・土工": "とび・土工",
  舗装: "舗装",
  解体: "解体",
  鉄筋: "鉄筋",
  コンクリート: "コンクリート",
  その他: "その他",
};

const SEVERITY_LABELS: Record<string, string> = {
  none: "—",
  watch: "注視",
  warning: "要確認",
  critical: "深刻",
};

const SEVERITY_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  none: "outline",
  watch: "secondary",
  warning: "destructive",
  critical: "destructive",
};

const DIRECTION_LABELS: Record<string, string> = {
  from_subcontractor: "下請→元請（引上げ申出）",
  to_subcontractor: "元請→下請（価格確認）",
};

const CONSULTATION_STATUS_LABELS: Record<string, string> = {
  open: "回答待ち",
  responded: "回答済",
  cancelled: "取下げ",
};

const CONSULTATION_STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  open: "outline",
  responded: "default",
  cancelled: "secondary",
};

const PREFECTURES = [
  "全国",
  "北海道",
  "青森県",
  "岩手県",
  "宮城県",
  "秋田県",
  "山形県",
  "福島県",
  "茨城県",
  "栃木県",
  "群馬県",
  "埼玉県",
  "千葉県",
  "東京都",
  "神奈川県",
  "新潟県",
  "富山県",
  "石川県",
  "福井県",
  "山梨県",
  "長野県",
  "岐阜県",
  "静岡県",
  "愛知県",
  "三重県",
  "滋賀県",
  "京都府",
  "大阪府",
  "兵庫県",
  "奈良県",
  "和歌山県",
  "鳥取県",
  "島根県",
  "岡山県",
  "広島県",
  "山口県",
  "徳島県",
  "香川県",
  "愛媛県",
  "高知県",
  "福岡県",
  "佐賀県",
  "長崎県",
  "熊本県",
  "大分県",
  "宮崎県",
  "鹿児島県",
  "沖縄県",
];

export default function LaborWagePage() {
  const [standards, setStandards] = useState<LaborWageStandard[]>([]);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [workTypeFilter, setWorkTypeFilter] = useState("all");
  const [prefectureFilter, setPrefectureFilter] = useState("all");

  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    work_type: "土木",
    prefecture: "全国",
    amount_jpy: "",
    effective_from: "",
    effective_to: "",
    source_ref: "",
  });

  // 乖離率判定
  const [discrepancyForm, setDiscrepancyForm] = useState({
    work_type: "土木",
    prefecture: "全国",
    quote_day_jpy: "",
  });
  const [discrepancyResult, setDiscrepancyResult] =
    useState<LaborWageDiscrepancy | null>(null);
  const [checking, setChecking] = useState(false);

  // 価格協議・見積変更監視（#23/#24）
  const [consultations, setConsultations] = useState<PriceConsultationLog[]>([]);
  const [consultationsLoading, setConsultationsLoading] = useState(true);
  const [consultationStatusFilter, setConsultationStatusFilter] = useState("all");
  const [consultOpen, setConsultOpen] = useState(false);
  const [consultCreating, setConsultCreating] = useState(false);
  const [consultForm, setConsultForm] = useState({
    direction: "from_subcontractor",
    work_type: "土木",
    prefecture: "全国",
    quote_day_jpy: "",
    summary: "",
    request_detail: "",
  });
  const [respondTarget, setRespondTarget] = useState<PriceConsultationLog | null>(null);
  const [respondText, setRespondText] = useState("");
  const [cancelTarget, setCancelTarget] = useState<PriceConsultationLog | null>(null);
  const [cancelReason, setCancelReason] = useState("");
  const [consultRunning, setConsultRunning] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await laborWageApi.standards({ page: 1, size: 200 });
      setStandards(result.items);
      setOffline(false);
    } catch {
      setStandards([]);
      setOffline(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // 価格協議ログ（#23/#24）の読み込み
  const loadConsultations = useCallback(async () => {
    setConsultationsLoading(true);
    try {
      const result = await priceConsultationApi.list({ page: 1, size: 100 });
      setConsultations(result.items);
    } catch {
      setConsultations([]);
    } finally {
      setConsultationsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadConsultations();
  }, [loadConsultations]);

  const filteredConsultations = useMemo(
    () =>
      consultationStatusFilter === "all"
        ? consultations
        : consultations.filter((c) => c.status === consultationStatusFilter),
    [consultations, consultationStatusFilter]
  );

  const createConsultation = async () => {
    if (!consultForm.summary.trim() || consultCreating) return;
    setConsultCreating(true);
    setActionError(null);
    try {
      await priceConsultationApi.create({
        direction: consultForm.direction,
        work_type: consultForm.work_type,
        prefecture: consultForm.prefecture === "全国" ? null : consultForm.prefecture,
        quote_day_jpy: consultForm.quote_day_jpy ? Number(consultForm.quote_day_jpy) : null,
        summary: consultForm.summary.trim(),
        request_detail: consultForm.request_detail || null,
      });
      setConsultOpen(false);
      setConsultForm({
        direction: "from_subcontractor",
        work_type: "土木",
        prefecture: "全国",
        quote_day_jpy: "",
        summary: "",
        request_detail: "",
      });
      await loadConsultations();
    } catch (err) {
      setActionError(
        err instanceof Error ? `協議申出に失敗しました: ${err.message}` : "協議申出に失敗しました。"
      );
    } finally {
      setConsultCreating(false);
    }
  };

  const respondConsultation = async () => {
    if (!respondTarget || !respondText.trim() || consultRunning) return;
    setConsultRunning(true);
    setActionError(null);
    try {
      await priceConsultationApi.respond(respondTarget.id, {
        response_summary: respondText.trim(),
      });
      setRespondTarget(null);
      setRespondText("");
      await loadConsultations();
    } catch (err) {
      setActionError(
        err instanceof Error ? `回答に失敗しました: ${err.message}` : "回答に失敗しました。"
      );
    } finally {
      setConsultRunning(false);
    }
  };

  const cancelConsultation = async () => {
    if (!cancelTarget || !cancelReason.trim() || consultRunning) return;
    setConsultRunning(true);
    setActionError(null);
    try {
      await priceConsultationApi.cancel(cancelTarget.id, { reason: cancelReason.trim() });
      setCancelTarget(null);
      setCancelReason("");
      await loadConsultations();
    } catch (err) {
      setActionError(
        err instanceof Error ? `取下げに失敗しました: ${err.message}` : "取下げに失敗しました。"
      );
    } finally {
      setConsultRunning(false);
    }
  };

  const filtered = useMemo(
    () =>
      standards.filter((s) => {
        if (workTypeFilter !== "all" && s.work_type !== workTypeFilter) return false;
        if (prefectureFilter !== "all" && s.prefecture !== prefectureFilter) return false;
        return true;
      }),
    [standards, workTypeFilter, prefectureFilter]
  );

  const formatYen = (value: number) => `${value.toLocaleString("ja-JP")} 円`;

  const createStandard = async () => {
    if (!form.amount_jpy || !form.effective_from || creating) return;
    setCreating(true);
    setActionError(null);
    try {
      const created = await laborWageApi.createStandard({
        work_type: form.work_type,
        amount_jpy: Number(form.amount_jpy),
        prefecture: form.prefecture || null,
        effective_from: form.effective_from,
        effective_to: form.effective_to || null,
        source_ref: form.source_ref || null,
      });
      setStandards((prev) => [...prev, created]);
      setCreateOpen(false);
      setForm({
        work_type: "土木",
        prefecture: "全国",
        amount_jpy: "",
        effective_from: "",
        effective_to: "",
        source_ref: "",
      });
    } catch (err) {
      setActionError(
        err instanceof Error ? `登録に失敗しました: ${err.message}` : "登録に失敗しました。"
      );
    } finally {
      setCreating(false);
    }
  };

  const runDiscrepancy = async () => {
    const amount = Number(discrepancyForm.quote_day_jpy);
    if (!Number.isFinite(amount) || amount <= 0 || checking) return;
    setChecking(true);
    setActionError(null);
    setDiscrepancyResult(null);
    try {
      const result = await laborWageApi.discrepancy({
        work_type: discrepancyForm.work_type,
        quote_day_jpy: amount,
        prefecture: discrepancyForm.prefecture === "全国" ? null : discrepancyForm.prefecture,
      });
      setDiscrepancyResult(result);
    } catch (err) {
      setActionError(
        err instanceof Error
          ? `乖離率判定に失敗しました（基準値が未登録の可能性があります）: ${err.message}`
          : "乖離率判定に失敗しました。"
      );
    } finally {
      setChecking(false);
    }
  };

  const effectiveLabel = (s: LaborWageStandard) =>
    s.effective_to ? `${s.effective_from} 〜 ${s.effective_to}` : `${s.effective_from} 〜（現行）`;

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">労務費基準</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            工種 × 都道府県の労務費基準値を管理し、見積単価の乖離率を判定します（更新型 Compliance Engine）
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)} className="gap-2">
          <Plus className="h-4 w-4" aria-hidden="true" />
          基準値を登録
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

      {/* 乖離率判定ツール */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Scale className="h-4 w-4 text-primary" aria-hidden="true" />
            見積単価の乖離率判定（#20）・ダンピング警告（#21）
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-end gap-3">
            <div className="space-y-2">
              <Label htmlFor="disc-work">工種</Label>
              <Select
                value={discrepancyForm.work_type}
                onValueChange={(v) =>
                  setDiscrepancyForm((f) => ({ ...f, work_type: v }))
                }
              >
                <SelectTrigger id="disc-work" className="w-44" aria-label="工種">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.keys(WORK_TYPE_LABELS).map((value) => (
                    <SelectItem key={value} value={value}>
                      {value}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="disc-pref">都道府県</Label>
              <Select
                value={discrepancyForm.prefecture}
                onValueChange={(v) =>
                  setDiscrepancyForm((f) => ({ ...f, prefecture: v }))
                }
              >
                <SelectTrigger id="disc-pref" className="w-40" aria-label="都道府県">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PREFECTURES.map((value) => (
                    <SelectItem key={value} value={value}>
                      {value}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="disc-quote">見積単価（円/日）</Label>
              <Input
                id="disc-quote"
                type="number"
                min={0}
                value={discrepancyForm.quote_day_jpy}
                onChange={(e) =>
                  setDiscrepancyForm((f) => ({ ...f, quote_day_jpy: e.target.value }))
                }
                className="w-40"
                placeholder="例: 18000"
              />
            </div>
            <Button
              onClick={() => void runDiscrepancy()}
              disabled={
                !discrepancyForm.quote_day_jpy ||
                Number(discrepancyForm.quote_day_jpy) <= 0 ||
                checking
              }
              className="gap-2"
            >
              {checking ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <BadgeJapaneseYen className="h-4 w-4" aria-hidden="true" />
              )}
              判定
            </Button>
          </div>

          {discrepancyResult && (
            <div
              className={`rounded-md border p-4 ${
                discrepancyResult.status === "below"
                  ? discrepancyResult.severity === "critical"
                    ? "border-red-400 bg-red-50 dark:border-red-700 dark:bg-red-950/40"
                    : "border-amber-300 bg-amber-50 dark:border-amber-700 dark:bg-amber-950/30"
                  : "border-green-300 bg-green-50 dark:border-green-800 dark:bg-green-950/30"
              }`}
            >
              <div className="flex flex-wrap items-center gap-2">
                {discrepancyResult.status === "below" ? (
                  <AlertTriangle
                    className={`h-5 w-5 ${
                      discrepancyResult.severity === "critical"
                        ? "text-destructive"
                        : "text-amber-600 dark:text-amber-400"
                    }`}
                    aria-hidden="true"
                  />
                ) : (
                  <CheckCircle2 className="h-5 w-5 text-green-700 dark:text-green-400" aria-hidden="true" />
                )}
                <p className="text-sm font-semibold">
                  {discrepancyResult.status === "below"
                    ? discrepancyResult.severity === "critical"
                      ? "🚨 基準を大きく下回っています（ダンピング確認必須）"
                      : "⚠️ 基準値を下回っています（ダンピング確認要）"
                    : "✅ 基準値以上です"}
                </p>
                {discrepancyResult.status === "below" && (
                  <Badge
                    variant={
                      discrepancyResult.severity === "critical"
                        ? "destructive"
                        : discrepancyResult.severity === "warning"
                          ? "destructive"
                          : "secondary"
                    }
                  >
                    {discrepancyResult.severity === "critical"
                      ? "深刻（要即時確認）"
                      : discrepancyResult.severity === "warning"
                        ? "要確認"
                        : "注視"}
                  </Badge>
                )}
              </div>
              <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-4">
                <div>
                  <dt className="text-xs text-muted-foreground">工種</dt>
                  <dd>{discrepancyResult.work_type}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">地域</dt>
                  <dd>{discrepancyResult.prefecture ?? "全国"}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">基準日額（{discrepancyResult.effective_from} 〜）</dt>
                  <dd>{formatYen(discrepancyResult.standard_day_jpy)}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">見積単価</dt>
                  <dd>{formatYen(discrepancyResult.quote_day_jpy)}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">対基準比</dt>
                  <dd>{(discrepancyResult.ratio * 100).toFixed(1)}%</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">乖離率（不足率）</dt>
                  <dd>{(discrepancyResult.shortage_rate * 100).toFixed(1)}%</dd>
                </div>
              </dl>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 基準値一覧 */}
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-2 border-b px-6 py-4">
          <p className="text-sm font-semibold">基準値マスタ（工種 × 都道府県 × 適用期間）</p>
          <div className="flex items-center gap-2">
            <Select value={workTypeFilter} onValueChange={setWorkTypeFilter}>
              <SelectTrigger className="w-40" aria-label="工種で絞り込み">
                <SelectValue placeholder="工種" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">すべての工種</SelectItem>
                {Object.keys(WORK_TYPE_LABELS).map((value) => (
                  <SelectItem key={value} value={value}>
                    {value}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={prefectureFilter} onValueChange={setPrefectureFilter}>
              <SelectTrigger className="w-40" aria-label="都道府県で絞り込み">
                <SelectValue placeholder="都道府県" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">すべての地域</SelectItem>
                {PREFECTURES.map((value) => (
                  <SelectItem key={value} value={value}>
                    {value}
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
              <TableHead className="w-28">工種</TableHead>
              <TableHead className="w-28">都道府県</TableHead>
              <TableHead className="w-32">日額</TableHead>
              <TableHead className="w-56">適用期間</TableHead>
              <TableHead>出典</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={5} className="py-10 text-center text-sm text-muted-foreground">
                  <Loader2 className="mx-auto h-6 w-6 animate-spin" aria-hidden="true" />
                  読み込み中…
                </TableCell>
              </TableRow>
            ) : filtered.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="py-10 text-center text-sm text-muted-foreground">
                  基準値が登録されていません。「基準値を登録」から追加してください。
                </TableCell>
              </TableRow>
            ) : (
              filtered.map((standard) => (
                <TableRow key={String(standard.id)}>
                  <TableCell>
                    <Badge variant="outline">{standard.work_type}</Badge>
                  </TableCell>
                  <TableCell className="text-sm">{standard.prefecture ?? "全国"}</TableCell>
                  <TableCell className="whitespace-nowrap text-sm font-medium">
                    {formatYen(standard.amount_jpy)}
                    <span className="text-xs text-muted-foreground">/{standard.amount_unit}</span>
                  </TableCell>
                  <TableCell className="whitespace-nowrap font-mono text-sm text-muted-foreground">
                    {effectiveLabel(standard)}
                  </TableCell>
                  <TableCell className="max-w-[240px]">
                    <p className="truncate text-sm text-muted-foreground">
                      {standard.source_ref ?? "—"}
                    </p>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Card>

      {/* 価格協議・見積変更監視（#23/#24） */}
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-2 border-b px-6 py-4">
          <p className="flex items-center gap-2 text-sm font-semibold">
            <MessageSquareText className="h-4 w-4 text-primary" aria-hidden="true" />
            価格協議・見積変更監視（#23/#24・未回答を深刻度付きで管理）
          </p>
          <div className="flex items-center gap-2">
            <Select
              value={consultationStatusFilter}
              onValueChange={setConsultationStatusFilter}
            >
              <SelectTrigger className="w-36" aria-label="状態で絞り込み">
                <SelectValue placeholder="状態" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">すべての状態</SelectItem>
                {Object.entries(CONSULTATION_STATUS_LABELS).map(([value, label]) => (
                  <SelectItem key={value} value={value}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              variant="outline"
              size="icon"
              onClick={() => void loadConsultations()}
              aria-label="価格協議を再読み込み"
            >
              <RefreshCw className="h-4 w-4" />
            </Button>
            <Button onClick={() => setConsultOpen(true)} className="gap-2">
              <Plus className="h-4 w-4" aria-hidden="true" />
              協議申出
            </Button>
          </div>
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-32">協議 No</TableHead>
              <TableHead>内容</TableHead>
              <TableHead className="w-40">方向</TableHead>
              <TableHead className="w-24">単価</TableHead>
              <TableHead className="w-20">深刻度</TableHead>
              <TableHead className="w-20">状態</TableHead>
              <TableHead className="w-36">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {consultationsLoading ? (
              <TableRow>
                <TableCell colSpan={7} className="py-10 text-center text-sm text-muted-foreground">
                  <Loader2 className="mx-auto h-6 w-6 animate-spin" aria-hidden="true" />
                  読み込み中…
                </TableCell>
              </TableRow>
            ) : filteredConsultations.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="py-10 text-center text-sm text-muted-foreground">
                  価格協議の記録がありません。「協議申出」から登録してください。
                </TableCell>
              </TableRow>
            ) : (
              filteredConsultations.map((log) => (
                <TableRow key={String(log.id)}>
                  <TableCell className="whitespace-nowrap font-mono text-sm">
                    {log.log_no}
                  </TableCell>
                  <TableCell className="max-w-[240px]">
                    <p className="truncate text-sm font-medium">{log.summary}</p>
                    <p className="text-xs text-muted-foreground">
                      {log.work_type}
                      {log.prefecture ? ` / ${log.prefecture}` : ""}
                      {log.responded_at ? ` / 回答: ${log.response_summary ?? ""}` : ""}
                    </p>
                  </TableCell>
                  <TableCell className="text-xs">
                    {DIRECTION_LABELS[log.direction] ?? log.direction}
                  </TableCell>
                  <TableCell className="whitespace-nowrap text-sm">
                    {log.quote_day_jpy !== null && log.quote_day_jpy !== undefined
                      ? formatYen(log.quote_day_jpy)
                      : "—"}
                    {log.standard_day_jpy !== null && log.standard_day_jpy !== undefined && (
                      <span className="block text-xs text-muted-foreground">
                        基準 {formatYen(log.standard_day_jpy)}
                      </span>
                    )}
                  </TableCell>
                  <TableCell>
                    <Badge variant={SEVERITY_VARIANT[log.severity ?? "none"] ?? "outline"}>
                      {SEVERITY_LABELS[log.severity ?? "none"] ?? log.severity}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant={CONSULTATION_STATUS_VARIANT[log.status] ?? "outline"}>
                      {CONSULTATION_STATUS_LABELS[log.status] ?? log.status}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {log.status === "open" && (
                      <div className="flex gap-1">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setRespondTarget(log);
                            setRespondText("");
                          }}
                        >
                          <Send className="mr-1 h-3 w-3" aria-hidden="true" />
                          回答
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-destructive"
                          onClick={() => {
                            setCancelTarget(log);
                            setCancelReason("");
                          }}
                        >
                          <XCircle className="mr-1 h-3 w-3" aria-hidden="true" />
                          取下げ
                        </Button>
                      </div>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Card>

      {/* 基準値登録ダイアログ */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>労務費基準値を登録</DialogTitle>
            <DialogDescription>
              適用期間で履歴蓄積されます。同じ工種・都道府県に新しい期間を登録できます。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="lw-work">工種</Label>
                <Select
                  value={form.work_type}
                  onValueChange={(v) => setForm((f) => ({ ...f, work_type: v }))}
                >
                  <SelectTrigger id="lw-work" aria-label="工種">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.keys(WORK_TYPE_LABELS).map((value) => (
                      <SelectItem key={value} value={value}>
                        {value}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="lw-pref">都道府県</Label>
                <Select
                  value={form.prefecture}
                  onValueChange={(v) => setForm((f) => ({ ...f, prefecture: v }))}
                >
                  <SelectTrigger id="lw-pref" aria-label="都道府県">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {PREFECTURES.map((value) => (
                      <SelectItem key={value} value={value}>
                        {value}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="lw-amount">基準日額（円・必須）</Label>
              <Input
                id="lw-amount"
                type="number"
                min={0}
                value={form.amount_jpy}
                onChange={(e) => setForm((f) => ({ ...f, amount_jpy: e.target.value }))}
                placeholder="例: 19000"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="lw-from">適用開始日（必須）</Label>
                <Input
                  id="lw-from"
                  type="date"
                  value={form.effective_from}
                  onChange={(e) => setForm((f) => ({ ...f, effective_from: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="lw-to">適用終了日（任意）</Label>
                <Input
                  id="lw-to"
                  type="date"
                  value={form.effective_to}
                  onChange={(e) => setForm((f) => ({ ...f, effective_to: e.target.value }))}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="lw-src">出典（任意）</Label>
              <Input
                id="lw-src"
                value={form.source_ref}
                onChange={(e) => setForm((f) => ({ ...f, source_ref: e.target.value }))}
                placeholder="例: 国土交通省 労務費基準 2026年度版"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              キャンセル
            </Button>
            <Button
              onClick={() => void createStandard()}
              disabled={!form.amount_jpy || !form.effective_from || creating}
            >
              {creating && <Loader2 className="mr-1 h-4 w-4 animate-spin" aria-hidden="true" />}
              登録
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 価格協議申出ダイアログ（#24） */}
      <Dialog open={consultOpen} onOpenChange={setConsultOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>価格協議を申出（#24）</DialogTitle>
            <DialogDescription>
              労務費に関する価格協議を記録します。単価を指定すると、基準値との乖離率と
              深刻度（ダンピング警告 #21）が自動で判定・保存されます。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="pc-direction">方向</Label>
              <Select
                value={consultForm.direction}
                onValueChange={(v) => setConsultForm((f) => ({ ...f, direction: v }))}
              >
                <SelectTrigger id="pc-direction" aria-label="方向">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="from_subcontractor">下請→元請（引上げ申出）</SelectItem>
                  <SelectItem value="to_subcontractor">元請→下請（価格確認）</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="pc-work">工種</Label>
                <Select
                  value={consultForm.work_type}
                  onValueChange={(v) => setConsultForm((f) => ({ ...f, work_type: v }))}
                >
                  <SelectTrigger id="pc-work" aria-label="工種">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.keys(WORK_TYPE_LABELS).map((value) => (
                      <SelectItem key={value} value={value}>
                        {value}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="pc-pref">都道府県</Label>
                <Select
                  value={consultForm.prefecture}
                  onValueChange={(v) => setConsultForm((f) => ({ ...f, prefecture: v }))}
                >
                  <SelectTrigger id="pc-pref" aria-label="都道府県">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {PREFECTURES.map((value) => (
                      <SelectItem key={value} value={value}>
                        {value}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="pc-quote">協議対象単価（円/日・任意）</Label>
              <Input
                id="pc-quote"
                type="number"
                min={0}
                value={consultForm.quote_day_jpy}
                onChange={(e) =>
                  setConsultForm((f) => ({ ...f, quote_day_jpy: e.target.value }))
                }
                placeholder="例: 17500"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="pc-summary">協議内容（必須）</Label>
              <Input
                id="pc-summary"
                value={consultForm.summary}
                onChange={(e) => setConsultForm((f) => ({ ...f, summary: e.target.value }))}
                placeholder="例: 労務費上昇に伴う単価引上げ協議"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="pc-detail">詳細（任意）</Label>
              <Textarea
                id="pc-detail"
                value={consultForm.request_detail}
                onChange={(e) =>
                  setConsultForm((f) => ({ ...f, request_detail: e.target.value }))
                }
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConsultOpen(false)}>
              キャンセル
            </Button>
            <Button
              onClick={() => void createConsultation()}
              disabled={!consultForm.summary.trim() || consultCreating}
            >
              {consultCreating && (
                <Loader2 className="mr-1 h-4 w-4 animate-spin" aria-hidden="true" />
              )}
              申出を記録
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 価格協議回答ダイアログ（#24・open → responded） */}
      <Dialog
        open={respondTarget !== null}
        onOpenChange={(open) => {
          if (!open) setRespondTarget(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>価格協議へ回答</DialogTitle>
            <DialogDescription>
              {respondTarget?.log_no} — {respondTarget?.summary}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <p className="text-xs font-semibold text-muted-foreground">申出内容</p>
              <p className="mt-1 whitespace-pre-wrap rounded-md border bg-muted/40 p-3 text-sm">
                {respondTarget?.request_detail ?? respondTarget?.summary}
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="pc-response">回答内容（必須）</Label>
              <Textarea
                id="pc-response"
                value={respondText}
                onChange={(e) => setRespondText(e.target.value)}
                rows={5}
                placeholder="協議への回答方針・理由を記載してください（最終判断は法務担当者が行います）"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRespondTarget(null)}>
              キャンセル
            </Button>
            <Button
              onClick={() => void respondConsultation()}
              disabled={!respondText.trim() || consultRunning}
            >
              {consultRunning && (
                <Loader2 className="mr-1 h-4 w-4 animate-spin" aria-hidden="true" />
              )}
              回答を記録
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 価格協議取下げダイアログ（#24・open → cancelled） */}
      <Dialog
        open={cancelTarget !== null}
        onOpenChange={(open) => {
          if (!open) setCancelTarget(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>価格協議を取下げ</DialogTitle>
            <DialogDescription>
              {cancelTarget?.log_no} — {cancelTarget?.summary}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="pc-cancel-reason">取下げ理由（必須）</Label>
            <Textarea
              id="pc-cancel-reason"
              value={cancelReason}
              onChange={(e) => setCancelReason(e.target.value)}
              rows={2}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCancelTarget(null)}>
              戻る
            </Button>
            <Button
              variant="destructive"
              onClick={() => void cancelConsultation()}
              disabled={!cancelReason.trim() || consultRunning}
            >
              {consultRunning && (
                <Loader2 className="mr-1 h-4 w-4 animate-spin" aria-hidden="true" />
              )}
              取り下げる
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
