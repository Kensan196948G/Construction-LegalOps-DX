import type { Metadata } from "next";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ComplianceChecklist } from "@/components/compliance/compliance-checklist";
import { ComplianceFindingsTable } from "@/components/compliance/compliance-findings-table";
import { AiDisclaimerInline } from "@/components/legal/ai-disclaimer-inline";

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

import { MOCK_COMPLIANCE_FRAMEWORKS, MOCK_COMPLIANCE_ITEMS } from "@/lib/mock-data";

async function getComplianceState(params: SearchParams) {
  let findings = MOCK_COMPLIANCE_ITEMS.map(c => ({
    id: c.id, law: c.law, item: c.item, status: c.status, lastCheck: c.lastCheck, detail: c.detail,
  }));
  if (params.framework) findings = findings.filter(f => f.law === params.framework);
  if (params.status) findings = findings.filter(f => f.status === params.status);
  return {
    frameworks: MOCK_COMPLIANCE_FRAMEWORKS,
    findings,
    total: findings.length,
    page: 1,
    perPage: 20,
  };
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
