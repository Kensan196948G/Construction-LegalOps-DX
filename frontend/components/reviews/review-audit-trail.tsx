"use client";

import { ShieldCheck, ShieldAlert } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { AuditLog } from "@/lib/api/schemas";

const ACTION_LABELS: Record<string, string> = {
  "review.start": "AI レビュー開始",
  "review.complete": "AI レビュー完了",
  "review.accept": "レビュー受領",
  "contract.upload": "契約書アップロード",
  "workflow.approve": "承認",
  "workflow.return": "差戻し",
};

interface Props {
  reviewId: string;
  logs?: AuditLog[];
  forbidden?: boolean;
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString("ja-JP", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function ReviewAuditTrail({ reviewId: _, logs = [], forbidden = false }: Props) {
  if (forbidden) {
    return (
      <p className="py-6 text-center text-sm text-muted-foreground">
        監査証跡は監査者・管理者権限でのみ表示されます。
      </p>
    );
  }

  if (logs.length === 0) {
    return (
      <p className="py-6 text-center text-sm text-muted-foreground">
        監査ログはまだありません。
      </p>
    );
  }

  return (
    <div className="space-y-4 py-2">
      <div className="flex items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/20 dark:text-emerald-200">
        <ShieldCheck className="h-4 w-4 shrink-0" aria-hidden="true" />
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
            {logs.map((log) => (
              <tr key={log.id} className="border-b last:border-0">
                <td className="whitespace-nowrap px-3 py-2 font-mono text-muted-foreground">
                  {formatDate(log.occurred_at)}
                </td>
                <td className="whitespace-nowrap px-3 py-2">
                  {log.actor?.display_name ?? "システム"}
                </td>
                <td className="px-3 py-2">{ACTION_LABELS[log.action] ?? log.action}</td>
                <td className="px-3 py-2">
                  {log.hash_chain ? (
                    <Badge variant="outline" className="border-emerald-300 text-emerald-700">
                      <ShieldCheck className="mr-1 h-3 w-3" aria-hidden="true" />
                      OK
                    </Badge>
                  ) : (
                    <Badge variant="destructive">
                      <ShieldAlert className="mr-1 h-3 w-3" aria-hidden="true" />
                      NG
                    </Badge>
                  )}
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
