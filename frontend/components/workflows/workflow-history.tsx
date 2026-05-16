import { MOCK_AUDIT_LOGS } from "@/lib/mock-data";

const ACTION_LABELS: Record<string, string> = {
  "workflow.approve": "承認",
  "workflow.reject": "却下",
  "workflow.return": "差戻し",
  "review.complete": "レビュー完了",
  "contract.upload": "書類アップロード",
};

interface Props { workflowId: string; }

export function WorkflowHistory({ workflowId: _ }: Props) {
  const logs = MOCK_AUDIT_LOGS
    .filter(l => l.action.startsWith("workflow.") || l.action.startsWith("review."))
    .slice(0, 6);

  return (
    <ol className="relative border-l border-border pl-4 space-y-4">
      {logs.map(log => (
        <li key={log.id} className="relative">
          <div className="absolute -left-[1.15rem] mt-1 h-2.5 w-2.5 rounded-full border-2 bg-background border-border" />
          <p className="text-xs text-muted-foreground font-mono">{log.occurredAt.replace("T", " ").slice(0, 16)}</p>
          <p className="mt-0.5 text-sm">
            <span className="font-medium">{log.actor.name}</span>
            <span className="text-muted-foreground">（{log.actor.role}）が </span>
            {ACTION_LABELS[log.action] ?? log.action}
          </p>
          {log.resourceId && (
            <p className="text-xs text-muted-foreground font-mono mt-0.5">対象: {log.resourceId}</p>
          )}
        </li>
      ))}
    </ol>
  );
}
export default WorkflowHistory;
