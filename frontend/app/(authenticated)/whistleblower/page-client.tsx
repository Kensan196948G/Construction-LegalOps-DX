"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, Loader2, Lock, Plus, RefreshCw, ShieldAlert } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, whistleblowerApi } from "@/lib/api";
import { useCurrentUser } from "@/hooks/use-users";
import type {
  WhistleblowerAction,
  WhistleblowerActionCategory,
  WhistleblowerAggregate,
  WhistleblowerCaseAccess,
  WhistleblowerCategory,
  WhistleblowerEvidence,
  WhistleblowerEvidenceType,
  WhistleblowerInterview,
  WhistleblowerIntervieweeType,
  WhistleblowerReport,
  WhistleblowerReporterProfile,
  WhistleblowerSeverity,
  WhistleblowerTimelineEvent,
} from "@/lib/api/schemas";

// 管理者・監査ロールは調査担当者 ACL 無しでも全件アクセス可（バックエンドと同義）。
const PRIVILEGED_ROLES = new Set(["admin", "auditor"]);

const CATEGORY_LABELS: Record<string, string> = {
  harassment: "ハラスメント",
  compliance: "コンプライアンス違反",
  safety: "安全衛生",
  labor: "労務",
  corruption: "汚職・談合",
  fraud: "不正経理",
  other: "その他",
};

const STATUS_LABELS: Record<string, string> = {
  received: "受付",
  triage: "一次評価中",
  investigating: "調査中",
  corrective_action: "是正措置中",
  closed: "完了",
  dismissed: "却下",
};

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  received: "outline",
  triage: "secondary",
  investigating: "default",
  corrective_action: "default",
  closed: "secondary",
  dismissed: "destructive",
};

const SEVERITY_LABELS: Record<string, string> = {
  low: "低",
  medium: "中",
  high: "高",
  critical: "重大",
};

const NEXT_STATUSES = ["received", "triage", "investigating", "corrective_action", "closed", "dismissed"];

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "-";
  try {
    return new Date(value).toLocaleString("ja-JP", { dateStyle: "medium", timeStyle: "short" });
  } catch {
    return value;
  }
}

interface CreateForm {
  category: WhistleblowerCategory;
  title: string;
  description: string;
  severity: WhistleblowerSeverity;
  is_anonymous: boolean;
  reporter_name: string;
  contact_email: string;
}

const EMPTY_FORM: CreateForm = {
  category: "harassment",
  title: "",
  description: "",
  severity: "medium",
  is_anonymous: false,
  reporter_name: "",
  contact_email: "",
};

interface EvidenceForm {
  evidence_type: WhistleblowerEvidenceType;
  description: string;
}

interface InterviewForm {
  interviewee_type: WhistleblowerIntervieweeType;
  summary: string;
}

interface ActionForm {
  action_category: WhistleblowerActionCategory;
  title: string;
}

