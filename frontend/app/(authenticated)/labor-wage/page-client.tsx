"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  BadgeJapaneseYen,
  CheckCircle2,
  Loader2,
  Plus,
  RefreshCw,
  Scale,
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
import { laborWageApi } from "@/lib/api";
import type {
  LaborWageDiscrepancy,
  LaborWageStandard,
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
            見積単価の乖離率判定（#20）
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
                  ? "border-red-300 bg-red-50 dark:border-red-800 dark:bg-red-950/30"
                  : "border-green-300 bg-green-50 dark:border-green-800 dark:bg-green-950/30"
              }`}
            >
              <div className="flex items-center gap-2">
                {discrepancyResult.status === "below" ? (
                  <AlertTriangle className="h-5 w-5 text-destructive" aria-hidden="true" />
                ) : (
                  <CheckCircle2 className="h-5 w-5 text-green-700 dark:text-green-400" aria-hidden="true" />
                )}
                <p className="text-sm font-semibold">
                  {discrepancyResult.status === "below"
                    ? "⚠️ 基準値を下回っています（ダンピング確認要）"
                    : "✅ 基準値以上です"}
                </p>
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
    </div>
  );
}
