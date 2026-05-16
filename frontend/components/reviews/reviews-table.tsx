"use client";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CheckCircle2 } from "lucide-react";

type RiskLevel = "low" | "medium" | "high" | "critical";
interface ReviewItem { id: string; contractId: string; contractTitle: string; aiModel: string; riskLevel: RiskLevel; issuesCount: number; status: string; reviewerConfirmed: boolean; completedAt: string | null; }
interface Props { items: ReviewItem[]; total: number; page: number; perPage: number; }

const STATUS_LABEL: Record<string, string> = { completed: "完了", in_progress: "レビュー中", pending_confirmation: "確認待ち" };
const STATUS_V: Record<string, "default" | "secondary" | "outline"> = { completed: "default", in_progress: "secondary", pending_confirmation: "outline" };
const RISK_LABEL: Record<RiskLevel, string> = { low: "低", medium: "中", high: "高", critical: "重大" };
const RISK_V: Record<RiskLevel, "outline" | "secondary" | "destructive"> = { low: "outline", medium: "secondary", high: "destructive", critical: "destructive" };

export function ReviewsTable({ items, total }: Props) {
  if (!items.length) return <p className="py-12 text-center text-sm text-muted-foreground">レビューが見つかりません</p>;
  return (
    <div className="space-y-2">
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-28">ID</TableHead>
              <TableHead>契約名</TableHead>
              <TableHead className="w-24">ステータス</TableHead>
              <TableHead className="w-16">リスク</TableHead>
              <TableHead className="w-16 text-center">指摘</TableHead>
              <TableHead className="w-20 text-center">確認済</TableHead>
              <TableHead className="w-24">完了日</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map(r => (
              <TableRow key={r.id} className="cursor-pointer hover:bg-muted/50">
                <TableCell className="font-mono text-xs">{r.id}</TableCell>
                <TableCell><Link href={`/reviews/${r.id}`} className="font-medium hover:underline line-clamp-1">{r.contractTitle}</Link></TableCell>
                <TableCell className="whitespace-nowrap"><Badge variant={STATUS_V[r.status] ?? "outline"}>{STATUS_LABEL[r.status] ?? r.status}</Badge></TableCell>
                <TableCell className="whitespace-nowrap"><Badge variant={RISK_V[r.riskLevel]}>{RISK_LABEL[r.riskLevel]}</Badge></TableCell>
                <TableCell className="text-center text-sm font-semibold">{r.issuesCount}</TableCell>
                <TableCell className="text-center">{r.reviewerConfirmed && <CheckCircle2 className="mx-auto h-4 w-4 text-emerald-500" />}</TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">{r.completedAt ?? "—"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <p className="text-xs text-muted-foreground">{total} 件</p>
    </div>
  );
}
export default ReviewsTable;
