"use client";

import { AlertCircle, Loader2, RefreshCw } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useSyncUsers, useUsers } from "@/hooks/use-users";

const ROLE_LABELS: Record<string, string> = {
  admin: "管理者",
  legal: "法務",
  reviewer: "レビューア",
  approver: "承認者",
  drafter: "起案者",
  viewer: "閲覧者",
  auditor: "監査担当",
  site: "現場担当",
  manager: "部門長",
  guest: "ゲスト",
};

export function UsersSettingsPanel() {
  const { data, isLoading, isError, refetch, isFetching } = useUsers({ page: 1, page_size: 100 });
  const sync = useSyncUsers();

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {data ? `${data.total} 名` : "ユーザ一覧"}（Entra ID 同期結果を表示）
        </p>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => void refetch()}
            disabled={isFetching}
            className="gap-2"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`} aria-hidden="true" />
            再読込
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => sync.mutate()}
            disabled={sync.isPending}
            className="gap-2"
          >
            <Loader2 className={`h-3.5 w-3.5 ${sync.isPending ? "animate-spin" : ""}`} aria-hidden="true" />
            Entra ID 同期
          </Button>
        </div>
      </div>

      {isError && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" aria-hidden="true" />
          <AlertDescription>
            ユーザ一覧を取得できませんでした。権限（admin/auditor）があるか確認してください。
          </AlertDescription>
        </Alert>
      )}

      {sync.data && (
        <Alert variant="default">
          <AlertCircle className="h-4 w-4" aria-hidden="true" />
          <AlertDescription>
            ユーザ同期を受け付けました（ジョブ ID: {sync.data.job_id}、状態: {sync.data.status}）
          </AlertDescription>
        </Alert>
      )}

      {isLoading ? (
        <div className="space-y-2" aria-label="読み込み中">
          {[0, 1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>氏名</TableHead>
                <TableHead>メール</TableHead>
                <TableHead className="w-28">ロール</TableHead>
                <TableHead className="w-24">部署</TableHead>
                <TableHead className="w-20">状態</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data && data.items.length > 0 ? (
                data.items.map((u) => (
                  <TableRow key={u.id}>
                    <TableCell className="text-sm font-medium">
                      {u.display_name ?? "—"}
                    </TableCell>
                    <TableCell className="max-w-[220px] truncate text-xs text-muted-foreground">
                      {u.email}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-xs">
                        {ROLE_LABELS[u.role] ?? u.role}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs">{u.department?.name ?? "—"}</TableCell>
                    <TableCell>
                      <Badge variant={u.is_active ? "default" : "secondary"} className="text-xs">
                        {u.is_active ? "有効" : "無効"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={5} className="py-8 text-center text-sm text-muted-foreground">
                    ユーザが登録されていません
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

export default UsersSettingsPanel;
