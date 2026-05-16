"use client";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

type RiskLevel = "low" | "medium" | "high" | "critical";
type RiskStatus = "open" | "mitigated" | "accepted" | "closed";
interface RiskItem { id: string; contractId: string; contractTitle: string; category: string; level: RiskLevel; score: number; description: string; status: RiskStatus; owner: string | null; detectedAt: string; }
interface Props { items: RiskItem[]; total: number; page: number; perPage: number; }

const RISK_LABEL: Record<RiskLevel, string> = { low: "低", medium: "中", high: "高", critical: "重大" };
const RISK_V: Record<RiskLevel, "outline" | "secondary" | "destructive"> = { low: "outline", medium: "secondary", high: "destructive", critical: "destructive" };
const STATUS_LABEL: Record<RiskStatus, string> = { open: "未対応", mitigated: "軽減済み", accepted: "受容", closed: "解消" };
const STATUS_V: Record<RiskStatus, "destructive" | "secondary" | "outline" | "default"> = { open: "destructive", mitigated: "default", accepted: "secondary", closed: "outline" };

export function RisksTable({ items, total }: Props) {
  if (!items.length) return <p className="py-12 text-center text-sm text-muted-foreground">リスクが見つかりません</p>;
  return (
    <div className="space-y-2">
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-24">ID</TableHead>
              <TableHead>説明</TableHead>
              <TableHead className="w-28">カテゴリ</TableHead>
              <TableHead className="w-20">レベル</TableHead>
              <TableHead className="w-14 text-center">スコア</TableHead>
              <TableHead className="w-24">状態</TableHead>
              <TableHead className="w-24">担当者</TableHead>
              <TableHead className="w-24">検出日</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map(r => (
              <TableRow key={r.id} className="hover:bg-muted/50">
                <TableCell className="font-mono text-xs">{r.id}</TableCell>
                <TableCell>
                  <div>
                    <Link href={`/contracts/${r.contractId}`} className="text-xs text-muted-foreground hover:underline">{r.contractTitle}</Link>
                    <p className="mt-0.5 text-sm truncate max-w-xs">{r.description}</p>
                  </div>
                </TableCell>
                <TableCell className="text-xs">{r.category}</TableCell>
                <TableCell><Badge variant={RISK_V[r.level]}>{RISK_LABEL[r.level]}</Badge></TableCell>
                <TableCell className="text-center font-bold text-sm">{r.score}</TableCell>
                <TableCell><Badge variant={STATUS_V[r.status]}>{STATUS_LABEL[r.status]}</Badge></TableCell>
                <TableCell className="text-sm">{r.owner ?? "—"}</TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">{r.detectedAt}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <p className="text-xs text-muted-foreground">{total} 件</p>
    </div>
  );
}
export default RisksTable;
