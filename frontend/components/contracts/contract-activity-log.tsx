import { MOCK_AUDIT_LOGS } from "@/lib/mock-data";

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

interface Props { contractId: string; }

export function ContractActivityLog({ contractId }: Props) {
  const logs = MOCK_AUDIT_LOGS
    .filter(l => l.resourceId === contractId || l.resourceId.startsWith("CTR"))
    .slice(0, 8);

  if (logs.length === 0) {
    return <p className="py-6 text-center text-sm text-muted-foreground">アクティビティはありません</p>;
  }

  return (
    <ol className="relative border-l border-border pl-4 space-y-4">
      {logs.map(log => (
        <li key={log.id} className="relative">
          <div className="absolute -left-[1.15rem] mt-1 h-2.5 w-2.5 rounded-full border bg-background" />
          <p className="text-xs text-muted-foreground font-mono">{log.occurredAt.replace("T", " ").slice(0, 16)}</p>
          <p className="mt-0.5 text-sm">
            <span className="font-medium">{log.actor.name}</span>
            {"（"}{log.actor.role}{"）が "}
            {ACTION_LABELS[log.action] ?? log.action}
          </p>
        </li>
      ))}
    </ol>
  );
}
export default ContractActivityLog;
