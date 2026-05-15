import * as React from "react";

import { cn } from "@/components/lib/utils";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import {
  HashChainVerifyBadge,
  type HashChainState,
} from "@/components/features/audit/hash-chain-verify-badge";

export interface AuditLogEntry {
  id: string;
  /** 発生時刻 (ISO 文字列・既に日本語フォーマット済み文字列でも可) */
  occurredAt: string;
  /** 実行ユーザー */
  actor: string;
  /** 操作種別 (例: contract.upload / review.approve / workflow.reject) */
  action: string;
  /** 対象リソース */
  target?: string;
  /** ハッシュチェーンの検証状態 */
  hashChain: HashChainState;
  /** ハッシュの先頭部分 */
  hashPreview?: string;
  /** 補足 (差分概要など) */
  detail?: string;
}

export interface AuditLogTableProps extends React.HTMLAttributes<HTMLDivElement> {
  entries: AuditLogEntry[];
  isLoading?: boolean;
}

export function AuditLogTable({
  entries,
  isLoading = false,
  className,
  ...props
}: AuditLogTableProps) {
  return (
    <div className={cn("rounded-md border", className)} {...props}>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[180px]">日時</TableHead>
            <TableHead>実行者</TableHead>
            <TableHead>操作</TableHead>
            <TableHead>対象</TableHead>
            <TableHead>詳細</TableHead>
            <TableHead className="w-[220px]">改ざん検証</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading ? (
            <TableRow>
              <TableCell colSpan={6} className="h-24 text-center">
                読み込み中...
              </TableCell>
            </TableRow>
          ) : entries.length === 0 ? (
            <TableRow>
              <TableCell
                colSpan={6}
                className="h-24 text-center text-muted-foreground"
              >
                監査ログはありません
              </TableCell>
            </TableRow>
          ) : (
            entries.map((entry) => (
              <TableRow key={entry.id}>
                <TableCell className="font-mono text-xs text-muted-foreground">
                  {entry.occurredAt}
                </TableCell>
                <TableCell className="text-sm">{entry.actor}</TableCell>
                <TableCell>
                  <Badge variant="outline" className="font-mono text-xs">
                    {entry.action}
                  </Badge>
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {entry.target ?? "—"}
                </TableCell>
                <TableCell className="max-w-[320px] truncate text-sm text-muted-foreground">
                  {entry.detail ?? "—"}
                </TableCell>
                <TableCell>
                  <HashChainVerifyBadge
                    state={entry.hashChain}
                    hashPreview={entry.hashPreview}
                  />
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
}

export default AuditLogTable;
