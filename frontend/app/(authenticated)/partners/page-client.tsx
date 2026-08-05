"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, Building2, RefreshCw, Search, ShieldCheck } from "lucide-react";

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
import { partnersApi } from "@/lib/api";
import type { Partner, PartnerSummary } from "@/lib/api/schemas";
import { AiDisclaimerBanner } from "@/components/layout/ai-disclaimer-banner";
import { PARTNERS, type RiskLevel } from "@/lib/mock-data";

const RISK_VARIANT: Record<RiskLevel, "default" | "secondary" | "destructive" | "outline"> = {
  low: "outline",
  medium: "secondary",
  high: "destructive",
  critical: "destructive",
};

const RISK_LABELS: Record<RiskLevel, string> = {
  low: "低",
  medium: "中",
  high: "高",
  critical: "重大",
};

const TYPE_LABELS = ["元請", "下請", "専門工事", "材料", "輸送", "その他"];

const PARTNER_TYPES = Array.from(new Set(PARTNERS.map((p) => p.type)));

interface PartnerRow {
  id: string;
  name: string;
  type: string;
  permitNumber: string;
  permitExpiry: string;
  antiSocialCheck: string;
  insurance: string;
  riskLevel: RiskLevel;
  lastTransaction: string;
}

function toRow(p: Partner): PartnerRow {
  return {
    id: String(p.id),
    name: p.name,
    type: p.partner_type,
    permitNumber: p.permit_number ?? "—",
    permitExpiry: p.permit_expiry ?? "—",
    antiSocialCheck: p.anti_social_check === "confirmed" ? "確認済" : p.anti_social_check === "pending" ? "確認中" : "未確認",
    insurance: p.social_insurance_joined === true ? "加入済" : p.social_insurance_joined === false ? "未加入" : "未確認",
    riskLevel: (p.risk_level as RiskLevel) ?? "low",
    lastTransaction: p.last_transaction ?? "—",
  };
}

function toMockRow(p: (typeof PARTNERS)[number]): PartnerRow {
  return {
    id: p.id,
    name: p.name,
    type: p.type,
    permitNumber: p.permitNumber,
    permitExpiry: p.permitExpiry,
    antiSocialCheck: p.antiSocialCheck,
    insurance: p.insurance,
    riskLevel: p.riskLevel,
    lastTransaction: p.lastTransaction,
  };
}

