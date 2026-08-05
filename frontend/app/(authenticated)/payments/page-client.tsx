"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { CalendarClock, RefreshCw, ShieldAlert } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import { contractsApi, paymentComplianceApi } from "@/lib/api";
import type { Contract, PaymentCompliance } from "@/lib/api/schemas";
import { AiDisclaimerBanner } from "@/components/layout/ai-disclaimer-banner";
import { formatCurrency } from "@/lib/utils/format-currency";

const SEVERITY_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  block: "destructive",
  warn: "secondary",
  info: "outline",
};

const SEVERITY_LABELS: Record<string, string> = {
  block: "必須対応",
  warn: "要確認",
  info: "情報",
};

export default function PaymentsPage() {
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [result, setResult] = useState<PaymentCompliance | null>(null);
  const [loading, setLoading] = useState(false);
  const [offline, setOffline] = useState(false);

  const loadContracts = useCallback(async () => {
    try {
      const list = await contractsApi.list({ page: 1, size: 100 });
      setContracts(list.items);
      setOffline(false);
    } catch {
      setOffline(true);
    }
  }, []);

  useEffect(() => {
    void loadContracts();
  }, [loadContracts]);

  const runCheck = useCallback(async (contractId: string) => {
    setLoading(true);
    try {
      const check = await paymentComplianceApi.check(contractId);
      setResult(check);
      setOffline(false);
    } catch {
      setOffline(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedId) {
      void runCheck(selectedId);
    } else {
      setResult(null);
    }
  }, [selectedId, runCheck]);

  const blockCount = result?.findings.filter((f) => f.severity === "block").length ?? 0;
  const warnCount = result?.findings.filter((f) => f.severity === "warn").length ?? 0;

  const selectedContract = useMemo(
    () => contracts.find((c) => String(c.id) === selectedId),
    [contracts, selectedId],
  );

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-foreground">支払・検収コンプライアンス</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            発注日・受領日・検収日・支払日から取適法（旧下請法）60 日ルール・手形払い禁止等を判定します
          </p>
        </div>
      </header>

      <AiDisclaimerBanner variant="inline" />

      {offline && (
        <Badge variant="outline" className="border-amber-400 bg-amber-50 text-amber-800 dark:bg-amber-950">
          API 未接続（バックエンド起動後に自動再接続）
        </Badge>
      )}

      <Card>
        <CardHeader>
          <CardTitle>判定対象契約</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap items-end gap-3">
          <div className="min-w-72 flex-1">
            <Select value={selectedId} onValueChange={setSelectedId}>
              <SelectTrigger>
                <SelectValue placeholder="契約を選択" />
              </SelectTrigger>
              <SelectContent>
                {contracts.map((c) => (
                  <SelectItem key={String(c.id)} value={String(c.id)}>
                    {c.contract_no} — {c.title}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button
            variant="outline"
            onClick={() => selectedId && void runCheck(selectedId)}
            disabled={!selectedId || loading}
          >
            <RefreshCw className={`mr-1 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            再判定
          </Button>
        </CardContent>
      </Card>

      {result && (
        <>
          <div className="grid grid-cols-3 gap-4">
            <Card>
              <CardContent className="flex items-center gap-3 pt-4">
                <CalendarClock className="h-8 w-8 text-primary" />
                <div>
                  <p className="text-2xl font-bold">{result.applicable_threshold_days} 日</p>
                  <p className="text-sm text-muted-foreground">
                    適用支払期限（{result.law_version}）
                  </p>
                </div>
              </CardContent>
            </Card>
            <Card className={blockCount > 0 ? "border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950/30" : ""}>
              <CardContent className="flex items-center gap-3 pt-4">
                <ShieldAlert className="h-8 w-8 text-destructive" />
                <div>
                  <p className="text-2xl font-bold">{blockCount}</p>
                  <p className="text-sm text-muted-foreground">必須対応（BLOCK）</p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="flex items-center gap-3 pt-4">
                <div>
                  <p className="text-2xl font-bold">{warnCount}</p>
                  <p className="text-sm text-muted-foreground">要確認（WARN）</p>
                </div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0">
              <CardTitle>
                判定結果 — {selectedContract?.contract_no ?? `契約 #${result.contract_id}`}
              </CardTitle>
              <Badge
                variant={
                  result.overall_status === "block"
                    ? "destructive"
                    : result.overall_status === "warn"
                      ? "secondary"
                      : "default"
                }
              >
                {result.overall_status === "pass"
                  ? "適合"
                  : result.overall_status === "warn"
                    ? "要確認"
                    : "不適合"}
              </Badge>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
                <div>
                  <p className="text-muted-foreground">発注日</p>
                  <p className="font-medium">{result.order_date ?? "—"}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">受領日</p>
                  <p className="font-medium">{result.receipt_date ?? "—"}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">検収日</p>
                  <p className="font-medium">{result.inspection_date ?? "—"}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">支払日</p>
                  <p className="font-medium">{result.payment_date ?? "—"}</p>
                </div>
              </div>
              {result.days_receipt_to_payment !== null &&
                result.days_receipt_to_payment !== undefined && (
                  <p className="text-sm">
                    受領→支払: <span className="font-semibold">{result.days_receipt_to_payment} 日</span>
                    {result.days_receipt_to_payment > result.applicable_threshold_days && (
                      <Badge variant="destructive" className="ml-2">
                        期限超過
                      </Badge>
                    )}
                  </p>
                )}
              {Number(result.late_interest_jpy) > 0 && (
                <p className="text-sm">
                  遅延利息（概算）: <span className="font-semibold">{formatCurrency(Number(result.late_interest_jpy))}</span>
                </p>
              )}
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-40">コード</TableHead>
                      <TableHead className="w-28">重大度</TableHead>
                      <TableHead>指摘内容</TableHead>
                      <TableHead className="w-64">根拠</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {result.findings.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={4} className="py-8 text-center text-sm text-muted-foreground">
                          指摘なし
                        </TableCell>
                      </TableRow>
                    ) : (
                      result.findings.map((f, i) => (
                        <TableRow key={`${f.code}-${i}`}>
                          <TableCell className="font-mono text-xs">{f.code}</TableCell>
                          <TableCell>
                            <Badge variant={SEVERITY_VARIANT[f.severity] ?? "outline"}>
                              {SEVERITY_LABELS[f.severity] ?? f.severity}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <p className="text-sm font-medium">{f.title}</p>
                            <p className="text-xs text-muted-foreground">{f.description}</p>
                          </TableCell>
                          <TableCell className="text-xs text-muted-foreground">{f.citation}</TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </>
      )}

      {!selectedId && !offline && (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            判定したい契約を選択してください
          </CardContent>
        </Card>
      )}
    </div>
  );
}
