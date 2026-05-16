import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Clock } from "lucide-react";

interface ApprovalItem { id: string; contractTitle: string; route: string; waitingFor: string; dueDate: string; }
interface Props { items: ApprovalItem[]; }

export function PendingApprovalsList({ items }: Props) {
  if (!items.length) return (
    <div className="flex flex-col items-center gap-2 py-8 text-center">
      <p className="text-sm text-muted-foreground">承認待ちの案件はありません</p>
    </div>
  );
  return (
    <ul className="divide-y">
      {items.map(item => (
        <li key={item.id} className="flex items-center justify-between gap-3 py-3">
          <div className="min-w-0 flex-1">
            <Link href={`/workflows/${item.id}`} className="text-sm font-medium hover:underline line-clamp-1">{item.contractTitle}</Link>
            <p className="mt-0.5 flex items-center gap-1.5 text-xs text-muted-foreground">
              <Clock className="h-3 w-3" aria-hidden />
              期限: {item.dueDate} · 担当: {item.waitingFor}
            </p>
          </div>
          <Badge variant="outline" className="shrink-0 text-xs font-mono">{item.route}</Badge>
        </li>
      ))}
    </ul>
  );
}
export default PendingApprovalsList;
