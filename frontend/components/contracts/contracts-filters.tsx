"use client";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { useCallback } from "react";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Search, X } from "lucide-react";

interface Props { defaultValues: { q?: string; status?: string; contractType?: string; riskLevel?: string }; }

const STATUSES = [["draft","下書き"],["in_review","レビュー中"],["approved","承認済み"],["pending_approval","承認待ち"],["expired","期限切れ"]];
const RISK_LEVELS = [["low","低リスク"],["medium","中リスク"],["high","高リスク"],["critical","重大リスク"]];
const CONTRACT_TYPES = ["工事請負契約","業務委託契約","資材購入契約","下請契約","設計監理契約","賃貸借契約","秘密保持契約"];

export function ContractsFilters({ defaultValues }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();

  const update = useCallback((key: string, val: string) => {
    const params = new URLSearchParams(sp.toString());
    if (val && val !== "all") params.set(key, val); else params.delete(key);
    params.delete("page");
    router.push(`${pathname}?${params.toString()}`);
  }, [router, pathname, sp]);

  const clear = () => router.push(pathname);
  const hasFilter = !!(defaultValues.q || defaultValues.status || defaultValues.contractType || defaultValues.riskLevel);

  return (
    <div className="flex flex-wrap gap-3">
      <div className="relative min-w-48 flex-1">
        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
        <Input
          defaultValue={defaultValues.q}
          placeholder="契約名・取引先を検索"
          className="pl-8"
          onChange={e => update("q", e.target.value)}
        />
      </div>
      <Select defaultValue={defaultValues.status ?? ""} onValueChange={v => update("status", v)}>
        <SelectTrigger className="w-36"><SelectValue placeholder="ステータス" /></SelectTrigger>
        <SelectContent>
          <SelectItem value="all">すべて</SelectItem>
          {STATUSES.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
        </SelectContent>
      </Select>
      <Select defaultValue={defaultValues.contractType ?? ""} onValueChange={v => update("contractType", v)}>
        <SelectTrigger className="w-36"><SelectValue placeholder="契約種別" /></SelectTrigger>
        <SelectContent>
          <SelectItem value="all">すべて</SelectItem>
          {CONTRACT_TYPES.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}
        </SelectContent>
      </Select>
      <Select defaultValue={defaultValues.riskLevel ?? ""} onValueChange={v => update("riskLevel", v)}>
        <SelectTrigger className="w-32"><SelectValue placeholder="リスク" /></SelectTrigger>
        <SelectContent>
          <SelectItem value="all">すべて</SelectItem>
          {RISK_LEVELS.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
        </SelectContent>
      </Select>
      {hasFilter && <Button variant="ghost" size="sm" onClick={clear}><X className="mr-1 h-3.5 w-3.5" />クリア</Button>}
    </div>
  );
}
export default ContractsFilters;
