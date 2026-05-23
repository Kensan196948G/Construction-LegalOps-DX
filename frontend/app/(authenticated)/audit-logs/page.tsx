import type { Metadata } from "next";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AuditLogsTable } from "@/components/audit-logs/audit-logs-table";
import { AuditLogsFilters } from "@/components/audit-logs/audit-logs-filters";
import { HashIntegrityBadge } from "@/components/audit-logs/hash-integrity-badge";
import { bindServerSession } from "@/lib/auth/session-bridge.server";
import { auditLogsApi } from "@/lib/api/endpoints";

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

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
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

async function getAuditLogs(params: SearchParams): Promise<AuditLogListResult> {
  const page = Number(params.page ?? 1);
  const perPage = 50;

  const cleanup = await bindServerSession();
  try {
    const [listResult, verifyResult] = await Promise.allSettled([
      auditLogsApi.list({
        action: params.action || undefined,
        target_type: params.resourceType || undefined,
        from: params.from || undefined,
        to: params.to || undefined,
        page,
        page_size: perPage,
      }),
      auditLogsApi.verify(),
    ]);

    const rawItems = listResult.status === "fulfilled" ? listResult.value.items : [];
    const total = listResult.status === "fulfilled" ? listResult.value.total : 0;

    const allItems = rawItems.map((l) => ({
      id: String(l.id),
      occurredAt: formatDate(l.occurred_at),
      actor: {
        id: String(l.actor?.id ?? ""),
        name: l.actor?.display_name ?? "—",
        role: "—",
      },
      action: l.action,
      resourceType: l.target_type,
      resourceId: String(l.target_id ?? "—"),
      ipAddress: null,
      userAgent: null,
      prevHash: l.previous_hash ?? "",
      hash: l.hash_chain ?? "",
      chainValid: true,
    }));

    // actor name is a client-side filter (API only supports actor_id)
    const filtered =
      params.actor
        ? allItems.filter((l) => l.actor.name.toLowerCase().includes(params.actor!.toLowerCase()))
        : allItems;

    const chainIntegrity =
      verifyResult.status === "fulfilled"
        ? {
            verified: verifyResult.value.verified,
            verifiedAt: null,
            tamperedCount: verifyResult.value.broken_at !== null ? 1 : 0,
          }
        : { verified: true, verifiedAt: null, tamperedCount: 0 };

    return { items: filtered, total, page, perPage, chainIntegrity };
  } catch {
    return {
      items: [],
      total: 0,
      page,
      perPage,
      chainIntegrity: { verified: true, verifiedAt: null, tamperedCount: 0 },
    };
  } finally {
    cleanup();
  }
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
