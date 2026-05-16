"use client";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { X } from "lucide-react";

const CATEGORIES = ["建設業法","下請法","損害賠償","工期","秘密保持","独占禁止法","検査・引渡し"];
interface Props { defaultValues: { level?: string; category?: string; status?: string }; }

export function RisksFilters({ defaultValues }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();
  const update = (key: string, val: string) => {
    const p = new URLSearchParams(sp.toString());
    if (val && val !== "all") p.set(key, val); else p.delete(key);
    router.push(`${pathname}?${p.toString()}`);
  };
  const hasFilter = !!(defaultValues.level || defaultValues.category || defaultValues.status);
  return (
    <div className="flex flex-wrap gap-3">
      <Select defaultValue={defaultValues.level ?? ""} onValueChange={v => update("level", v)}>
        <SelectTrigger className="w-32"><SelectValue placeholder="レベル" /></SelectTrigger>
        <SelectContent>
          <SelectItem value="all">すべて</SelectItem>
          <SelectItem value="low">低</SelectItem><SelectItem value="medium">中</SelectItem>
          <SelectItem value="high">高</SelectItem><SelectItem value="critical">重大</SelectItem>
        </SelectContent>
      </Select>
      <Select defaultValue={defaultValues.category ?? ""} onValueChange={v => update("category", v)}>
        <SelectTrigger className="w-36"><SelectValue placeholder="カテゴリ" /></SelectTrigger>
        <SelectContent>
          <SelectItem value="all">すべて</SelectItem>
          {CATEGORIES.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
        </SelectContent>
      </Select>
      <Select defaultValue={defaultValues.status ?? ""} onValueChange={v => update("status", v)}>
        <SelectTrigger className="w-32"><SelectValue placeholder="状態" /></SelectTrigger>
        <SelectContent>
          <SelectItem value="all">すべて</SelectItem>
          <SelectItem value="open">未対応</SelectItem>
          <SelectItem value="mitigated">軽減済み</SelectItem>
          <SelectItem value="accepted">受容</SelectItem>
          <SelectItem value="closed">解消</SelectItem>
        </SelectContent>
      </Select>
      {hasFilter && <Button variant="ghost" size="sm" onClick={() => router.push(pathname)}><X className="mr-1 h-3.5 w-3.5" />クリア</Button>}
    </div>
  );
}
export default RisksFilters;
