"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Building2, Loader2, RefreshCw, ShieldAlert } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import { partnersApi, partnerExtApi } from "@/lib/api";
import type { Partner, PartnerExpiryFlags, PartnerRiskScore } from "@/lib/api/schemas";

const STATE_LABELS: Record<string, string> = {
  expired: "期限切れ",
  expiring: "期限接近",
  ok: "有効",
  unset: "未設定",
};

const STATE_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  expired: "destructive",
  expiring: "secondary",
  ok: "outline",
  unset: "outline",
};

const RISK_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  low: "outline",
  medium: "secondary",
  high: "destructive",
  critical: "destructive",
};

function StateBadge({ state }: { state: string }) {
  return (
    <Badge variant={STATE_VARIANT[state] ?? "outline"}>
      {STATE_LABELS[state] ?? state}
    </Badge>
  );
}

export default function PartnerRiskPage() {
  const [alerts, setAlerts] = useState<PartnerExpiryFlags[]>([]);
  const [partners, setPartners] = useState<Partner[]>([]);
  const [selectedPartnerId, setSelectedPartnerId] = useState("");
  const [riskScore, setRiskScore] = useState<PartnerRiskScore | null>(null);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [alertRows, partnerRows] = await Promise.all([
        partnerExtApi.alerts({ within_days: 60, size: 100 }),
        partnersApi.list({ page: 1, page_size: 200 }),
      ]);
      setAlerts(alertRows);
      setPartners(partnerRows.items);
      setOffline(false);
    } catch {
      setAlerts([]);
      setPartners([]);
      setOffline(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const showRiskScore = useCallback(async (partnerId: string) => {
    if (!partnerId) return;
    setActionError(null);
    try {
      const result = await partnerExtApi.riskScore(partnerId);
      setRiskScore(result);
    } catch (err) {
      setActionError(
        err instanceof Error ? `取得に失敗しました: ${err.message}` : "取得に失敗しました。"
      );
    }
  }, []);

  const refreshScore = async () => {
    if (!selectedPartnerId || refreshing) return;
    setRefreshing(true);
    setActionError(null);
    try {
      const result = await partnerExtApi.refreshRiskScore(selectedPartnerId);
      setRiskScore(result);
      await load();
    } catch (err) {
      setActionError(
        err instanceof Error ? `更新に失敗しました: ${err.message}` : "更新に失敗しました。"
      );
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-foreground">協力会社リスク</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          期限アラート（許可・保険・CCUS・再審査）と Partner Risk Score を管理します
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

      {/* #150 Risk Score ツール */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ShieldAlert className="h-4 w-4 text-primary" aria-hidden="true" />
            Partner Risk Score（#150・決定論的算出）
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-[280px] flex-1 space-y-2">
              <Label htmlFor="pr-partner">協力会社</Label>
              <Select value={selectedPartnerId} onValueChange={setSelectedPartnerId}>
                <SelectTrigger id="pr-partner" aria-label="協力会社">
                  <SelectValue placeholder="協力会社を選択" />
                </SelectTrigger>
                <SelectContent>
                  {partners.map((p) => (
                    <SelectItem key={String(p.id)} value={String(p.id)}>
                      {p.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button
              variant="outline"
              onClick={() => void showRiskScore(selectedPartnerId)}
              disabled={!selectedPartnerId}
              className="gap-2"
            >
              <Building2 className="h-4 w-4" aria-hidden="true" />
              取得
            </Button>
            <Button
              onClick={() => void refreshScore()}
              disabled={!selectedPartnerId || refreshing}
              className="gap-2"
            >
              {refreshing ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <RefreshCw className="h-4 w-4" aria-hidden="true" />
              )}
              算出・保存
            </Button>
          </div>

          {riskScore && (
            <div
              className={`rounded-md border p-4 ${
                riskScore.risk_level === "critical" || riskScore.risk_level === "high"
                  ? "border-red-300 bg-red-50 dark:border-red-800 dark:bg-red-950/30"
                  : "border-green-300 bg-green-50 dark:border-green-800 dark:bg-green-950/30"
              }`}
            >
              <div className="flex items-center gap-2">
                <Badge variant={RISK_VARIANT[riskScore.risk_level] ?? "outline"}>
                  {riskScore.risk_level}
                </Badge>
                <p className="text-sm font-semibold">
                  {riskScore.partner_name} — Score {riskScore.risk_score}/100
                </p>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                期限切れ {riskScore.expiry_overdue_count} 件・基準判定 {riskScore.base_level}
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* #138/#146/#151 期限アラート */}
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-2 border-b px-6 py-4">
          <p className="text-sm font-semibold">
            期限アラート（許可・保険・CCUS・定期再審査 / #138・#146・#151）
          </p>
          <Button variant="outline" size="icon" onClick={() => void load()} aria-label="再読み込み">
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>協力会社</TableHead>
              <TableHead className="w-36">建設業許可</TableHead>
              <TableHead className="w-36">保険証券</TableHead>
              <TableHead className="w-36">CCUS</TableHead>
              <TableHead className="w-36">定期再審査</TableHead>
              <TableHead className="w-24">Risk Score</TableHead>
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
            ) : alerts.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="py-10 text-center text-sm text-muted-foreground">
                  期限アラート対象の協力会社はありません。
                </TableCell>
              </TableRow>
            ) : (
              alerts.map((a) => (
                <TableRow key={String(a.partner_id)}>
                  <TableCell className="text-sm font-medium">{a.partner_name}</TableCell>
                  <TableCell>
                    <StateBadge state={a.permit_state} />
                    {a.permit_expiry && (
                      <span className="ml-1 text-xs text-muted-foreground">{a.permit_expiry}</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <StateBadge state={a.insurance_state} />
                    {a.insurance_expiry && (
                      <span className="ml-1 text-xs text-muted-foreground">
                        {a.insurance_expiry}
                      </span>
                    )}
                  </TableCell>
                  <TableCell>
                    <StateBadge state={a.ccus_state} />
                    {a.ccus_expiry && (
                      <span className="ml-1 text-xs text-muted-foreground">{a.ccus_expiry}</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <StateBadge state={a.review_state} />
                    {a.next_review_due && (
                      <span className="ml-1 text-xs text-muted-foreground">
                        {a.next_review_due}
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-sm">
                    {a.risk_score !== null && a.risk_score !== undefined ? a.risk_score : "—"}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}
