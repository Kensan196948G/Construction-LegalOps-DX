"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Building2,
  Handshake,
  Loader2,
  Plus,
  RefreshCw,
  Swords,
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
import { contractsApi, jvApi } from "@/lib/api";
import type { Contract, Jv, JvMember } from "@/lib/api/schemas";

const JV_STATUS_LABELS: Record<string, string> = {
  prospecting: "検討中",
  active: "活動中",
  completed: "完了・清算済",
  dissolved: "解散",
};

const JV_STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  prospecting: "outline",
  active: "default",
  completed: "secondary",
  dissolved: "destructive",
};

const MEMBER_ROLE_LABELS: Record<string, string> = {
  representative: "代表会社",
  member: "構成員",
};

export default function JvPage() {
  const [rows, setRows] = useState<Jv[]>([]);
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("all");

  // 詳細（構成員・協定書・紛争・清算）
  const [detail, setDetail] = useState<Jv | null>(null);
  const [members, setMembers] = useState<JvMember[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);

  // JV 登録
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    name: "",
    representative_name: "",
    works_title: "",
    contract_id: "",
    start_date: "",
    end_date: "",
  });

  // 構成員追加
  const [memberOpen, setMemberOpen] = useState(false);
  const [memberSaving, setMemberSaving] = useState(false);
  const [memberForm, setMemberForm] = useState({
    company_name: "",
    role: "member",
    equity_ratio: "",
  });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [jvResult, contractResult] = await Promise.all([
        jvApi.list({ page: 1, size: 100 }),
        contractsApi.list({ page: 1, page_size: 200 }),
      ]);
      setRows(jvResult.items);
      setContracts(contractResult.items);
      setOffline(false);
    } catch {
      setRows([]);
      setContracts([]);
      setOffline(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const openDetail = useCallback(async (jv: Jv) => {
    setDetail(jv);
    setDetailLoading(true);
    try {
      const memberRows = await jvApi.members(jv.id);
      setMembers(memberRows);
    } catch {
      setMembers([]);
    } finally {
      setDetailLoading(false);
    }
  }, []);

  const refreshDetail = useCallback(async (jvId: number | string) => {
    try {
      const [updated, memberRows] = await Promise.all([
        jvApi.get(jvId),
        jvApi.members(jvId),
      ]);
      setDetail(updated);
      setRows((prev) => prev.map((r) => (String(r.id) === String(jvId) ? updated : r)));
      setMembers(memberRows);
    } catch {
      /* ignore */
    }
  }, []);

  const filtered = useMemo(
    () => (statusFilter === "all" ? rows : rows.filter((r) => r.status === statusFilter)),
    [rows, statusFilter]
  );

  const createJv = async () => {
    if (!form.name.trim() || creating) return;
    setCreating(true);
    setActionError(null);
    try {
      await jvApi.create({
        name: form.name.trim(),
        representative_name: form.representative_name || null,
        works_title: form.works_title || null,
        contract_id: form.contract_id || null,
        start_date: form.start_date || null,
        end_date: form.end_date || null,
      });
      setCreateOpen(false);
      setForm({
        name: "",
        representative_name: "",
        works_title: "",
        contract_id: "",
        start_date: "",
        end_date: "",
      });
      await load();
    } catch (err) {
      setActionError(
        err instanceof Error ? `作成に失敗しました: ${err.message}` : "作成に失敗しました。"
      );
    } finally {
      setCreating(false);
    }
  };

  const changeStatus = async (jv: Jv, status: string) => {
    setActionError(null);
    try {
      await jvApi.setStatus(jv.id, { status });
      if (detail && String(detail.id) === String(jv.id)) {
        await refreshDetail(jv.id);
      } else {
        await load();
      }
    } catch (err) {
      setActionError(
        err instanceof Error ? `状態変更に失敗しました: ${err.message}` : "状態変更に失敗しました。"
      );
    }
  };

  const addMember = async () => {
    if (!detail || !memberForm.company_name.trim() || memberSaving) return;
    setMemberSaving(true);
    setActionError(null);
    try {
      await jvApi.addMember(detail.id, {
        company_name: memberForm.company_name.trim(),
        role: memberForm.role,
        equity_ratio: memberForm.equity_ratio ? Number(memberForm.equity_ratio) : null,
      });
      setMemberOpen(false);
      setMemberForm({ company_name: "", role: "member", equity_ratio: "" });
      await refreshDetail(detail.id);
    } catch (err) {
      setActionError(
        err instanceof Error ? `構成員追加に失敗しました: ${err.message}` : "追加に失敗しました。"
      );
    } finally {
      setMemberSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">JV 管理</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            共同企業体の台帳・構成員・出資比率・協定書・清算を管理します
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)} className="gap-2">
          <Plus className="h-4 w-4" aria-hidden="true" />
          JV を登録
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

      <Card>
        <div className="flex items-center justify-between border-b px-6 py-4">
          <p className="text-sm font-semibold">JV 台帳（#61）</p>
          <div className="flex items-center gap-2">
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-36" aria-label="状態で絞り込み">
                <SelectValue placeholder="状態" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">すべての状態</SelectItem>
                {Object.entries(JV_STATUS_LABELS).map(([value, label]) => (
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
              <TableHead className="w-32">JV No</TableHead>
              <TableHead>JV 名</TableHead>
              <TableHead className="w-32">代表会社</TableHead>
              <TableHead className="w-20">状態</TableHead>
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
            ) : filtered.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="py-10 text-center text-sm text-muted-foreground">
                  JV が登録されていません。「JV を登録」から作成してください。
                </TableCell>
              </TableRow>
            ) : (
              filtered.map((jv) => (
                <TableRow key={String(jv.id)}>
                  <TableCell className="whitespace-nowrap font-mono text-sm">
                    {jv.jv_no}
                  </TableCell>
                  <TableCell className="max-w-[260px]">
                    <p className="truncate text-sm font-medium">{jv.name}</p>
                    {jv.works_title && (
                      <p className="truncate text-xs text-muted-foreground">{jv.works_title}</p>
                    )}
                  </TableCell>
                  <TableCell className="text-sm">{jv.representative_name ?? "—"}</TableCell>
                  <TableCell>
                    <Badge variant={JV_STATUS_VARIANT[jv.status] ?? "outline"}>
                      {JV_STATUS_LABELS[jv.status] ?? jv.status}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Button variant="ghost" size="sm" onClick={() => void openDetail(jv)}>
                      詳細
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Card>

      {/* JV 登録ダイアログ */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>JV を登録（#61）</DialogTitle>
            <DialogDescription>
              JV 番号は JV-YYYY-NNNNNN 形式で自動採番されます。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="jv-name">JV 名（必須）</Label>
              <Input
                id="jv-name"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="例: ◯◯工事共同企業体"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="jv-rep">代表会社名（任意）</Label>
              <Input
                id="jv-rep"
                value={form.representative_name}
                onChange={(e) =>
                  setForm((f) => ({ ...f, representative_name: e.target.value }))
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="jv-works">対象工事名（任意）</Label>
              <Input
                id="jv-works"
                value={form.works_title}
                onChange={(e) => setForm((f) => ({ ...f, works_title: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="jv-contract">関連契約（任意）</Label>
              <Select
                value={form.contract_id}
                onValueChange={(v) => setForm((f) => ({ ...f, contract_id: v }))}
              >
                <SelectTrigger id="jv-contract" aria-label="関連契約">
                  <SelectValue placeholder="選択（未指定で可）" />
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
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              キャンセル
            </Button>
            <Button onClick={() => void createJv()} disabled={!form.name.trim() || creating}>
              {creating && <Loader2 className="mr-1 h-4 w-4 animate-spin" aria-hidden="true" />}
              登録
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* JV 詳細ダイアログ */}
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
                  <Handshake className="h-5 w-5 text-primary" aria-hidden="true" />
                  {detail.name}
                </DialogTitle>
                <DialogDescription>
                  {detail.jv_no} / {JV_STATUS_LABELS[detail.status] ?? detail.status}
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-5">
                {/* 状態遷移 */}
                <div className="flex flex-wrap items-center gap-2 rounded-md border p-3">
                  <span className="text-xs font-semibold text-muted-foreground">状態:</span>
                  {Object.entries(JV_STATUS_LABELS).map(([value, label]) => (
                    <Button
                      key={value}
                      size="sm"
                      variant={detail.status === value ? "default" : "outline"}
                      onClick={() => void changeStatus(detail, value)}
                      disabled={detail.status === value}
                    >
                      {label}
                    </Button>
                  ))}
                </div>

                {/* 構成員 */}
                <div>
                  <div className="mb-2 flex items-center justify-between">
                    <p className="flex items-center gap-1 text-sm font-semibold">
                      <Building2 className="h-4 w-4" aria-hidden="true" />
                      構成員・出資比率（#63/#64）
                    </p>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setMemberOpen(true)}
                      className="gap-1"
                    >
                      <Plus className="h-3 w-3" aria-hidden="true" />
                      構成員を追加
                    </Button>
                  </div>
                  {detailLoading ? (
                    <div className="flex items-center justify-center py-4">
                      <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
                    </div>
                  ) : members.length === 0 ? (
                    <p className="text-sm text-muted-foreground">構成員がいません。</p>
                  ) : (
                    <ul className="space-y-1">
                      {members.map((m) => (
                        <li
                          key={String(m.id)}
                          className="flex flex-wrap items-center gap-2 rounded-md border px-3 py-2 text-sm"
                        >
                          <Badge variant={m.role === "representative" ? "default" : "outline"}>
                            {MEMBER_ROLE_LABELS[m.role] ?? m.role}
                          </Badge>
                          <span className="font-medium">{m.company_name}</span>
                          <span className="ml-auto text-muted-foreground">
                            出資 {m.equity_ratio !== null && m.equity_ratio !== undefined ? `${m.equity_ratio}%` : "—"}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                {/* 協定書・紛争・清算（API は実装済み・詳細操作は一覧画面から） */}
                <p className="flex items-center gap-1 text-xs text-muted-foreground">
                  <Swords className="h-3 w-3" aria-hidden="true" />
                  協定書・内紛争・清算の操作は API（/joint-ventures/{String(detail.id)}/…）から実行できます
                </p>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>

      {/* 構成員追加ダイアログ */}
      <Dialog open={memberOpen} onOpenChange={setMemberOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>構成員を追加（#63/#64）</DialogTitle>
            <DialogDescription>
              代表会社は 1 社のみ。出資比率の合計は 100% 以内にしてください。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="jvm-company">会社名（必須）</Label>
              <Input
                id="jvm-company"
                value={memberForm.company_name}
                onChange={(e) =>
                  setMemberForm((f) => ({ ...f, company_name: e.target.value }))
                }
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="jvm-role">役割</Label>
                <Select
                  value={memberForm.role}
                  onValueChange={(v) => setMemberForm((f) => ({ ...f, role: v }))}
                >
                  <SelectTrigger id="jvm-role" aria-label="役割">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="representative">代表会社</SelectItem>
                    <SelectItem value="member">構成員</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="jvm-equity">出資比率（%）</Label>
                <Input
                  id="jvm-equity"
                  type="number"
                  min={0}
                  max={100}
                  value={memberForm.equity_ratio}
                  onChange={(e) =>
                    setMemberForm((f) => ({ ...f, equity_ratio: e.target.value }))
                  }
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setMemberOpen(false)}>
              キャンセル
            </Button>
            <Button
              onClick={() => void addMember()}
              disabled={!memberForm.company_name.trim() || memberSaving}
            >
              {memberSaving && (
                <Loader2 className="mr-1 h-4 w-4 animate-spin" aria-hidden="true" />
              )}
              追加
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
