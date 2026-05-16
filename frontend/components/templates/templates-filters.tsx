"use client";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Search, X } from "lucide-react";

const TYPES = ["工事請負契約","業務委託契約","資材購入契約","下請契約","設計監理契約","秘密保持契約"];
interface Props { defaultValues: { q?: string; contractType?: string; status?: string }; }

export function TemplatesFilters({ defaultValues }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();
  const update = (key: string, val: string) => {
    const p = new URLSearchParams(sp.toString());
    if (val && val !== "all") p.set(key, val); else p.delete(key);
    router.push(`${pathname}?${p.toString()}`);
  };
  const hasFilter = !!(defaultValues.q || defaultValues.contractType || defaultValues.status);
  return (
    <div className="flex flex-wrap gap-3">
      <div className="relative min-w-48 flex-1">
        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
        <Input defaultValue={defaultValues.q} placeholder="ひな形名を検索" className="pl-8" onChange={e => update("q", e.target.value)} />
      </div>
      <Select defaultValue={defaultValues.contractType ?? ""} onValueChange={v => update("contractType", v)}>
        <SelectTrigger className="w-36"><SelectValue placeholder="契約種別" /></SelectTrigger>
        <SelectContent>
          <SelectItem value="all">すべて</SelectItem>
          {TYPES.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}
        </SelectContent>
      </Select>
      <Select defaultValue={defaultValues.status ?? ""} onValueChange={v => update("status", v)}>
        <SelectTrigger className="w-32"><SelectValue placeholder="状態" /></SelectTrigger>
        <SelectContent>
          <SelectItem value="all">すべて</SelectItem>
          <SelectItem value="published">公開中</SelectItem>
          <SelectItem value="draft">下書き</SelectItem>
          <SelectItem value="archived">アーカイブ</SelectItem>
        </SelectContent>
      </Select>
      {hasFilter && <Button variant="ghost" size="sm" onClick={() => router.push(pathname)}><X className="mr-1 h-3.5 w-3.5" />クリア</Button>}
    </div>
  );
}
export default TemplatesFilters;
