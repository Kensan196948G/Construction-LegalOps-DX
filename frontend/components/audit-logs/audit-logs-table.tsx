import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CheckCircle2, XCircle } from "lucide-react";

interface Actor { id: string; name: string; role: string; }
interface LogItem { id: string; occurredAt: string; actor: Actor; action: string; resourceType: string; resourceId: string; ipAddress: string | null; userAgent: string | null; prevHash: string; hash: string; chainValid: boolean; }
interface Props { items: LogItem[]; total: number; page: number; perPage: number; }

const ACTION_LABELS: Record<string, string> = { "contract.create": "契約作成", "contract.update": "契約更新", "contract.upload": "ファイルアップロード", "review.start": "レビュー開始", "review.complete": "レビュー完了", "workflow.approve": "ワークフロー承認", "workflow.reject": "ワークフロー否決", "user.login": "ログイン", "settings.update": "設定変更" };

export function AuditLogsTable({ items, total }: Props) {
  if (!items.length) return <p className="py-12 text-center text-sm text-muted-foreground">監査ログが見つかりません</p>;
  return (
    <div className="space-y-2">
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-40">日時</TableHead>
              <TableHead className="w-28">操作者</TableHead>
              <TableHead className="w-36">アクション</TableHead>
              <TableHead className="w-24">対象種別</TableHead>
              <TableHead className="w-36">対象ID</TableHead>
              <TableHead className="w-32">IPアドレス</TableHead>
              <TableHead className="w-16 text-center">整合性</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map(l => (
              <TableRow key={l.id} className="hover:bg-muted/50">
                <TableCell className="font-mono text-xs">{l.occurredAt.replace("T", " ")}</TableCell>
                <TableCell>
                  <div>
                    <p className="text-sm font-medium">{l.actor.name}</p>
                    <p className="text-xs text-muted-foreground">{l.actor.role}</p>
                  </div>
                </TableCell>
                <TableCell>
                  <Badge variant="outline" className="text-xs font-mono">{l.action}</Badge>
                  <p className="mt-0.5 text-xs text-muted-foreground">{ACTION_LABELS[l.action] ?? l.action}</p>
                </TableCell>
                <TableCell className="text-sm">{l.resourceType}</TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">{l.resourceId}</TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">{l.ipAddress ?? "—"}</TableCell>
                <TableCell className="text-center">
                  {l.chainValid
                    ? <CheckCircle2 className="mx-auto h-4 w-4 text-emerald-500" aria-label="ハッシュ正常" />
                    : <XCircle className="mx-auto h-4 w-4 text-destructive" aria-label="ハッシュ不正" />}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <p className="text-xs text-muted-foreground">{total} 件</p>
    </div>
  );
}
export default AuditLogsTable;
