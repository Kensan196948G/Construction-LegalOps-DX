"use client";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ExternalLink } from "lucide-react";

type WfStatus = "in_progress" | "approved" | "rejected" | "returned" | "withdrawn";
interface WfItem { id: string; contractId: string; contractTitle: string; route: string; currentStep: string; waitingFor: string; status: WfStatus; requiresOutsideCounsel: boolean; dueDate: string | null; updatedAt: string; }
interface Props { items: WfItem[]; total: number; page: number; perPage: number; }

const STATUS_LABEL: Record<WfStatus, string> = { in_progress: "審査中", approved: "承認済み", rejected: "否決", returned: "差戻し", withdrawn: "取下げ" };
const STATUS_V: Record<WfStatus, "default" | "secondary" | "destructive" | "outline"> = { in_progress: "secondary", approved: "default", rejected: "destructive", returned: "outline", withdrawn: "outline" };

export function WorkflowsTable({ items, total }: Props) {
  if (!items.length) return <p className="py-12 text-center text-sm text-muted-foreground">ワークフローが見つかりません</p>;
  return (
    <div className="space-y-2">
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-24">ID</TableHead>
              <TableHead>契約名</TableHead>
              <TableHead className="w-16 text-center">ルート</TableHead>
              <TableHead className="w-32">現在のステップ</TableHead>
              <TableHead className="w-28">担当者</TableHead>
              <TableHead className="w-24">ステータス</TableHead>
              <TableHead className="w-24">期限</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map(w => (
              <TableRow key={w.id} className="cursor-pointer hover:bg-muted/50">
                <TableCell className="font-mono text-xs">{w.id}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-1.5">
                    <Link href={`/workflows/${w.id}`} className="font-medium hover:underline line-clamp-1 max-w-xs">{w.contractTitle}</Link>
                    {w.requiresOutsideCounsel && <ExternalLink className="h-3 w-3 shrink-0 text-amber-500" aria-label="弁護士確認必要" />}
                  </div>
                </TableCell>
                <TableCell className="text-center"><Badge variant="outline" className="font-mono">{w.route}</Badge></TableCell>
                <TableCell className="text-sm">{w.currentStep}</TableCell>
                <TableCell className="text-sm text-muted-foreground">{w.waitingFor}</TableCell>
                <TableCell><Badge variant={STATUS_V[w.status]}>{STATUS_LABEL[w.status]}</Badge></TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">{w.dueDate ?? "—"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <p className="text-xs text-muted-foreground">{total} 件</p>
    </div>
  );
}
export default WorkflowsTable;