export default function WhistleblowerPage() {
  const { data: currentUser } = useCurrentUser();
  const isPrivileged = !!currentUser && PRIVILEGED_ROLES.has(currentUser.role);

  const [rows, setRows] = useState<WhistleblowerReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState<CreateForm>(EMPTY_FORM);

  // 詳細
  const [detail, setDetail] = useState<WhistleblowerReport | null>(null);
  const [detailForbidden, setDetailForbidden] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [reporterProfile, setReporterProfile] = useState<WhistleblowerReporterProfile | null>(null);
  const [reporterForbidden, setReporterForbidden] = useState(false);
  const [access, setAccess] = useState<WhistleblowerCaseAccess[]>([]);
  const [evidence, setEvidence] = useState<WhistleblowerEvidence[]>([]);
  const [interviews, setInterviews] = useState<WhistleblowerInterview[]>([]);
  const [timeline, setTimeline] = useState<WhistleblowerTimelineEvent[]>([]);
  const [actions, setActions] = useState<WhistleblowerAction[]>([]);

  const [grantUserId, setGrantUserId] = useState("");
  const [evidenceForm, setEvidenceForm] = useState<EvidenceForm>({
    evidence_type: "email",
    description: "",
  });
  const [interviewForm, setInterviewForm] = useState<InterviewForm>({
    interviewee_type: "witness",
    summary: "",
  });
  const [actionForm, setActionForm] = useState<ActionForm>({
    action_category: "corrective",
    title: "",
  });

  const [aggregate, setAggregate] = useState<WhistleblowerAggregate | null>(null);
  const [aggregateOpen, setAggregateOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await whistleblowerApi.list({ page: 1, size: 100 });
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

  const openDetail = async (report: WhistleblowerReport) => {
    setDetail(report);
    setDetailForbidden(false);
    setReporterProfile(null);
    setReporterForbidden(false);
    setAccess([]);
    setEvidence([]);
    setInterviews([]);
    setTimeline([]);
    setActions([]);
    setDetailLoading(true);
    try {
      const fresh = await whistleblowerApi.get(report.id);
      setDetail(fresh);
    } catch (err) {
      if (err instanceof ApiError && err.isForbidden()) {
        setDetailForbidden(true);
        setDetailLoading(false);
        return;
      }
    }

    // 通報者情報は最重要の隔離対象。403 は「権限なし」として明示し、握りつぶさない。
    try {
      const profile = await whistleblowerApi.getReporterProfile(report.id);
      setReporterProfile(profile);
    } catch (err) {
      if (err instanceof ApiError && err.isForbidden()) {
        setReporterForbidden(true);
      }
    }

    try {
      const [accessRows, evidenceRows, interviewRows, timelineRows, actionRows] = await Promise.all([
        whistleblowerApi.listAccess(report.id),
        whistleblowerApi.listEvidence(report.id),
        whistleblowerApi.listInterviews(report.id),
        whistleblowerApi.listTimeline(report.id),
        whistleblowerApi.listActions(report.id),
      ]);
      setAccess(accessRows);
      setEvidence(evidenceRows);
      setInterviews(interviewRows);
      setTimeline(timelineRows);
      setActions(actionRows);
    } catch {
      /* 個別取得失敗時は空のまま表示 */
    } finally {
      setDetailLoading(false);
    }
  };

  const refreshDetail = useCallback(async (reportId: number | string) => {
    try {
      const [updated, evidenceRows, interviewRows, timelineRows, actionRows] = await Promise.all([
        whistleblowerApi.get(reportId),
        whistleblowerApi.listEvidence(reportId),
        whistleblowerApi.listInterviews(reportId),
        whistleblowerApi.listTimeline(reportId),
        whistleblowerApi.listActions(reportId),
      ]);
      setDetail(updated);
      setRows((prev) => prev.map((r) => (String(r.id) === String(reportId) ? updated : r)));
      setEvidence(evidenceRows);
      setInterviews(interviewRows);
      setTimeline(timelineRows);
      setActions(actionRows);
    } catch {
      /* ignore */
    }
  }, []);

  const createReport = async () => {
    if (!form.title.trim() || !form.description.trim() || creating) return;
    setCreating(true);
    setActionError(null);
    try {
      const created = await whistleblowerApi.create({
        category: form.category,
        title: form.title.trim(),
        description: form.description.trim(),
        severity: form.severity,
        is_anonymous: form.is_anonymous,
        reporter_name: form.is_anonymous ? null : form.reporter_name || null,
        contact_email: form.is_anonymous ? null : form.contact_email || null,
        consent_identity_disclosure: false,
      });
      setRows((prev) => [created, ...prev]);
      setCreateOpen(false);
      setForm(EMPTY_FORM);
    } catch (err) {
      setActionError(
        err instanceof Error ? `通報の登録に失敗しました: ${err.message}` : "通報の登録に失敗しました。",
      );
    } finally {
      setCreating(false);
    }
  };

  const changeStatus = async (report: WhistleblowerReport, status: string) => {
    setActionError(null);
    try {
      await whistleblowerApi.setStatus(report.id, { status });
      await refreshDetail(report.id);
    } catch (err) {
      setActionError(
        err instanceof Error ? `状態変更に失敗しました: ${err.message}` : "状態変更に失敗しました。",
      );
    }
  };

  const promote = async (report: WhistleblowerReport) => {
    setActionError(null);
    try {
      await whistleblowerApi.promoteToMatter(report.id);
      await refreshDetail(report.id);
    } catch (err) {
      setActionError(
        err instanceof Error ? `Matter 連携に失敗しました: ${err.message}` : "Matter 連携に失敗しました。",
      );
    }
  };

  const grantAccess = async (report: WhistleblowerReport) => {
    if (!grantUserId.trim()) return;
    setActionError(null);
    try {
      await whistleblowerApi.grantAccess(report.id, {
        user_id: grantUserId.trim(),
        role_in_case: "investigator",
        can_view_reporter_identity: true,
      });
      setGrantUserId("");
      const accessRows = await whistleblowerApi.listAccess(report.id);
      setAccess(accessRows);
    } catch (err) {
      setActionError(
        err instanceof Error ? `ACL 付与に失敗しました: ${err.message}` : "ACL 付与に失敗しました。",
      );
    }
  };

  const revokeAccess = async (report: WhistleblowerReport, grantId: number | string) => {
    setActionError(null);
    try {
      await whistleblowerApi.revokeAccess(report.id, grantId);
      const accessRows = await whistleblowerApi.listAccess(report.id);
      setAccess(accessRows);
    } catch (err) {
      setActionError(
        err instanceof Error ? `ACL 失効に失敗しました: ${err.message}` : "ACL 失効に失敗しました。",
      );
    }
  };

  const addEvidence = async (report: WhistleblowerReport) => {
    setActionError(null);
    try {
      await whistleblowerApi.addEvidence(report.id, {
        evidence_type: evidenceForm.evidence_type,
        description: evidenceForm.description || null,
        preserved: true,
      });
      setEvidenceForm({ evidence_type: "email", description: "" });
      await refreshDetail(report.id);
    } catch (err) {
      setActionError(
        err instanceof Error ? `証拠の登録に失敗しました: ${err.message}` : "証拠の登録に失敗しました。",
      );
    }
  };

  const addInterview = async (report: WhistleblowerReport) => {
    setActionError(null);
    try {
      await whistleblowerApi.addInterview(report.id, {
        interviewee_type: interviewForm.interviewee_type,
        conducted_at: new Date().toISOString(),
        summary: interviewForm.summary || null,
      });
      setInterviewForm({ interviewee_type: "witness", summary: "" });
      await refreshDetail(report.id);
    } catch (err) {
      setActionError(
        err instanceof Error
          ? `ヒアリング記録の登録に失敗しました: ${err.message}`
          : "ヒアリング記録の登録に失敗しました。",
      );
    }
  };

  const addAction = async (report: WhistleblowerReport) => {
    if (!actionForm.title.trim()) return;
    setActionError(null);
    try {
      await whistleblowerApi.addAction(report.id, {
        action_category: actionForm.action_category,
        title: actionForm.title.trim(),
      });
      setActionForm({ action_category: "corrective", title: "" });
      await refreshDetail(report.id);
    } catch (err) {
      setActionError(
        err instanceof Error ? `措置の登録に失敗しました: ${err.message}` : "措置の登録に失敗しました。",
      );
    }
  };

  const completeAction = async (report: WhistleblowerReport, actionId: number | string) => {
    setActionError(null);
    try {
      await whistleblowerApi.updateActionStatus(report.id, actionId, { status: "completed" });
      await refreshDetail(report.id);
    } catch (err) {
      setActionError(
        err instanceof Error ? `措置の更新に失敗しました: ${err.message}` : "措置の更新に失敗しました。",
      );
    }
  };

  const openAggregate = async () => {
    setAggregateOpen(true);
    try {
      const result = await whistleblowerApi.aggregate();
      setAggregate(result);
    } catch {
      setAggregate(null);
    }
  };

  const rowCount = useMemo(() => rows.length, [rows]);

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">内部通報・調査</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            内部通報の受付・調査担当者限定アクセス・証拠保全・ヒアリング・是正措置を管理します。
          </p>
          <p className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
            <Lock className="h-3 w-3" aria-hidden="true" />
            通報者を特定できる情報は、案件ごとに付与された調査担当者と管理者/監査ロールのみが閲覧できます。
          </p>
        </div>
        <div className="flex gap-2">
          {isPrivileged && (
            <Button variant="outline" onClick={() => void openAggregate()} className="gap-2">
              <ShieldAlert className="h-4 w-4" aria-hidden="true" />
              経営報告匿名集計
            </Button>
          )}
          <Button variant="outline" onClick={() => void load()} className="gap-2">
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            更新
          </Button>
          <Button onClick={() => setCreateOpen(true)} className="gap-2">
            <Plus className="h-4 w-4" aria-hidden="true" />
            通報を登録
          </Button>
        </div>
      </header>

      {!isPrivileged && (
        <Alert>
          <AlertDescription>
            一覧には、あなたが調査担当者として割り当てられている案件のみ表示されます。
          </AlertDescription>
        </Alert>
      )}

      {offline && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" aria-hidden="true" />
          <AlertDescription>データを取得できませんでした。時間をおいて再度お試しください。</AlertDescription>
        </Alert>
      )}

      {actionError && (
        <Alert variant="destructive">
          <AlertDescription>{actionError}</AlertDescription>
        </Alert>
      )}

      <Card className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>通報番号</TableHead>
              <TableHead>カテゴリ</TableHead>
              <TableHead>タイトル</TableHead>
              <TableHead>状態</TableHead>
              <TableHead>重大度</TableHead>
              <TableHead>匿名</TableHead>
              <TableHead>受付日時</TableHead>
              <TableHead>操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={8} className="py-8 text-center text-muted-foreground">
                  <Loader2 className="mx-auto h-5 w-5 animate-spin" aria-hidden="true" />
                </TableCell>
              </TableRow>
            ) : rowCount === 0 ? (
              <TableRow>
                <TableCell colSpan={8} className="py-8 text-center text-muted-foreground">
                  表示できる通報がありません。
                </TableCell>
              </TableRow>
            ) : (
              rows.map((r) => (
                <TableRow key={String(r.id)}>
                  <TableCell className="font-mono text-xs">{r.report_no}</TableCell>
                  <TableCell>{CATEGORY_LABELS[r.category] ?? r.category}</TableCell>
                  <TableCell className="max-w-[280px] truncate">{r.title}</TableCell>
                  <TableCell>
                    <Badge variant={STATUS_VARIANT[r.status] ?? "outline"}>
                      {STATUS_LABELS[r.status] ?? r.status}
                    </Badge>
                  </TableCell>
                  <TableCell>{SEVERITY_LABELS[r.severity] ?? r.severity}</TableCell>
                  <TableCell>{r.is_anonymous ? "匿名" : "実名"}</TableCell>
                  <TableCell>{formatDateTime(r.received_at)}</TableCell>
                  <TableCell>
                    {/* M17（CodeRabbit）: TableRow の onClick はキーボード操作不可のため、
                        フォーカス可能なボタンで詳細を開けるようにする。 */}
                    <Button size="sm" variant="ghost" onClick={() => void openDetail(r)}>
                      詳細
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Card>

      {/* 通報登録ダイアログ */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>内部通報を登録</DialogTitle>
            <DialogDescription>
              匿名通報を選択すると、通報者を特定できる情報は一切保存されません。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label htmlFor="wb-category">カテゴリ</Label>
              <Select
                value={form.category}
                onValueChange={(v) =>
                  setForm((f) => ({ ...f, category: v as WhistleblowerCategory }))
                }
              >
                <SelectTrigger id="wb-category">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
                    <SelectItem key={value} value={value}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="wb-title">タイトル</Label>
              <Input
                id="wb-title"
                value={form.title}
                onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              />
            </div>
            <div>
              <Label htmlFor="wb-description">詳細内容</Label>
              <Textarea
                id="wb-description"
                rows={4}
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              />
            </div>
            <div>
              <Label htmlFor="wb-severity">重大度</Label>
              <Select
                value={form.severity}
                onValueChange={(v) =>
                  setForm((f) => ({ ...f, severity: v as WhistleblowerSeverity }))
                }
              >
                <SelectTrigger id="wb-severity">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(SEVERITY_LABELS).map(([value, label]) => (
                    <SelectItem key={value} value={value}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.is_anonymous}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    is_anonymous: e.target.checked,
                    reporter_name: e.target.checked ? "" : f.reporter_name,
                    contact_email: e.target.checked ? "" : f.contact_email,
                  }))
                }
              />
              匿名で通報する（通報者情報を一切登録しない）
            </label>
            {!form.is_anonymous && (
              <>
                <div>
                  <Label htmlFor="wb-reporter-name">通報者氏名（任意）</Label>
                  <Input
                    id="wb-reporter-name"
                    value={form.reporter_name}
                    onChange={(e) => setForm((f) => ({ ...f, reporter_name: e.target.value }))}
                  />
                </div>
                <div>
                  <Label htmlFor="wb-reporter-email">連絡先メール（任意）</Label>
                  <Input
                    id="wb-reporter-email"
                    type="email"
                    value={form.contact_email}
                    onChange={(e) => setForm((f) => ({ ...f, contact_email: e.target.value }))}
                  />
                </div>
              </>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              キャンセル
            </Button>
            <Button
              onClick={() => void createReport()}
              disabled={creating || !form.title.trim() || !form.description.trim()}
            >
              {creating ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : "登録"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 詳細ダイアログ */}
      <Dialog open={!!detail} onOpenChange={(open) => !open && setDetail(null)}>
        <DialogContent className="max-w-3xl">
          {detail && (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  {detail.report_no}
                  <Badge variant={STATUS_VARIANT[detail.status] ?? "outline"}>
                    {STATUS_LABELS[detail.status] ?? detail.status}
                  </Badge>
                </DialogTitle>
                <DialogDescription>{detail.title}</DialogDescription>
              </DialogHeader>

              {detailForbidden ? (
                <Alert variant="destructive">
                  <ShieldAlert className="h-4 w-4" aria-hidden="true" />
                  <AlertDescription>
                    この案件へのアクセス権がありません（調査担当者限定）。
                  </AlertDescription>
                </Alert>
              ) : detailLoading ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
                </div>
              ) : (
                <Tabs defaultValue="overview" className="w-full">
                  <TabsList className="flex flex-wrap">
                    <TabsTrigger value="overview">概要</TabsTrigger>
                    <TabsTrigger value="reporter">通報者情報</TabsTrigger>
                    <TabsTrigger value="access">調査担当 ACL</TabsTrigger>
                    <TabsTrigger value="evidence">証拠保全</TabsTrigger>
                    <TabsTrigger value="interviews">ヒアリング</TabsTrigger>
                    <TabsTrigger value="actions">是正・再発防止</TabsTrigger>
                    <TabsTrigger value="timeline">タイムライン</TabsTrigger>
                  </TabsList>

                  <TabsContent value="overview" className="space-y-3">
                    <p className="text-sm">{detail.description}</p>
                    <div className="flex flex-wrap gap-2">
                      {NEXT_STATUSES.map((s) => (
                        <Button
                          key={s}
                          size="sm"
                          variant={detail.status === s ? "default" : "outline"}
                          disabled={detail.status === s}
                          onClick={() => void changeStatus(detail, s)}
                        >
                          {STATUS_LABELS[s]}
                        </Button>
                      ))}
                    </div>
                    <div>
                      {detail.matter_id ? (
                        <p className="text-sm text-muted-foreground">
                          Matter 連携済み（matter_id: {String(detail.matter_id)}）
                        </p>
                      ) : (
                        <Button size="sm" variant="outline" onClick={() => void promote(detail)}>
                          Investigative Matter へ昇格
                        </Button>
                      )}
                    </div>
                  </TabsContent>

                  <TabsContent value="reporter" className="space-y-2">
                    {detail.is_anonymous ? (
                      <Alert>
                        <AlertDescription>匿名通報のため、通報者情報は保存されていません。</AlertDescription>
                      </Alert>
                    ) : reporterForbidden ? (
                      <Alert variant="destructive">
                        <Lock className="h-4 w-4" aria-hidden="true" />
                        <AlertDescription>
                          通報者情報は調査担当者（識別情報閲覧権限あり）のみ閲覧できます。
                        </AlertDescription>
                      </Alert>
                    ) : reporterProfile ? (
                      <div className="space-y-1 text-sm">
                        <p>氏名: {reporterProfile.reporter_name ?? "未登録"}</p>
                        <p>連絡先メール: {reporterProfile.contact_email ?? "未登録"}</p>
                        <p>連絡先電話: {reporterProfile.contact_phone ?? "未登録"}</p>
                        <p>所属: {reporterProfile.department ?? "未登録"}</p>
                      </div>
                    ) : (
                      <p className="text-sm text-muted-foreground">通報者情報は登録されていません。</p>
                    )}
                  </TabsContent>

                  <TabsContent value="access" className="space-y-3">
                    {isPrivileged && (
                      <div className="flex items-end gap-2">
                        <div className="flex-1">
                          <Label htmlFor="wb-grant-user">調査担当者に付与する user id</Label>
                          <Input
                            id="wb-grant-user"
                            value={grantUserId}
                            onChange={(e) => setGrantUserId(e.target.value)}
                          />
                        </div>
                        <Button onClick={() => void grantAccess(detail)}>付与</Button>
                      </div>
                    )}
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>ユーザー</TableHead>
                          <TableHead>役割</TableHead>
                          <TableHead>識別情報閲覧</TableHead>
                          <TableHead>状態</TableHead>
                          {isPrivileged && <TableHead />}
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {access.map((a) => (
                          <TableRow key={String(a.id)}>
                            <TableCell>{String(a.user_id)}</TableCell>
                            <TableCell>{a.role_in_case}</TableCell>
                            <TableCell>{a.can_view_reporter_identity ? "可" : "不可"}</TableCell>
                            <TableCell>{a.revoked_at ? "失効済み" : "有効"}</TableCell>
                            {isPrivileged && (
                              <TableCell>
                                {!a.revoked_at && (
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    onClick={() => void revokeAccess(detail, a.id)}
                                  >
                                    失効
                                  </Button>
                                )}
                              </TableCell>
                            )}
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TabsContent>

                  <TabsContent value="evidence" className="space-y-3">
                    <div className="flex items-end gap-2">
                      <Select
                        value={evidenceForm.evidence_type}
                        onValueChange={(v) =>
                          setEvidenceForm((f) => ({
                            ...f,
                            evidence_type: v as WhistleblowerEvidenceType,
                          }))
                        }
                      >
                        <SelectTrigger className="w-40">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="document">文書</SelectItem>
                          <SelectItem value="email">メール</SelectItem>
                          <SelectItem value="photo">写真</SelectItem>
                          <SelectItem value="recording">録音・録画</SelectItem>
                          <SelectItem value="testimony">証言</SelectItem>
                          <SelectItem value="system_log">システムログ</SelectItem>
                          <SelectItem value="other">その他</SelectItem>
                        </SelectContent>
                      </Select>
                      <Input
                        placeholder="説明"
                        value={evidenceForm.description}
                        onChange={(e) =>
                          setEvidenceForm((f) => ({ ...f, description: e.target.value }))
                        }
                      />
                      <Button onClick={() => void addEvidence(detail)}>登録</Button>
                    </div>
                    <ul className="space-y-1 text-sm">
                      {evidence.map((e) => (
                        <li key={String(e.id)} className="rounded border p-2">
                          [{e.evidence_type}] {e.description ?? "(説明なし)"}{" "}
                          {e.preserved && <Badge variant="secondary">保全済み</Badge>}
                        </li>
                      ))}
                    </ul>
                  </TabsContent>

                  <TabsContent value="interviews" className="space-y-3">
                    <div className="flex items-end gap-2">
                      <Select
                        value={interviewForm.interviewee_type}
                        onValueChange={(v) =>
                          setInterviewForm((f) => ({
                            ...f,
                            interviewee_type: v as WhistleblowerIntervieweeType,
                          }))
                        }
                      >
                        <SelectTrigger className="w-40">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="reporter">通報者本人</SelectItem>
                          <SelectItem value="witness">参考人</SelectItem>
                          <SelectItem value="subject">被通報者</SelectItem>
                          <SelectItem value="other">その他</SelectItem>
                        </SelectContent>
                      </Select>
                      <Input
                        placeholder="ヒアリング概要"
                        value={interviewForm.summary}
                        onChange={(e) =>
                          setInterviewForm((f) => ({ ...f, summary: e.target.value }))
                        }
                      />
                      <Button onClick={() => void addInterview(detail)}>登録</Button>
                    </div>
                    <ul className="space-y-1 text-sm">
                      {interviews.map((i) => (
                        <li key={String(i.id)} className="rounded border p-2">
                          [{i.interviewee_type}] {i.summary ?? "(概要なし)"} —{" "}
                          {formatDateTime(i.conducted_at)}
                        </li>
                      ))}
                    </ul>
                  </TabsContent>

                  <TabsContent value="actions" className="space-y-3">
                    <div className="flex items-end gap-2">
                      <Select
                        value={actionForm.action_category}
                        onValueChange={(v) =>
                          setActionForm((f) => ({
                            ...f,
                            action_category: v as WhistleblowerActionCategory,
                          }))
                        }
                      >
                        <SelectTrigger className="w-40">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="corrective">是正措置</SelectItem>
                          <SelectItem value="preventive">再発防止策</SelectItem>
                        </SelectContent>
                      </Select>
                      <Input
                        placeholder="タイトル"
                        value={actionForm.title}
                        onChange={(e) => setActionForm((f) => ({ ...f, title: e.target.value }))}
                      />
                      <Button onClick={() => void addAction(detail)}>登録</Button>
                    </div>
                    <ul className="space-y-1 text-sm">
                      {actions.map((a) => (
                        <li
                          key={String(a.id)}
                          className="flex items-center justify-between rounded border p-2"
                        >
                          <span>
                            [{a.action_category === "corrective" ? "是正措置" : "再発防止"}] {a.title}{" "}
                            <Badge variant="outline">{a.status}</Badge>
                          </span>
                          {a.status !== "completed" && a.status !== "verified" && (
                            <Button size="sm" variant="ghost" onClick={() => void completeAction(detail, a.id)}>
                              完了にする
                            </Button>
                          )}
                        </li>
                      ))}
                    </ul>
                  </TabsContent>

                  <TabsContent value="timeline" className="space-y-2">
                    <ul className="space-y-1 text-sm">
                      {timeline.map((t) => (
                        <li key={String(t.id)} className="rounded border p-2">
                          <span className="font-medium">{t.event_type}</span>
                          {t.note && <span> — {t.note}</span>}
                          <span className="ml-2 text-xs text-muted-foreground">
                            {formatDateTime(t.created_at)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </TabsContent>
                </Tabs>
              )}
            </>
          )}
        </DialogContent>
      </Dialog>

      {/* 経営報告匿名集計ダイアログ */}
      <Dialog open={aggregateOpen} onOpenChange={setAggregateOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>経営報告匿名集計</DialogTitle>
            <DialogDescription>個人・通報者を特定できる情報は含まれません。</DialogDescription>
          </DialogHeader>
          {aggregate ? (
            <div className="space-y-2 text-sm">
              <p>総件数: {aggregate.total}</p>
              <p>匿名通報件数: {aggregate.anonymous_count}</p>
              <p>事実確認済み件数: {aggregate.substantiated_count}</p>
              <p>却下件数: {aggregate.dismissed_count}</p>
              <p>平均解決日数: {aggregate.avg_days_to_close ?? "-"}</p>
              <div>
                <p className="font-medium">カテゴリ別</p>
                <ul>
                  {Object.entries(aggregate.by_category).map(([k, v]) => (
                    <li key={k}>
                      {CATEGORY_LABELS[k] ?? k}: {v}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              集計を取得できませんでした（admin/auditor 限定機能です）。
            </p>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
