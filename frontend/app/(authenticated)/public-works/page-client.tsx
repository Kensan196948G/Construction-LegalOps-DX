"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  Building2,
  CheckCircle2,
  ClipboardCheck,
  Loader2,
  MessageSquareText,
  Plus,
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
import {
  contractsApi,
  contractingAgenciesApi,
  ownerNotificationsApi,
  publicWorksApi,
  publicWorksConsultationsApi,
} from "@/lib/api";
import type {
  Contract,
  ContractingAgency,
  OwnerNotification,
  PublicWorksConsultation,
  PublicWorksDashboard,
  StandardClauseCheck,
} from "@/lib/api/schemas";

const AGENCY_TYPE_LABELS: Record<string, string> = {
  national: "国の機関",
  prefectural: "都道府県",
  municipal: "市町村",
  public_corp: "公社・公団",
  other: "その他",
};

const NOTIF_TYPE_LABELS: Record<string, string> = {
  design_change: "設計変更",
  delay: "工期遅延",
  suspension: "中止・再開",
  claim: "請求・クレーム",
  completion: "完了・引渡し",
  other: "その他",
};

const NOTIF_STATUS_LABELS: Record<string, string> = {
  open: "送付待ち",
  notified: "通知済",
  cancelled: "取下げ",
};

const NOTIF_STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  open: "destructive",
  notified: "default",
  cancelled: "secondary",
};

const CONSULT_TYPE_LABELS: Record<string, string> = {
  extension_of_time: "工期延伸協議",
  design_change: "設計変更協議",
  price_slide: "スライド請求",
  suspension: "中止・再開協議",
  other: "その他",
};

const CONSULT_STATUS_LABELS: Record<string, string> = {
  open: "協議中",
  responded: "回答済",
  cancelled: "取下げ",
};

const CONSULT_STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  open: "outline",
  responded: "default",
  cancelled: "secondary",
};

