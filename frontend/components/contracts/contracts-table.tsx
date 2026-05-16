"use client";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";

type RiskLevel = "low" | "medium" | "high" | "critical";
interface ContractItem { id: string; title: string; counterparty: string; contractType: string; amount: number | null; status: string; riskLevel: RiskLevel; updatedAt: string; }
interface Props { items: ContractItem[]; total: number; page: number; perPage: number; }

const STATUS_LABEL: Record<string, string> = { draft: "下書き", in_review: "レビュー中", approved: "承認済み", pending_approval: "承認待ち", expired: "期限切れ", archived: "アーカイブ" };
const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = { draft: "outline", in_review: "secondary", approved: "default", pending_approval: "secondary", expired: "destructive", archived: "outline" };
const RISK_LABEL: Record<RiskLevel, string> = { low: "低", medium: "中", high: "高", critical: "重大" };
const RISK_VARIANT: Record<RiskLevel, "default" | "secondary" | "destructive" | "outline"> = { low: "outline", medium: "secondary", high: "destructive", critical: "destructive" };

function fmtYen(n: number | null) { return n === null ? "—" : "¥" + n.toLocaleString("ja-JP"); }

export function ContractsTable({ items, total, page, perPage }: Props) {
  if (!items.length) return <p className="py-12 text-center text-sm text-muted-foreground">契約が見つかりません</p>;
  const totalPages = Math.ceil(total / perPage);
  return (
    <div className="space-y-3">
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>契約名</TableHead>
              <TableHead className="w-36">取引先</TableHead>
              <TableHead className="w-28">種別</TableHead>
              <TableHead className="w-24">ステータス</TableHead>
              <TableHead className="w-20">リスク</TableHead>
              <TableHead className="w-28 text-right">金額</TableHead>
              <TableHead className="w-24">更新日</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map(c => (
              <TableRow key={c.id} className="cursor-pointer hover:bg-muted/50">
                <TableCell>
                  <Link href={`/contracts/${c.id}`} className="font-medium hover:underline line-clamp-1">{c.title}</Link>
                </TableCell>
                <TableCell className="text-sm text-muted-foreground truncate max-w-[140px]">{c.counterparty}</TableCell>
                <TableCell className="text-xs text-muted-foreground">{c.contractType}</TableCell>
                <TableCell className="whitespace-nowrap"><Badge variant={STATUS_VARIANT[c.status] ?? "outline"}>{STATUS_LABEL[c.status] ?? c.status}</Badge></TableCell>
                <TableCell className="whitespace-nowrap"><Badge variant={RISK_VARIANT[c.riskLevel]}>{RISK_LABEL[c.riskLevel]}</Badge></TableCell>
                <TableCell className="text-right font-mono text-sm">{fmtYen(c.amount)}</TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">{c.updatedAt}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{total} 件中 {(page - 1) * perPage + 1}–{Math.min(page * perPage, total)} 件表示</span>
        {totalPages > 1 && (
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" disabled={page <= 1} asChild={page > 1}>
              {page > 1 ? <Link href={`?page=${page - 1}`}>前へ</Link> : <span>前へ</span>}
            </Button>
            <span>{page} / {totalPages}</span>
            <Button variant="outline" size="sm" disabled={page >= totalPages} asChild={page < totalPages}>
              {page < totalPages ? <Link href={`?page=${page + 1}`}>次へ</Link> : <span>次へ</span>}
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
export default ContractsTable;
