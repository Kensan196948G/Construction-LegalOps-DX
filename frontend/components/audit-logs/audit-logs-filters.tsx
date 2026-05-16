"use client";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Search, X } from "lucide-react";

const ACTIONS = ["contract.create","contract.update","contract.upload","review.start","review.complete","workflow.approve","workflow.reject","user.login","settings.update"];
const RESOURCE_TYPES = ["contract","review","workflow","user","system"];
interface Props { defaultValues: { actor?: string; action?: string; resourceType?: string; from?: string; to?: string }; }

export function AuditLogsFilters({ defaultValues }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();
  const update = (key: string, val: string) => {
    const p = new URLSearchParams(sp.toString());
    if (val && val !== "all") p.set(key, val); else p.delete(key);
    router.push(`${pathname}?${p.toString()}`);
  };
  const hasFilter = !!(defaultValues.actor || defaultValues.action || defaultValues.resourceType);
  return (
    <div className="flex flex-wrap gap-3">
      <div className="relative min-w-40">
        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
        <Input defaultValue={defaultValues.actor} placeholder="操作者名" className="pl-8 w-40" onChange={e => update("actor", e.target.value)} />
      </div>
      <Select defaultValue={defaultValues.action ?? ""} onValueChange={v => update("action", v)}>
        <SelectTrigger className="w-48"><SelectValue placeholder="アクション" /></SelectTrigger>
        <SelectContent>
          <SelectItem value="all">すべて</SelectItem>
          {ACTIONS.map(a => <SelectItem key={a} value={a}>{a}</SelectItem>)}
        </SelectContent>
      </Select>
      <Select defaultValue={defaultValues.resourceType ?? ""} onValueChange={v => update("resourceType", v)}>
        <SelectTrigger className="w-32"><SelectValue placeholder="対象種別" /></SelectTrigger>
        <SelectContent>
          <SelectItem value="all">すべて</SelectItem>
          {RESOURCE_TYPES.map(r => <SelectItem key={r} value={r}>{r}</SelectItem>)}
        </SelectContent>
      </Select>
      {hasFilter && <Button variant="ghost" size="sm" onClick={() => router.push(pathname)}><X className="mr-1 h-3.5 w-3.5" />クリア</Button>}
    </div>
  );
}
export default AuditLogsFilters;
