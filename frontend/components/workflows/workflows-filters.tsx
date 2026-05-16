"use client";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { X } from "lucide-react";

interface Props { defaultValues: { status?: string; route?: string; assignedToMe?: string }; }

export function WorkflowsFilters({ defaultValues }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();
  const update = (key: string, val: string) => {
    const p = new URLSearchParams(sp.toString());
    if (val && val !== "all") p.set(key, val); else p.delete(key);
    router.push(`${pathname}?${p.toString()}`);
  };
  const hasFilter = !!(defaultValues.status || defaultValues.route || defaultValues.assignedToMe);
  return (
    <div className="flex flex-wrap gap-3">
      <Select defaultValue={defaultValues.status ?? ""} onValueChange={v => update("status", v)}>
        <SelectTrigger className="w-36"><SelectValue placeholder="ステータス" /></SelectTrigger>
        <SelectContent>
          <SelectItem value="all">すべて</SelectItem>
          <SelectItem value="in_progress">審査中</SelectItem>
          <SelectItem value="approved">承認済み</SelectItem>
          <SelectItem value="rejected">否決</SelectItem>
          <SelectItem value="returned">差戻し</SelectItem>
        </SelectContent>
      </Select>
      <Select defaultValue={defaultValues.route ?? ""} onValueChange={v => update("route", v)}>
        <SelectTrigger className="w-36"><SelectValue placeholder="承認ルート" /></SelectTrigger>
        <SelectContent>
          <SelectItem value="all">すべて</SelectItem>
          {["A1","A2","B1","B2","C1","C2","D1"].map(r => <SelectItem key={r} value={r}>{r}</SelectItem>)}
        </SelectContent>
      </Select>
      <Select defaultValue={defaultValues.assignedToMe ?? ""} onValueChange={v => update("assignedToMe", v)}>
        <SelectTrigger className="w-40"><SelectValue placeholder="担当者" /></SelectTrigger>
        <SelectContent>
          <SelectItem value="all">全員</SelectItem>
          <SelectItem value="true">自分宛のみ</SelectItem>
        </SelectContent>
      </Select>
      {hasFilter && <Button variant="ghost" size="sm" onClick={() => router.push(pathname)}><X className="mr-1 h-3.5 w-3.5" />クリア</Button>}
    </div>
  );
}
export default WorkflowsFilters;