function formatYen(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${value.toLocaleString("ja-JP")} 円`;
}

function isOverdue(notification: OwnerNotification): boolean {
  if (notification.status !== "open" || !notification.due_date) return false;
  return new Date(`${notification.due_date}T00:00:00+09:00`).getTime() < Date.now();
}

function agencyNameById(
  agencies: ContractingAgency[],
  id: number | string | null | undefined
): string {
  if (id === null || id === undefined) return "—";
  const found = agencies.find((a) => String(a.id) === String(id));
  return found?.name ?? `機関 ID ${id}`;
}

export default function PublicWorksPage() {
  const [dashboard, setDashboard] = useState<PublicWorksDashboard | null>(null);
  const [agencies, setAgencies] = useState<ContractingAgency[]>([]);
  const [notifications, setNotifications] = useState<OwnerNotification[]>([]);
  const [consultations, setConsultations] = useState<PublicWorksConsultation[]>([]);
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  // 発注機関登録
  const [agencyOpen, setAgencyOpen] = useState(false);
  const [agencySaving, setAgencySaving] = useState(false);
  const [agencyForm, setAgencyForm] = useState({
    code: "",
    name: "",
    agency_type: "municipal",
    prefecture: "",
    payment_deadline_days: "",
    advance_payment_ratio: "",
    requires_slide_clause: false,
    notes: "",
  });

  // 通知登録
  const [notifOpen, setNotifOpen] = useState(false);
  const [notifSaving, setNotifSaving] = useState(false);
  const [notifForm, setNotifForm] = useState({
    notification_type: "delay",
    title: "",
    agency_id: "",
    detail: "",
    due_date: "",
  });

  // 協議
  const [consultOpen, setConsultOpen] = useState(false);
  const [consultSaving, setConsultSaving] = useState(false);
  const [consultForm, setConsultForm] = useState({
    consultation_type: "extension_of_time",
    title: "",
    agency_id: "",
    detail: "",
    due_date: "",
    claimed_days: "",
    claimed_amount_jpy: "",
  });
  const [respondTarget, setRespondTarget] = useState<PublicWorksConsultation | null>(null);
  const [respondForm, setRespondForm] = useState({
    response_note: "",
    resolved_days: "",
    resolved_amount_jpy: "",
  });
  const [running, setRunning] = useState(false);

  // 約款差分チェック（#43）
  const [checkContractId, setCheckContractId] = useState("");
  const [checkResult, setCheckResult] = useState<StandardClauseCheck | null>(null);
  const [checkRunning, setCheckRunning] = useState(false);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [dash, agencyRows, notifRows, consultRows, contractRows] = await Promise.all([
        publicWorksApi.dashboard(),
        contractingAgenciesApi.list({ page: 1, size: 100 }),
        ownerNotificationsApi.list({ page: 1, size: 100 }),
        publicWorksConsultationsApi.list({ page: 1, size: 100 }),
        contractsApi.list({ page: 1, page_size: 200 }),
      ]);
      setDashboard(dash);
      setAgencies(agencyRows.items);
      setNotifications(notifRows.items);
      setConsultations(consultRows.items);
      setContracts(contractRows.items);
      setOffline(false);
    } catch {
      setOffline(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  const createAgency = async () => {
    if (!agencyForm.code.trim() || !agencyForm.name.trim() || agencySaving) return;
    setAgencySaving(true);
    setActionError(null);
    try {
      await contractingAgenciesApi.create({
        code: agencyForm.code.trim(),
        name: agencyForm.name.trim(),
        agency_type: agencyForm.agency_type,
        prefecture: agencyForm.prefecture || null,
        payment_deadline_days: agencyForm.payment_deadline_days
          ? Number(agencyForm.payment_deadline_days)
          : null,
        advance_payment_ratio: agencyForm.advance_payment_ratio
          ? Number(agencyForm.advance_payment_ratio)
          : null,
        requires_slide_clause: agencyForm.requires_slide_clause,
        notes: agencyForm.notes || null,
      });
      setAgencyOpen(false);
      setAgencyForm({
        code: "",
        name: "",
        agency_type: "municipal",
        prefecture: "",
        payment_deadline_days: "",
        advance_payment_ratio: "",
        requires_slide_clause: false,
        notes: "",
      });
      await loadAll();
    } catch (err) {
      setActionError(
        err instanceof Error ? `登録に失敗しました: ${err.message}` : "登録に失敗しました。"
      );
    } finally {
      setAgencySaving(false);
    }
  };

  const createNotification = async () => {
    if (!notifForm.title.trim() || notifSaving) return;
    setNotifSaving(true);
    setActionError(null);
    try {
      await ownerNotificationsApi.create({
        notification_type: notifForm.notification_type,
        title: notifForm.title.trim(),
        agency_id: notifForm.agency_id || null,
        detail: notifForm.detail || null,
        due_date: notifForm.due_date || null,
      });
      setNotifOpen(false);
      setNotifForm({
        notification_type: "delay",
        title: "",
        agency_id: "",
        detail: "",
        due_date: "",
      });
      await loadAll();
    } catch (err) {
      setActionError(
        err instanceof Error ? `登録に失敗しました: ${err.message}` : "登録に失敗しました。"
      );
    } finally {
      setNotifSaving(false);
    }
  };

  const createConsultation = async () => {
    if (!consultForm.title.trim() || consultSaving) return;
    setConsultSaving(true);
    setActionError(null);
    try {
      await publicWorksConsultationsApi.create({
        consultation_type: consultForm.consultation_type,
        title: consultForm.title.trim(),
        agency_id: consultForm.agency_id || null,
        detail: consultForm.detail || null,
        due_date: consultForm.due_date || null,
        claimed_days: consultForm.claimed_days ? Number(consultForm.claimed_days) : null,
        claimed_amount_jpy: consultForm.claimed_amount_jpy
          ? Number(consultForm.claimed_amount_jpy)
          : null,
      });
      setConsultOpen(false);
      setConsultForm({
        consultation_type: "extension_of_time",
        title: "",
        agency_id: "",
        detail: "",
        due_date: "",
        claimed_days: "",
        claimed_amount_jpy: "",
      });
      await loadAll();
    } catch (err) {
      setActionError(
        err instanceof Error ? `申出に失敗しました: ${err.message}` : "申出に失敗しました。"
      );
    } finally {
      setConsultSaving(false);
    }
  };

  const respondConsultation = async () => {
    if (!respondTarget || !respondForm.response_note.trim() || running) return;
    setRunning(true);
    setActionError(null);
    try {
      await publicWorksConsultationsApi.respond(respondTarget.id, {
        response_note: respondForm.response_note.trim(),
        resolved_days: respondForm.resolved_days ? Number(respondForm.resolved_days) : null,
        resolved_amount_jpy: respondForm.resolved_amount_jpy
          ? Number(respondForm.resolved_amount_jpy)
          : null,
      });
      setRespondTarget(null);
      setRespondForm({ response_note: "", resolved_days: "", resolved_amount_jpy: "" });
      await loadAll();
    } catch (err) {
      setActionError(
        err instanceof Error ? `回答に失敗しました: ${err.message}` : "回答に失敗しました。"
      );
    } finally {
      setRunning(false);
    }
  };

  const handleNotify = async (notification: OwnerNotification) => {
    setActionError(null);
    try {
      await ownerNotificationsApi.notify(notification.id);
      await loadAll();
    } catch (err) {
      setActionError(
        err instanceof Error ? `通知処理に失敗しました: ${err.message}` : "通知処理に失敗しました。"
      );
    }
  };

  const runClauseCheck = async () => {
    if (!checkContractId || checkRunning) return;
    setCheckRunning(true);
    setActionError(null);
    setCheckResult(null);
    try {
      const result = await publicWorksApi.standardClauseCheck(checkContractId);
      setCheckResult(result);
    } catch (err) {
      setActionError(
        err instanceof Error ? `チェックに失敗しました: ${err.message}` : "チェックに失敗しました。"
      );
    } finally {
      setCheckRunning(false);
    }
  };

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-foreground">公共工事</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          発注機関マスタ・通知期限・協議管理・標準約款チェックを管理します（公共工事特化）
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

      {/* #60 ダッシュボード */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Card>
          <CardContent className="flex items-center gap-3 pt-4">
            <Building2 className="h-8 w-8 text-muted-foreground" aria-hidden="true" />
            <div>
              <p className="text-2xl font-bold">{dashboard?.agencies_active ?? "—"}</p>
              <p className="text-sm text-muted-foreground">有効な発注機関</p>
            </div>
          </CardContent>
        </Card>
        <Card
          className={
            (dashboard?.notifications_overdue ?? 0) > 0
              ? "border-red-300 bg-red-50 dark:border-red-800 dark:bg-red-950/30"
              : ""
          }
        >
          <CardContent className="flex items-center gap-3 pt-4">
            <AlertTriangle
              className={`h-8 w-8 ${
                (dashboard?.notifications_overdue ?? 0) > 0
                  ? "text-destructive"
                  : "text-muted-foreground"
              }`}
              aria-hidden="true"
            />
            <div>
              <p className="text-2xl font-bold">{dashboard?.notifications_overdue ?? "—"}</p>
              <p className="text-sm text-muted-foreground">通知期限切れ</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 pt-4">
            <Send className="h-8 w-8 text-muted-foreground" aria-hidden="true" />
            <div>
              <p className="text-2xl font-bold">{dashboard?.notifications_open ?? "—"}</p>
              <p className="text-sm text-muted-foreground">送付待ち通知</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 pt-4">
            <MessageSquareText className="h-8 w-8 text-muted-foreground" aria-hidden="true" />
            <div>
              <p className="text-2xl font-bold">{dashboard?.consultations_open ?? "—"}</p>
              <p className="text-sm text-muted-foreground">協議中</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* #43 標準約款差分チェック */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ClipboardCheck className="h-4 w-4 text-primary" aria-hidden="true" />
            標準請負約款差分チェック（#43）
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-[280px] flex-1 space-y-2">
              <Label htmlFor="pw-check-contract">チェック対象契約</Label>
              <Select value={checkContractId} onValueChange={setCheckContractId}>
                <SelectTrigger id="pw-check-contract" aria-label="対象契約">
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
            <Button
              onClick={() => void runClauseCheck()}
              disabled={!checkContractId || checkRunning}
              className="gap-2"
            >
              {checkRunning ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <ClipboardCheck className="h-4 w-4" aria-hidden="true" />
              )}
              チェック実行
            </Button>
          </div>

          {checkResult && (
            <div className="space-y-3 rounded-md border p-4">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={checkResult.missing_categories === 0 ? "default" : "destructive"}>
                  {checkResult.covered_categories}/{checkResult.total_categories} カテゴリ確認
                </Badge>
                {checkResult.missing_categories > 0 && (
                  <span className="text-sm text-muted-foreground">
                    欠落 {checkResult.missing_categories} カテゴリ（要確認）
                  </span>
                )}
              </div>
              <ul className="grid grid-cols-1 gap-1 text-sm sm:grid-cols-2 lg:grid-cols-3">
                {(checkResult.categories ?? []).map((cat) => (
                  <li key={cat.category} className="flex items-center gap-2">
                    {cat.covered ? (
                      <CheckCircle2 className="h-3.5 w-3.5 text-green-700 dark:text-green-400" aria-hidden="true" />
                    ) : (
                      <AlertTriangle className="h-3.5 w-3.5 text-amber-500" aria-hidden="true" />
                    )}
                    <span className={cat.covered ? "" : "text-muted-foreground"}>
                      {cat.category}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </CardContent>
      </Card>

      {/* #54 発注者通知期限 */}
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-2 border-b px-6 py-4">
          <p className="text-sm font-semibold">発注者通知期限管理（#54）</p>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="icon" onClick={() => void loadAll()} aria-label="再読み込み">
              <RefreshCw className="h-4 w-4" />
            </Button>
            <Button
              onClick={() => {
                setNotifOpen(true);
              }}
              className="gap-2"
            >
              <Plus className="h-4 w-4" aria-hidden="true" />
              通知を登録
            </Button>
          </div>
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-32">通知 No</TableHead>
              <TableHead>内容</TableHead>
              <TableHead className="w-28">種別</TableHead>
              <TableHead className="w-28">期限</TableHead>
              <TableHead className="w-20">状態</TableHead>
              <TableHead className="w-24">操作</TableHead>
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
            ) : notifications.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="py-10 text-center text-sm text-muted-foreground">
                  発注者通知の記録がありません。
                </TableCell>
              </TableRow>
            ) : (
              notifications.map((notification) => {
                const overdue = isOverdue(notification);
                return (
                  <TableRow
                    key={String(notification.id)}
                    className={overdue ? "bg-red-50/50 dark:bg-red-950/20" : ""}
                  >
                    <TableCell className="whitespace-nowrap font-mono text-sm">
                      {notification.notification_no}
                    </TableCell>
                    <TableCell className="max-w-[240px]">
                      <p className="truncate text-sm font-medium">{notification.title}</p>
                      <p className="text-xs text-muted-foreground">
                        {agencyNameById(agencies, notification.agency_id)}
                      </p>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">
                        {NOTIF_TYPE_LABELS[notification.notification_type] ??
                          notification.notification_type}
                      </Badge>
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-sm">
                      {notification.due_date ?? "—"}
                    </TableCell>
                    <TableCell>
                      <Badge variant={NOTIF_STATUS_VARIANT[notification.status] ?? "outline"}>
                        {NOTIF_STATUS_LABELS[notification.status] ?? notification.status}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {notification.status === "open" && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => void handleNotify(notification)}
                        >
                          <Send className="mr-1 h-3 w-3" aria-hidden="true" />
                          通知済へ
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </Card>

      {/* #55-#57 協議管理 */}
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-2 border-b px-6 py-4">
          <p className="text-sm font-semibold">
            発注者との協議（工期延伸・設計変更・スライド請求 / #55-#57）
          </p>
          <Button onClick={() => setConsultOpen(true)} className="gap-2">
            <Plus className="h-4 w-4" aria-hidden="true" />
            協議を申出
          </Button>
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-32">協議 No</TableHead>
              <TableHead>内容</TableHead>
              <TableHead className="w-32">種別</TableHead>
              <TableHead className="w-32">申出</TableHead>
              <TableHead className="w-24">状態</TableHead>
              <TableHead className="w-24">操作</TableHead>
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
            ) : consultations.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="py-10 text-center text-sm text-muted-foreground">
                  協議の記録がありません。
                </TableCell>
              </TableRow>
            ) : (
              consultations.map((consult) => (
                <TableRow key={String(consult.id)}>
                  <TableCell className="whitespace-nowrap font-mono text-sm">
                    {consult.consultation_no}
                  </TableCell>
                  <TableCell className="max-w-[240px]">
                    <p className="truncate text-sm font-medium">{consult.title}</p>
                    <p className="text-xs text-muted-foreground">
                      {agencyNameById(agencies, consult.agency_id)}
                      {consult.claimed_days ? ` / 申出 ${consult.claimed_days} 日` : ""}
                      {consult.claimed_amount_jpy
                        ? ` / 申出 ${formatYen(consult.claimed_amount_jpy)}`
                        : ""}
                    </p>
                    {consult.response_note && (
                      <p className="mt-1 line-clamp-1 rounded bg-muted/40 p-1 text-xs text-muted-foreground">
                        回答: {consult.response_note}
                      </p>
                    )}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">
                      {CONSULT_TYPE_LABELS[consult.consultation_type] ?? consult.consultation_type}
                    </Badge>
                  </TableCell>
                  <TableCell className="whitespace-nowrap text-sm">
                    {consult.due_date ?? "—"}
                  </TableCell>
                  <TableCell>
                    <Badge variant={CONSULT_STATUS_VARIANT[consult.status] ?? "outline"}>
                      {CONSULT_STATUS_LABELS[consult.status] ?? consult.status}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {consult.status === "open" && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setRespondTarget(consult);
                          setRespondForm({
                            response_note: "",
                            resolved_days: "",
                            resolved_amount_jpy: "",
                          });
                        }}
                      >
                        回答
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Card>

      {/* #41/#42 発注機関マスタ */}
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-2 border-b px-6 py-4">
          <p className="flex items-center gap-2 text-sm font-semibold">
            <Building2 className="h-4 w-4 text-primary" aria-hidden="true" />
            発注機関マスタ（#41）＋機関別契約条件（#42）
          </p>
          <Button onClick={() => setAgencyOpen(true)} className="gap-2">
            <Plus className="h-4 w-4" aria-hidden="true" />
            機関を登録
          </Button>
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-32">コード</TableHead>
              <TableHead>機関名</TableHead>
              <TableHead className="w-24">種別</TableHead>
              <TableHead className="w-28">支払日数</TableHead>
              <TableHead className="w-20">前払率</TableHead>
              <TableHead className="w-24">スライド条項</TableHead>
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
            ) : agencies.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="py-10 text-center text-sm text-muted-foreground">
                  発注機関が登録されていません。
                </TableCell>
              </TableRow>
            ) : (
              agencies.map((agency) => (
                <TableRow key={String(agency.id)}>
                  <TableCell className="whitespace-nowrap font-mono text-sm">
                    {agency.code}
                  </TableCell>
                  <TableCell className="text-sm font-medium">{agency.name}</TableCell>
                  <TableCell>
                    <Badge variant="outline">
                      {AGENCY_TYPE_LABELS[agency.agency_type] ?? agency.agency_type}
                    </Badge>
                  </TableCell>
                  <TableCell className="whitespace-nowrap text-sm">
                    {agency.payment_deadline_days ? `${agency.payment_deadline_days} 日` : "—"}
                  </TableCell>
                  <TableCell className="whitespace-nowrap text-sm">
                    {agency.advance_payment_ratio !== null &&
                    agency.advance_payment_ratio !== undefined
                      ? `${Math.round(agency.advance_payment_ratio * 100)}%`
                      : "—"}
                  </TableCell>
                  <TableCell className="whitespace-nowrap text-sm">
                    {agency.requires_slide_clause ? "必須" : "—"}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Card>

      {/* 発注機関登録ダイアログ */}
      <Dialog open={agencyOpen} onOpenChange={setAgencyOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>発注機関を登録（#41/#42）</DialogTitle>
            <DialogDescription>
              機関ごとの支払日数・前払率等の契約条件も登録できます。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="ag-code">機関コード（必須）</Label>
                <Input
                  id="ag-code"
                  value={agencyForm.code}
                  onChange={(e) => setAgencyForm((f) => ({ ...f, code: e.target.value }))}
                  placeholder="例: AG-DEMO-0004"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="ag-type">種別</Label>
                <Select
                  value={agencyForm.agency_type}
                  onValueChange={(v) => setAgencyForm((f) => ({ ...f, agency_type: v }))}
                >
                  <SelectTrigger id="ag-type" aria-label="種別">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(AGENCY_TYPE_LABELS).map(([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="ag-name">機関名（必須）</Label>
              <Input
                id="ag-name"
                value={agencyForm.name}
                onChange={(e) => setAgencyForm((f) => ({ ...f, name: e.target.value }))}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="ag-pay">支払日数（日・任意）</Label>
                <Input
                  id="ag-pay"
                  type="number"
                  min={1}
                  value={agencyForm.payment_deadline_days}
                  onChange={(e) =>
                    setAgencyForm((f) => ({ ...f, payment_deadline_days: e.target.value }))
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="ag-adv">前払率（0〜1・任意）</Label>
                <Input
                  id="ag-adv"
                  type="number"
                  step="0.1"
                  min={0}
                  max={1}
                  value={agencyForm.advance_payment_ratio}
                  onChange={(e) =>
                    setAgencyForm((f) => ({ ...f, advance_payment_ratio: e.target.value }))
                  }
                />
              </div>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={agencyForm.requires_slide_clause}
                onChange={(e) =>
                  setAgencyForm((f) => ({ ...f, requires_slide_clause: e.target.checked }))
                }
              />
              スライド条項必須
            </label>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAgencyOpen(false)}>
              キャンセル
            </Button>
            <Button
              onClick={() => void createAgency()}
              disabled={!agencyForm.code.trim() || !agencyForm.name.trim() || agencySaving}
            >
              {agencySaving && <Loader2 className="mr-1 h-4 w-4 animate-spin" aria-hidden="true" />}
              登録
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 通知登録ダイアログ */}
      <Dialog open={notifOpen} onOpenChange={setNotifOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>発注者通知を登録（#54）</DialogTitle>
            <DialogDescription>通知種別と送付期限を指定します。</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="on-type">種別</Label>
                <Select
                  value={notifForm.notification_type}
                  onValueChange={(v) => setNotifForm((f) => ({ ...f, notification_type: v }))}
                >
                  <SelectTrigger id="on-type" aria-label="種別">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(NOTIF_TYPE_LABELS).map(([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="on-due">送付期限</Label>
                <Input
                  id="on-due"
                  type="date"
                  value={notifForm.due_date}
                  onChange={(e) => setNotifForm((f) => ({ ...f, due_date: e.target.value }))}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="on-title">件名（必須）</Label>
              <Input
                id="on-title"
                value={notifForm.title}
                onChange={(e) => setNotifForm((f) => ({ ...f, title: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="on-detail">詳細（任意）</Label>
              <Textarea
                id="on-detail"
                value={notifForm.detail}
                onChange={(e) => setNotifForm((f) => ({ ...f, detail: e.target.value }))}
                rows={2}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setNotifOpen(false)}>
              キャンセル
            </Button>
            <Button
              onClick={() => void createNotification()}
              disabled={!notifForm.title.trim() || notifSaving}
            >
              {notifSaving && <Loader2 className="mr-1 h-4 w-4 animate-spin" aria-hidden="true" />}
              登録
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 協議申出ダイアログ（#55-#57） */}
      <Dialog open={consultOpen} onOpenChange={setConsultOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>発注者との協議を申出（#55-#57）</DialogTitle>
            <DialogDescription>
              工期延伸・設計変更・スライド請求などの協議を記録します。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="pw-ctype">種別</Label>
                <Select
                  value={consultForm.consultation_type}
                  onValueChange={(v) => setConsultForm((f) => ({ ...f, consultation_type: v }))}
                >
                  <SelectTrigger id="pw-ctype" aria-label="種別">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(CONSULT_TYPE_LABELS).map(([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="pw-agency">発注機関（任意）</Label>
                <Select
                  value={consultForm.agency_id}
                  onValueChange={(v) => setConsultForm((f) => ({ ...f, agency_id: v }))}
                >
                  <SelectTrigger id="pw-agency" aria-label="発注機関">
                    <SelectValue placeholder="選択" />
                  </SelectTrigger>
                  <SelectContent>
                    {agencies.map((a) => (
                      <SelectItem key={String(a.id)} value={String(a.id)}>
                        {a.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="pw-title">件名（必須）</Label>
              <Input
                id="pw-title"
                value={consultForm.title}
                onChange={(e) => setConsultForm((f) => ({ ...f, title: e.target.value }))}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="pw-days">申出日数（工期延伸・任意）</Label>
                <Input
                  id="pw-days"
                  type="number"
                  min={1}
                  value={consultForm.claimed_days}
                  onChange={(e) =>
                    setConsultForm((f) => ({ ...f, claimed_days: e.target.value }))
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="pw-amount">申出金額（スライド等・任意）</Label>
                <Input
                  id="pw-amount"
                  type="number"
                  min={0}
                  value={consultForm.claimed_amount_jpy}
                  onChange={(e) =>
                    setConsultForm((f) => ({ ...f, claimed_amount_jpy: e.target.value }))
                  }
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="pw-due">協議期限</Label>
              <Input
                id="pw-due"
                type="date"
                value={consultForm.due_date}
                onChange={(e) => setConsultForm((f) => ({ ...f, due_date: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="pw-detail">詳細（任意）</Label>
              <Textarea
                id="pw-detail"
                value={consultForm.detail}
                onChange={(e) => setConsultForm((f) => ({ ...f, detail: e.target.value }))}
                rows={2}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConsultOpen(false)}>
              キャンセル
            </Button>
            <Button
              onClick={() => void createConsultation()}
              disabled={!consultForm.title.trim() || consultSaving}
            >
              {consultSaving && <Loader2 className="mr-1 h-4 w-4 animate-spin" aria-hidden="true" />}
              申出
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 協議回答ダイアログ */}
      <Dialog
        open={respondTarget !== null}
        onOpenChange={(open) => {
          if (!open) setRespondTarget(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>協議の回答・結果を記録</DialogTitle>
            <DialogDescription>
              {respondTarget?.consultation_no} — {respondTarget?.title}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="pw-note">回答内容（必須）</Label>
              <Textarea
                id="pw-note"
                value={respondForm.response_note}
                onChange={(e) => setRespondForm((f) => ({ ...f, response_note: e.target.value }))}
                rows={4}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="pw-rdays">確定日数（工期延伸・任意）</Label>
                <Input
                  id="pw-rdays"
                  type="number"
                  min={1}
                  value={respondForm.resolved_days}
                  onChange={(e) =>
                    setRespondForm((f) => ({ ...f, resolved_days: e.target.value }))
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="pw-ramount">確定金額（円・任意）</Label>
                <Input
                  id="pw-ramount"
                  type="number"
                  min={0}
                  value={respondForm.resolved_amount_jpy}
                  onChange={(e) =>
                    setRespondForm((f) => ({ ...f, resolved_amount_jpy: e.target.value }))
                  }
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRespondTarget(null)}>
              キャンセル
            </Button>
            <Button
              onClick={() => void respondConsultation()}
              disabled={!respondForm.response_note.trim() || running}
            >
              {running && <Loader2 className="mr-1 h-4 w-4 animate-spin" aria-hidden="true" />}
              記録
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
