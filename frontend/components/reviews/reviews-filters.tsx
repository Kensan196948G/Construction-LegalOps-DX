"use client";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { X } from "lucide-react";

interface Props { defaultValues: { status?: string; riskLevel?: string; reviewerConfirmed?: string }; }

export function ReviewsFilters({ defaultValues }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();
  const update = (key: string, val: string) => {
    const p = new URLSearchParams(sp.toString());
    if (val && val !== "all") p.set(key, val); else p.delete(key);
    router.push(`${pathname}?${p.toString()}`);
  };
  const hasFilter = !!(defaultValues.status || defaultValues.riskLevel || defaultValues.reviewerConfirmed);
  return (
    <div className="flex flex-wrap gap-3">
      <Select defaultValue={defaultValues.status ?? ""} onValueChange={v => update("status", v)}>
        <SelectTrigger className="w-36"><SelectValue placeholder="ステータス" /></SelectTrigger>
        <SelectContent>
          <SelectItem value="all">すべて</SelectItem>
          <SelectItem value="completed">完了</SelectItem>
          <SelectItem value="in_progress">レビュー中</SelectItem>
          <SelectItem value="pending_confirmation">確認待ち</SelectItem>
        </SelectContent>
      </Select>
      <Select defaultValue={defaultValues.riskLevel ?? ""} onValueChange={v => update("riskLevel", v)}>
        <SelectTrigger className="w-32"><SelectValue placeholder="リスク" /></SelectTrigger>
        <SelectContent>
          <SelectItem value="all">すべて</SelectItem>
          <SelectItem value="low">低</SelectItem><SelectItem value="medium">中</SelectItem>
          <SelectItem value="high">高</SelectItem><SelectItem value="critical">重大</SelectItem>
        </SelectContent>
      </Select>
      <Select defaultValue={defaultValues.reviewerConfirmed ?? ""} onValueChange={v => update("reviewerConfirmed", v)}>
        <SelectTrigger className="w-36"><SelectValue placeholder="確認状態" /></SelectTrigger>
        <SelectContent>
          <SelectItem value="all">すべて</SelectItem>
          <SelectItem value="true">確認済み</SelectItem>
          <SelectItem value="false">未確認</SelectItem>
        </SelectContent>
      </Select>
      {hasFilter && <Button variant="ghost" size="sm" onClick={() => router.push(pathname)}><X className="mr-1 h-3.5 w-3.5" />クリア</Button>}
    </div>
  );
}
export default ReviewsFilters;