export default function PartnersPage() {
  const [rows, setRows] = useState<PartnerRow[]>(() => PARTNERS.map(toMockRow));
  const [summary, setSummary] = useState<PartnerSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [riskFilter, setRiskFilter] = useState<"all" | RiskLevel>("all");
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState({
    name: "",
    partner_type: "下請",
    permit_number: "",
    permit_expiry: "",
    social_insurance_joined: "unknown",
    anti_social_check: "unconfirmed",
    risk_level: "low",
    notes: "",
  });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [list, sum] = await Promise.all([
        partnersApi.list({ page: 1, size: 100 }),
        partnersApi.summary(),
      ]);
      setRows(list.items.map(toRow));
      setSummary(sum);
      setOffline(false);
    } catch {
      setRows(PARTNERS.map(toMockRow));
      setOffline(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const filtered = useMemo(() => {
    return rows.filter((p) => {
      if (search && !p.name.includes(search) && !p.permitNumber.includes(search)) return false;
      if (typeFilter !== "all" && p.type !== typeFilter) return false;
      if (riskFilter !== "all" && p.riskLevel !== riskFilter) return false;
      return true;
    });
  }, [rows, search, typeFilter, riskFilter]);

  const unverified = summary?.antisocial_unconfirmed ??
    rows.filter((p) => p.antiSocialCheck === "未確認").length;
  const expiringPermit = summary?.permit_expiring_within_90d ??
    rows.filter((p) => {
      if (p.permitExpiry === "—") return false;
      const days = Math.ceil(
        (new Date(p.permitExpiry.replace(/\//g, "-")).getTime() - new Date("2026-05-16").getTime()) /
          86400000,
      );
      return days <= 90;
    }).length;
  const highRisk = rows.filter((p) => p.riskLevel === "high" || p.riskLevel === "critical").length;

  const createPartner = async () => {
    try {
      const created = await partnersApi.create({
        name: form.name,
        partner_type: form.partner_type as Partner["partner_type"],
        permit_number: form.permit_number || undefined,
        permit_expiry: form.permit_expiry || undefined,
        social_insurance_joined:
          form.social_insurance_joined === "unknown" ? undefined : form.social_insurance_joined === "yes",
        anti_social_check: form.anti_social_check as Partner["anti_social_check"],
        risk_level: form.risk_level as Partner["risk_level"],
        notes: form.notes || undefined,
      });
      setRows((prev) => [toRow(created), ...prev]);
      setCreateOpen(false);
      setForm({
        name: "",
        partner_type: "下請",
        permit_number: "",
        permit_expiry: "",
        social_insurance_joined: "unknown",
        anti_social_check: "unconfirmed",
        risk_level: "low",
        notes: "",
      });
    } catch {
      setOffline(true);
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-foreground">取引先・協力会社管理</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            建設業許可・社会保険・CCUS・反社確認・リスクを一元管理します
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>協力会社登録</Button>
      </header>

      <AiDisclaimerBanner variant="inline" />

      {offline && (
        <Badge variant="outline" className="border-amber-400 bg-amber-50 text-amber-800 dark:bg-amber-950">
          オフライン表示（モックデータ）
        </Badge>
      )}

      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardContent className="flex items-center gap-3 pt-4">
            <Building2 className="h-8 w-8 text-primary" />
            <div>
              <p className="text-2xl font-bold">{loading ? "—" : summary?.total ?? rows.length}</p>
              <p className="text-sm text-muted-foreground">登録会社数</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 pt-4">
            <ShieldCheck className="h-8 w-8 text-destructive" />
            <div>
              <p className="text-2xl font-bold">{loading ? "—" : unverified}</p>
              <p className="text-sm text-muted-foreground">反社確認 未確認</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 pt-4">
            <AlertTriangle className="h-8 w-8 text-amber-500" />
            <div>
              <p className="text-2xl font-bold">{loading ? "—" : expiringPermit}</p>
              <p className="text-sm text-muted-foreground">許可期限 90日以内</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 pt-4">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-destructive/10">
              <span className="text-lg font-bold text-destructive">!</span>
            </div>
            <div>
              <p className="text-2xl font-bold">{loading ? "—" : highRisk}</p>
              <p className="text-sm text-muted-foreground">高リスク会社</p>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle>協力会社一覧</CardTitle>
          <Button variant="ghost" size="sm" onClick={() => void load()} disabled={loading}>
            <RefreshCw className={`mr-1 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            更新
          </Button>
        </CardHeader>
        <CardContent>
          <div className="mb-4 flex flex-wrap gap-3">
            <div className="relative min-w-48 flex-1">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="会社名・許可番号で検索"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-8"
              />
            </div>
            <Select value={typeFilter} onValueChange={setTypeFilter}>
              <SelectTrigger className="w-40">
                <SelectValue placeholder="種別" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">すべての種別</SelectItem>
                {[...new Set([...PARTNER_TYPES, ...TYPE_LABELS])].map((t) => (
                  <SelectItem key={t} value={t}>{t}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={riskFilter} onValueChange={(v) => setRiskFilter(v as "all" | RiskLevel)}>
              <SelectTrigger className="w-32">
                <SelectValue placeholder="リスク" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">すべて</SelectItem>
                {Object.entries(RISK_LABELS).map(([v, l]) => (
                  <SelectItem key={v} value={v}>{l}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>会社名</TableHead>
                  <TableHead className="w-28">種別</TableHead>
                  <TableHead className="w-52">建設業許可番号</TableHead>
                  <TableHead className="w-28">許可期限</TableHead>
                  <TableHead className="w-24">反社確認</TableHead>
                  <TableHead className="w-20">社会保険</TableHead>
                  <TableHead className="w-20">リスク</TableHead>
                  <TableHead className="w-24">最終取引</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={8} className="py-10 text-center text-sm text-muted-foreground">
                      該当する協力会社がありません
                    </TableCell>
                  </TableRow>
                ) : (
                  filtered.map((p) => (
                    <TableRow key={p.id}>
                      <TableCell className="text-sm font-medium">{p.name}</TableCell>
                      <TableCell className="text-sm">{p.type}</TableCell>
                      <TableCell className="max-w-[220px] truncate font-mono text-xs">{p.permitNumber}</TableCell>
                      <TableCell className="text-sm whitespace-nowrap">
                        {p.permitExpiry === "—" ? "—" : p.permitExpiry}
                      </TableCell>
                      <TableCell className="text-sm whitespace-nowrap">{p.antiSocialCheck}</TableCell>
                      <TableCell className="text-sm whitespace-nowrap">{p.insurance}</TableCell>
                      <TableCell>
                        <Badge variant={RISK_VARIANT[p.riskLevel] ?? "outline"}>
                          {RISK_LABELS[p.riskLevel] ?? p.riskLevel}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm whitespace-nowrap">{p.lastTransaction}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>協力会社登録</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3">
            <div>
              <Label>会社名 *</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>種別</Label>
                <Select value={form.partner_type} onValueChange={(v) => setForm({ ...form, partner_type: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {TYPE_LABELS.map((t) => (
                      <SelectItem key={t} value={t}>{t}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>リスク</Label>
                <Select value={form.risk_level} onValueChange={(v) => setForm({ ...form, risk_level: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {Object.entries(RISK_LABELS).map(([v, l]) => (
                      <SelectItem key={v} value={v}>{l}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>建設業許可番号</Label>
                <Input value={form.permit_number} onChange={(e) => setForm({ ...form, permit_number: e.target.value })} />
              </div>
              <div>
                <Label>許可期限</Label>
                <Input type="date" value={form.permit_expiry} onChange={(e) => setForm({ ...form, permit_expiry: e.target.value })} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>社会保険加入</Label>
                <Select
                  value={form.social_insurance_joined}
                  onValueChange={(v) => setForm({ ...form, social_insurance_joined: v })}
                >
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="unknown">未確認</SelectItem>
                    <SelectItem value="yes">加入済</SelectItem>
                    <SelectItem value="no">未加入</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>反社確認</Label>
                <Select value={form.anti_social_check} onValueChange={(v) => setForm({ ...form, anti_social_check: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="confirmed">確認済</SelectItem>
                    <SelectItem value="unconfirmed">未確認</SelectItem>
                    <SelectItem value="pending">確認中</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div>
              <Label>備考</Label>
              <Input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>キャンセル</Button>
            <Button onClick={() => void createPartner()} disabled={!form.name}>登録</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
