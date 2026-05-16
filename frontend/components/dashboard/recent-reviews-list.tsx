import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/components/lib/utils";

interface Review { id: string; title: string; status: string; riskLevel: "low" | "medium" | "high" | "critical"; updatedAt: string; }
interface Props { reviews: Review[]; }

const STATUS_LABEL: Record<string, string> = { completed: "完了", in_progress: "レビュー中", pending_confirmation: "確認待ち" };
const RISK_VARIANT: Record<string, string> = { low: "outline", medium: "secondary", high: "destructive", critical: "destructive" };
const RISK_LABEL: Record<string, string> = { low: "低", medium: "中", high: "高", critical: "重大" };

export function RecentReviewsList({ reviews }: Props) {
  if (!reviews.length) return <p className="py-4 text-center text-sm text-muted-foreground">レビューデータがありません</p>;
  return (
    <ul className="divide-y">
      {reviews.map(r => (
        <li key={r.id} className="flex items-center justify-between gap-3 py-3">
          <div className="min-w-0 flex-1">
            <Link href={`/reviews/${r.id}`} className="text-sm font-medium hover:underline line-clamp-1">{r.title}</Link>
            <p className="mt-0.5 text-xs text-muted-foreground">{r.updatedAt}</p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <Badge variant={r.status === "completed" ? "default" : "secondary"} className="text-xs">
              {STATUS_LABEL[r.status] ?? r.status}
            </Badge>
            <Badge variant={RISK_VARIANT[r.riskLevel] as "default" | "secondary" | "destructive" | "outline"} className="text-xs">
              {RISK_LABEL[r.riskLevel]}リスク
            </Badge>
          </div>
        </li>
      ))}
    </ul>
  );
}
export default RecentReviewsList;
