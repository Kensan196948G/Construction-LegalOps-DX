import { ShieldCheck, ShieldAlert } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { MOCK_AUDIT_LOGS } from "@/lib/mock-data";

const ACTION_LABELS: Record<string, string> = {
  "review.start": "AI レビュー開始",
  "review.complete": "AI レビュー完了",
  "contract.upload": "契約書アップロード",
  "workflow.approve": "承認",
  "workflow.return": "差戻し",
};

interface Props { reviewId: string; }

export function ReviewAuditTrail({ reviewId: _ }: Props) {
  const logs = MOCK_AUDIT_LOGS
    .filter(l => ["review.start", "review.complete", "contract.upload", "workflow.approve"].includes(l.action))
    .slice(0, 6);

  return (
    <div className="space-y-4 py-2">
      <div className="rounded-md border border-emerald-200 bg-emerald-50 dark:border-emerald-800 dark:bg-emerald-950/20 p-3 flex items-center gap-2 text-sm text-emerald-800 dark:text-emerald-200">
        <ShieldCheck className="h-4 w-4 shrink-0" />
        <span>全 {logs.length} 件のログがハッシュチェーンで保護されています</span>
      </div>

      <div className="rounded-md border">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">日時</th>
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">操作者</th>
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">操作</th>
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">整合性</th>
            </tr>
          </thead>
          <tbody>
            {logs.map(log => (
              <tr key={log.id} className="border-b last:border-0">
                <td className="px-3 py-2 font-mono text-muted-foreground whitespace-nowrap">
                  {log.occurredAt.replace("T", " ").slice(0, 16)}
                </td>
                <td className="px-3 py-2 whitespace-nowrap">{log.actor.name}</td>
                <td className="px-3 py-2">{ACTION_LABELS[log.action] ?? log.action}</td>
                <td className="px-3 py-2">
                  {log.chainValid
                    ? <Badge variant="outline" className="text-emerald-700 border-emerald-300"><ShieldCheck className="mr-1 h-3 w-3" />OK</Badge>
                    : <Badge variant="destructive"><ShieldAlert className="mr-1 h-3 w-3" />NG</Badge>
                  }
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
export default ReviewAuditTrail;
