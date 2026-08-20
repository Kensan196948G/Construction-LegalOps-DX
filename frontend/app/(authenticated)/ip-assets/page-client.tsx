"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ExternalLink,
  FileText,
  Plus,
  RefreshCw,
  Search,
  Sparkles,
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
import { ipAssetsApi, ipDashboardApi } from "@/lib/api";
import type { IpAsset, IpDashboard, IpDocument } from "@/lib/api/schemas";
import { AiDisclaimerBanner } from "@/components/layout/ai-disclaimer-banner";

const IP_TYPE_LABELS: Record<string, string> = {
  patent: "特許",
  design: "意匠",
  trademark: "商標",
};

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  登録: "default",
  拒絶理由通知: "destructive",
  拒絶査定: "destructive",
  出願: "secondary",
  公開: "secondary",
  審査請求: "secondary",
};

interface MockAsset {
  id: string;
  application_number: string;
  ip_type: string;
  invention_title: string;
  status: string;
  filing_date: string;
  registration_number?: string;
}

const MOCK_ASSETS: MockAsset[] = [
  {
    id: "1",
    application_number: "2026000001",
    ip_type: "patent",
    invention_title: "建設現場の安全管理システム（デモ）",
    status: "登録",
    filing_date: "2026-01-15",
    registration_number: "7000001",
  },
  {
    id: "2",
    application_number: "2026000002",
    ip_type: "patent",
    invention_title: "建設機械の遠隔監視装置（デモ）",
    status: "審査請求",
    filing_date: "2026-02-10",
  },
  {
    id: "3",
    application_number: "2026000003",
    ip_type: "patent",
    invention_title: "コンクリート養生管理方法（デモ・競合）",
    status: "拒絶理由通知",
    filing_date: "2026-03-05",
  },
];

