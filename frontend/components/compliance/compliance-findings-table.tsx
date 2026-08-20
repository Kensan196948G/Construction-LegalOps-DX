"use client";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CheckCircle2, AlertTriangle, CircleDashed, XCircle } from "lucide-react";
import type { ComplianceFindingStatus } from "@/lib/compliance/status";

interface Finding { id: string; law: string; item: string; status: ComplianceFindingStatus; lastCheck: string; detail: string; }
interface Props { items: Finding[]; total: number; page: number; perPage: number; defaultFilters: { framework?: string; status?: string }; }

const STATUS_LABEL: Record<ComplianceFindingStatus, string> = {
  compliant: "適合",
  warning: "要確認",
  non_compliant: "不適合",
  not_run: "未実施",
};
const STATUS_V: Record<ComplianceFindingStatus, "default" | "secondary" | "destructive" | "outline"> = {
  compliant: "default",
  warning: "secondary",
  non_compliant: "destructive",
  not_run: "outline",
};
const StatusIcon = ({ s }: { s: ComplianceFindingStatus }) => {
  if (s === "compliant") return <CheckCircle2 className="h-4 w-4 text-emerald-500" />;
  if (s === "warning") return <AlertTriangle className="h-4 w-4 text-amber-500" />;
  if (s === "non_compliant") return <XCircle className="h-4 w-4 text-destructive" />;
  return <CircleDashed className="h-4 w-4 text-muted-foreground" />;
};
const LAWS = ["建設業法", "下請法", "電子帳簿保存法", "個人情報保護法"];

export function ComplianceFindingsTable({ items, total, defaultFilters }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();
  const update = (key: string, val: string) => {
    const p = new URLSearchParams(sp.toString());
    if (val && val !== "all") p.set(key, val); else p.delete(key);
    router.push(`${pathname}?${p.toString()}`);
  };
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-3">
        <Select defaultValue={defaultFilters.framework ?? "all"} onValueChange={v => update("framework", v)}>
          <SelectTrigger className="w-48"><SelectValue placeholder="法令" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">すべての法令</SelectItem>
            {LAWS.map(l => <SelectItem key={l} value={l}>{l}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select defaultValue={defaultFilters.status ?? "all"} onValueChange={v => update("status", v)}>
          <SelectTrigger className="w-32"><SelectValue placeholder="状態" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">すべて</SelectItem>
            <SelectItem value="compliant">適合</SelectItem>
            <SelectItem value="warning">要確認</SelectItem>
            <SelectItem value="non_compliant">不適合</SelectItem>
            <SelectItem value="not_run">未実施</SelectItem>
          </SelectContent>
        </Select>
      </div>
      {items.length === 0 ? (
        <p className="py-10 text-center text-sm text-muted-foreground">該当する項目がありません</p>
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-8"></TableHead>
                <TableHead className="w-40">法令</TableHead>
                <TableHead className="min-w-[280px]">チェック項目・指摘内容</TableHead>
                <TableHead className="w-28">状態</TableHead>
                <TableHead className="w-28">確認日</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map(f => (
                <TableRow key={f.id} className="hover:bg-muted/50">
                  <TableCell><StatusIcon s={f.status} /></TableCell>
                  <TableCell className="whitespace-nowrap text-xs font-medium">{f.law}</TableCell>
                  <TableCell>
                    <p className="text-sm font-medium">{f.item}</p>
                    {f.detail ? (
                      <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                        {f.detail}
                      </p>
                    ) : null}
                  </TableCell>
                  <TableCell><Badge variant={STATUS_V[f.status]}>{STATUS_LABEL[f.status]}</Badge></TableCell>
                  <TableCell className="whitespace-nowrap font-mono text-xs text-muted-foreground">{f.lastCheck}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      <p className="text-xs text-muted-foreground">{total} 件</p>
    </div>
  );
}
export default ComplianceFindingsTable;
