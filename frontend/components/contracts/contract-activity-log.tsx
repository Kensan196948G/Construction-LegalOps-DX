"use client";

import type { AuditLog } from "@/lib/api/schemas";

const ACTION_LABELS: Record<string, string> = {
  "contract.create": "契約を作成",
  "contract.update": "契約を更新",
  "contract.upload": "ファイルをアップロード",
  "review.start": "レビューを開始",
  "review.complete": "レビューを完了",
  "workflow.approve": "承認",
  "workflow.reject": "却下",
  "workflow.return": "差戻し",
  "settings.update": "設定を更新",
  "user.login": "ログイン",
};

interface Props {
  contractId: string;
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

export function ContractActivityLog({ contractId: _, logs = [], forbidden = false }: Props) {
  if (forbidden) {
    return (
      <p className="py-6 text-center text-sm text-muted-foreground">
        監査証跡は監査者・管理者権限でのみ表示されます。
      </p>
    );
  }

  if (logs.length === 0) {
    return <p className="py-6 text-center text-sm text-muted-foreground">アクティビティはありません</p>;
  }

  return (
    <ol className="relative space-y-4 border-l border-border pl-4">
      {logs.map((log) => (
        <li key={log.id} className="relative">
          <div className="absolute -left-[1.15rem] mt-1 h-2.5 w-2.5 rounded-full border bg-background" />
          <p className="text-xs text-muted-foreground font-mono">{formatDate(log.occurred_at)}</p>
          <p className="mt-0.5 text-sm">
            <span className="font-medium">{log.actor?.display_name ?? "システム"}</span>
            {log.actor ? <span className="text-muted-foreground">（{log.actor_role ?? "—"}）が </span> : " が "}
            {ACTION_LABELS[log.action] ?? log.action}
          </p>
        </li>
      ))}
    </ol>
  );
}
export default ContractActivityLog;