function toMockAsset(a: MockAsset): IpAsset {
  return {
    id: a.id,
    application_number: a.application_number,
    ip_type: a.ip_type as IpAsset["ip_type"],
    invention_title: a.invention_title,
    status: a.status,
    filing_date: a.filing_date,
    registration_number: a.registration_number,
    applicants: [],
    progress_data: {},
    registration_data: {},
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
}

export default function IpAssetsPage() {
  const [rows, setRows] = useState<IpAsset[]>(() => MOCK_ASSETS.map(toMockAsset));
  const [dashboard, setDashboard] = useState<IpDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [createOpen, setCreateOpen] = useState(false);
  const [detail, setDetail] = useState<IpAsset | null>(null);
  const [documents, setDocuments] = useState<Record<string, IpDocument[]>>({});
  const [form, setForm] = useState({
    application_number: "",
    ip_type: "patent",
    notes: "",
  });
  const [busyId, setBusyId] = useState<number | string | null>(null);
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [list, dash] = await Promise.all([
        ipAssetsApi.list({ page: 1, size: 100 }),
        ipDashboardApi.get(),
      ]);
      setRows(list.items);
      setDashboard(dash);
      setOffline(false);
    } catch {
      setRows(MOCK_ASSETS.map(toMockAsset));
      setOffline(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const filtered = useMemo(() => {
    return rows.filter((a) => {
      if (
        search &&
        !a.application_number.includes(search) &&
        !(a.invention_title ?? "").includes(search)
      )
        return false;
      if (typeFilter !== "all" && a.ip_type !== typeFilter) return false;
      if (statusFilter !== "all" && a.status !== statusFilter) return false;
      return true;
    });
  }, [rows, search, typeFilter, statusFilter]);

  const createAsset = async () => {
    if (!form.application_number.trim()) return;
    try {
      const created = await ipAssetsApi.create({
        application_number: form.application_number.trim(),
        ip_type: form.ip_type as IpAsset["ip_type"],
        notes: form.notes || undefined,
      });
      setRows((prev) => [created, ...prev]);
      setCreateOpen(false);
      setForm({ application_number: "", ip_type: "patent", notes: "" });
      setMessage("出願を登録し、JPO API から経過情報を取得しました");
      setTimeout(() => setMessage(""), 5000);
    } catch {
      setOffline(true);
    }
  };

  const syncAsset = async (asset: IpAsset) => {
    setBusyId(asset.id);
    try {
      const result = await ipAssetsApi.sync(asset.id);
      await load();
      setMessage(result.message);
      setTimeout(() => setMessage(""), 5000);
    } catch {
      setOffline(true);
    } finally {
      setBusyId(null);
    }
  };

  const openDetail = async (asset: IpAsset) => {
    setDetail(asset);
    try {
      const docs = await ipAssetsApi.documents(asset.id);
      setDocuments((prev) => ({ ...prev, [String(asset.id)]: docs }));
    } catch {
      // 書類一覧はオフライン時は空のまま
    }
  };

  const statuses = useMemo(
    () => Array.from(new Set(rows.map((r) => r.status))),
    [rows]
  );

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-foreground">知財台帳</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            特許・意匠・商標の出願情報を JPO 特許情報取得 API と連携して一元管理します
          </p>
        </div>
        <div className="flex items-center gap-2">
          {dashboard && (
            <Badge variant="outline">
              JPO API: {dashboard.api_configured ? "live 接続" : "デモモード"}
            </Badge>
          )}
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="mr-2 h-4 w-4" /> 出願登録
          </Button>
        </div>
      </header>

      <AiDisclaimerBanner variant="inline" />

      {offline && (
        <Badge variant="outline" className="border-amber-400 bg-amber-50 text-amber-800 dark:bg-amber-950">
          オフライン表示（モックデータ）
        </Badge>
      )}
      {message && (
        <Badge variant="outline" className="border-emerald-400 bg-emerald-50 text-emerald-800 dark:bg-emerald-950">
          {message}
        </Badge>
      )}

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Card>
          <CardContent className="flex items-center gap-3 pt-4">
            <FileText className="h-8 w-8 text-primary" />
            <div>
              <p className="text-2xl font-bold">{loading ? "—" : dashboard?.total_assets ?? rows.length}</p>
              <p className="text-sm text-muted-foreground">登録出願</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 pt-4">
            <Sparkles className="h-8 w-8 text-primary" />
            <div>
              <p className="text-2xl font-bold">{loading ? "—" : dashboard?.by_status["登録"] ?? 0}</p>
              <p className="text-sm text-muted-foreground">登録済</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 pt-4">
            <RefreshCw className="h-8 w-8 text-primary" />
            <div>
              <p className="text-2xl font-bold">{loading ? "—" : dashboard?.by_status["拒絶理由通知"] ?? 0}</p>
              <p className="text-sm text-muted-foreground">拒絶理由通知</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 pt-4">
            <FileText className="h-8 w-8 text-primary" />
            <div>
              <p className="text-2xl font-bold">{loading ? "—" : dashboard?.documents_total ?? 0}</p>
              <p className="text-sm text-muted-foreground">審査書類</p>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">出願一覧</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <div className="relative flex-1 min-w-[220px]">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                className="pl-8"
                placeholder="出願番号・発明名称で検索"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <Select value={typeFilter} onValueChange={setTypeFilter}>
              <SelectTrigger className="w-[140px]">
                <SelectValue placeholder="種別" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全種別</SelectItem>
                <SelectItem value="patent">特許</SelectItem>
                <SelectItem value="design">意匠</SelectItem>
                <SelectItem value="trademark">商標</SelectItem>
              </SelectContent>
            </Select>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[160px]">
                <SelectValue placeholder="ステータス" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全ステータス</SelectItem>
                {statuses.map((s) => (
                  <SelectItem key={s} value={s}>
                    {s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>出願番号</TableHead>
                <TableHead>種別</TableHead>
                <TableHead>発明等の名称</TableHead>
                <TableHead>出願日</TableHead>
                <TableHead>登録番号</TableHead>
                <TableHead>ステータス</TableHead>
                <TableHead className="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((a) => (
                <TableRow key={a.id}>
                  <TableCell className="font-mono text-xs">{a.application_number}</TableCell>
                  <TableCell>{IP_TYPE_LABELS[a.ip_type] ?? a.ip_type}</TableCell>
                  <TableCell>
                    <button
                      className="text-left font-medium hover:underline"
                      onClick={() => void openDetail(a)}
                    >
                      {a.invention_title ?? "—"}
                    </button>
                  </TableCell>
                  <TableCell>{a.filing_date ?? "—"}</TableCell>
                  <TableCell className="font-mono text-xs">{a.registration_number ?? "—"}</TableCell>
                  <TableCell>
                    <Badge variant={STATUS_VARIANT[a.status] ?? "outline"}>{a.status}</Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => void syncAsset(a)}
                        disabled={busyId === a.id}
                      >
                        <RefreshCw className={`mr-1 h-3 w-3 ${busyId === a.id ? "animate-spin" : ""}`} />
                        同期
                      </Button>
                      {a.jplatpat_url && (
                        <Button variant="ghost" size="sm" asChild>
                          <a href={a.jplatpat_url} target="_blank" rel="noreferrer">
                            <ExternalLink className="h-3 w-3" />
                          </a>
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {filtered.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7} className="py-8 text-center text-muted-foreground">
                    該当する出願がありません
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* 登録ダイアログ */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>出願登録</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="application_number">出願番号</Label>
              <Input
                id="application_number"
                placeholder="例: 2026000001"
                value={form.application_number}
                onChange={(e) => setForm({ ...form, application_number: e.target.value })}
              />
              <p className="mt-1 text-xs text-muted-foreground">
                登録すると JPO 特許情報取得 API から経過情報・登録情報を自動取得します
              </p>
            </div>
            <div>
              <Label>権利種別</Label>
              <Select
                value={form.ip_type}
                onValueChange={(v) => setForm({ ...form, ip_type: v })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="種別" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="patent">特許</SelectItem>
                  <SelectItem value="design">意匠</SelectItem>
                  <SelectItem value="trademark">商標</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="notes">メモ</Label>
              <Textarea
                id="notes"
                placeholder="社内メモ（任意）"
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              キャンセル
            </Button>
            <Button onClick={() => void createAsset()}>登録して取得</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 詳細ダイアログ */}
      <Dialog open={detail !== null} onOpenChange={(open) => !open && setDetail(null)}>
        <DialogContent className="max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {detail?.invention_title ?? "出願詳細"}
              <span className="ml-2 text-sm font-normal text-muted-foreground">
                {detail?.application_number}
              </span>
            </DialogTitle>
          </DialogHeader>
          {detail && (
            <div className="space-y-4">
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline">{IP_TYPE_LABELS[detail.ip_type] ?? detail.ip_type}</Badge>
                <Badge variant={STATUS_VARIANT[detail.status] ?? "outline"}>{detail.status}</Badge>
                {detail.jplatpat_url && (
                  <Button variant="outline" size="sm" asChild>
                    <a href={detail.jplatpat_url} target="_blank" rel="noreferrer">
                      <ExternalLink className="mr-1 h-3 w-3" /> J-PlatPat
                    </a>
                  </Button>
                )}
              </div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>
                  <p className="text-muted-foreground">出願日</p>
                  <p>{detail.filing_date ?? "—"}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">公開番号</p>
                  <p className="font-mono text-xs">{detail.publication_number ?? "—"}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">登録番号</p>
                  <p className="font-mono text-xs">{detail.registration_number ?? "—"}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">最終同期</p>
                  <p className="text-xs">{detail.last_synced_at ? new Date(detail.last_synced_at).toLocaleString("ja-JP") : "—"}</p>
                </div>
              </div>
              {detail.applicants.length > 0 && (
                <div>
                  <p className="text-sm text-muted-foreground">申請人</p>
                  <ul className="mt-1 space-y-1 text-sm">
                    {detail.applicants.map((ap, i) => (
                      <li key={i}>
                        {ap.name ?? "—"}
                        <span className="ml-2 text-xs text-muted-foreground">
                          {ap.applicantAttorneyClass === "1" ? "出願人" : "代理人"}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <div>
                <p className="text-sm text-muted-foreground">審査書類</p>
                <div className="mt-1 space-y-1">
                  {(documents[detail.id] ?? []).length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      書類がありません。「審査書類」画面から収集できます
                    </p>
                  ) : (
                    (documents[String(detail.id)] ?? []).map((d, i) => (
                      <div key={i} className="text-sm">
                        {d.doc_name ?? "書類"}
                      </div>
                    ))
                  )}
                </div>
              </div>
              {detail.notes && (
                <div>
                  <p className="text-sm text-muted-foreground">メモ</p>
                  <p className="text-sm">{detail.notes}</p>
                </div>
              )}
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setDetail(null)}>
              閉じる
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
