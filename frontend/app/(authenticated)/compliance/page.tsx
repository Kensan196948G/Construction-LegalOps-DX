import type { Metadata } from "next";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ComplianceChecklist } from "@/components/compliance/compliance-checklist";
import { ComplianceFindingsTable } from "@/components/compliance/compliance-findings-table";
import { AiDisclaimerInline } from "@/components/legal/ai-disclaimer-inline";
import { bindServerSession } from "@/lib/auth/session-bridge.server";
import { complianceApi } from "@/lib/api/endpoints";

export const metadata: Metadata = {
  title: "コンプライアンスチェック",
  description: "建設業法・下請法・独禁法等の遵守状況確認",
};

interface SearchParams {
  framework?: string;
  status?: string;
  page?: string;
}

interface CompliancePageProps {
  searchParams?: Promise<SearchParams>;
}

type CStatus = "compliant" | "warning" | "non_compliant";

interface Framework {
  id: string;
  label: string;
  passed: number;
  failed: number;
  na: number;
}

interface Finding {
  id: string;
  law: string;
  item: string;
  status: CStatus;
  lastCheck: string;
  detail: string;
}

function toFindingStatus(severity: string | null | undefined): CStatus {
  if (severity === "high" || severity === "critical") return "non_compliant";
  if (severity === "medium") return "warning";
  return "warning"; // default: unchecked = needs review
}

function categoryLabel(category: string): string {
  const labels: Record<string, string> = {
    construction_law: "建設業法",
    subcontract_act: "下請法",
    others: "その他法令",
  };
  return labels[category] ?? category;
}

async function getComplianceState(params: SearchParams) {
  const cleanup = await bindServerSession();
  try {
    const checklists = await complianceApi.checklists({ page: 1, page_size: 100 });

    const frameworks: Framework[] = checklists.map((cl) => {
      return {
        id: String(cl.id),
        label: cl.name,
        passed: 0,
        failed: 0,
        na: 1,
      };
    });

    const allFindings: Finding[] = checklists.map((cl) => ({
      id: String(cl.id),
      law: categoryLabel(cl.category),
      item: cl.name,
      status: toFindingStatus(null),
      lastCheck: "—",
      detail: cl.description ?? "",
    }));

    // Client-side filters
    const filtered = allFindings.filter((f) => {
      if (params.framework && params.framework !== "all" && f.law !== params.framework) return false;
      if (params.status && params.status !== "all" && f.status !== params.status) return false;
      return true;
    });

    return {
      frameworks,
      findings: filtered,
      total: allFindings.length,
      page: 1,
      perPage: 20,
    };
  } catch {
    return { frameworks: [], findings: [], total: 0, page: 1, perPage: 20 };
  } finally {
    cleanup();
  }
}

export default async function CompliancePage({ searchParams }: CompliancePageProps) {
  const params = (await searchParams) ?? {};
  const state = await getComplianceState(params);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-foreground">コンプライアンスチェック</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          建設業法・下請法・独禁法・個人情報保護法等のチェック項目と検出結果を表示します。
        </p>
      </header>

      <AiDisclaimerInline>
        本ページの AI チェック結果は参考情報です。実際の法令適用判断は
        法務担当者・顧問弁護士が行います。
      </AiDisclaimerInline>

      <Card>
        <CardHeader>
          <CardTitle>適用フレームワーク</CardTitle>
        </CardHeader>
        <CardContent>
          <ComplianceChecklist frameworks={state.frameworks} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>検出された是正対象</CardTitle>
        </CardHeader>
        <CardContent>
          <ComplianceFindingsTable
            items={state.findings}
            total={state.total}
            page={state.page}
            perPage={state.perPage}
            defaultFilters={{
              framework: params.framework,
              status: params.status,
            }}
          />
        </CardContent>
      </Card>
    </div>
  );
}
