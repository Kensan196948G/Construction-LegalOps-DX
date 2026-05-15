import type { Metadata } from "next";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AuditLogsTable } from "@/components/audit-logs/audit-logs-table";
import { AuditLogsFilters } from "@/components/audit-logs/audit-logs-filters";
import { HashIntegrityBadge } from "@/components/audit-logs/hash-integrity-badge";

export const metadata: Metadata = {
  title: "監査ログ",
  description: "改ざん不能な操作監査ログとハッシュ整合性検証",
};

interface SearchParams {
  actor?: string;
  action?: string;
  resourceType?: string;
  from?: string;
  to?: string;
  page?: string;
}

interface AuditLogsPageProps {
  searchParams?: Promise<SearchParams>;
}

interface AuditLogListResult {
  items: Array<{
    id: string;
    occurredAt: string;
    actor: { id: string; name: string; role: string };
    action: string;
    resourceType: string;
    resourceId: string;
    ipAddress: string | null;
    userAgent: string | null;
    prevHash: string;
    hash: string;
    chainValid: boolean;
  }>;
  total: number;
  page: number;
  perPage: number;
  chainIntegrity: {
    verified: boolean;
    verifiedAt: string | null;
    tamperedCount: number;
  };
}

async function getAuditLogs(_params: SearchParams): Promise<AuditLogListResult> {
  return {
    items: [],
    total: 0,
    page: 1,
    perPage: 50,
    chainIntegrity: { verified: true, verifiedAt: null, tamperedCount: 0 },
  };
}

export default async function AuditLogsPage({ searchParams }: AuditLogsPageProps) {
  const params = (await searchParams) ?? {};
  const result = await getAuditLogs(params);

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">監査ログ</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            全ての操作はハッシュチェーン付きで改ざん不能に記録されます。
            管理者は本画面から整合性を検証できます。
          </p>
        </div>
        <HashIntegrityBadge integrity={result.chainIntegrity} />
      </header>

      <AuditLogsFilters
        defaultValues={{
          actor: params.actor,
          action: params.action,
          resourceType: params.resourceType,
          from: params.from,
          to: params.to,
        }}
      />

      <Card>
        <CardHeader>
          <CardTitle>監査ログ一覧</CardTitle>
        </CardHeader>
        <CardContent>
          <AuditLogsTable
            items={result.items}
            total={result.total}
            page={result.page}
            perPage={result.perPage}
          />
        </CardContent>
      </Card>
    </div>
  );
}
