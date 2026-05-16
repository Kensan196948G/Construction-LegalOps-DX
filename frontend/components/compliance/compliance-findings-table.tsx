"use client";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CheckCircle2, AlertTriangle, XCircle } from "lucide-react";

type CStatus = "compliant" | "warning" | "non_compliant";
interface Finding { id: string; law: string; item: string; status: CStatus; lastCheck: string; detail: string; }
interface Props { items: Finding[]; total: number; page: number; perPage: number; defaultFilters: { framework?: string; status?: string }; }

const STATUS_LABEL: Record<CStatus, string> = { compliant: "適合", warning: "要確認", non_compliant: "不適合" };
const STATUS_V: Record<CStatus, "default" | "secondary" | "destructive"> = { compliant: "default", warning: "secondary", non_compliant: "destructive" };
const StatusIcon = ({ s }: { s: CStatus }) => s === "compliant" ? <CheckCircle2 className="h-4 w-4 text-emerald-500" /> : s === "warning" ? <AlertTriangle className="h-4 w-4 text-amber-500" /> : <XCircle className="h-4 w-4 text-destructive" />;
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
                <TableHead className="w-36">法令</TableHead>
                <TableHead>チェック項目</TableHead>
                <TableHead className="w-20">状態</TableHead>
                <TableHead className="w-24">確認日</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map(f => (
                <TableRow key={f.id} className="hover:bg-muted/50">
                  <TableCell><StatusIcon s={f.status} /></TableCell>
                  <TableCell className="text-xs font-medium">{f.law}</TableCell>
                  <TableCell>
                    <p className="text-sm font-medium truncate max-w-xs">{f.item}</p>
                    <p className="text-xs text-muted-foreground truncate max-w-xs">{f.detail}</p>
                  </TableCell>
                  <TableCell><Badge variant={STATUS_V[f.status]}>{STATUS_LABEL[f.status]}</Badge></TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground">{f.lastCheck}</TableCell>
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
