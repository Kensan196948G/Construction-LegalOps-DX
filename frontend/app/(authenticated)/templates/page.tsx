import type { Metadata } from "next";
import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TemplatesGrid } from "@/components/templates/templates-grid";
import { TemplatesFilters } from "@/components/templates/templates-filters";
import { CreateTemplateButton } from "@/components/templates/create-template-button";

export const metadata: Metadata = {
  title: "ひな形管理",
  description: "契約ひな形（テンプレート）の登録・編集・公開管理",
};

interface SearchParams {
  q?: string;
  contractType?: string;
  status?: string;
  page?: string;
}

interface TemplatesPageProps {
  searchParams?: Promise<SearchParams>;
}

interface TemplateListResult {
  items: Array<{
    id: string;
    title: string;
    contractType: string;
    version: string;
    status: "draft" | "published" | "archived";
    updatedBy: string;
    updatedAt: string;
  }>;
  total: number;
  page: number;
  perPage: number;
}

async function getTemplates(_params: SearchParams): Promise<TemplateListResult> {
  return { items: [], total: 0, page: 1, perPage: 24 };
}

export default async function TemplatesPage({ searchParams }: TemplatesPageProps) {
  const params = (await searchParams) ?? {};
  const result = await getTemplates(params);

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">ひな形管理</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            契約ひな形（テンプレート）の登録、版管理、公開状態を管理します。
          </p>
        </div>
        <CreateTemplateButton>
          <Button>
            <Plus className="mr-2 h-4 w-4" aria-hidden="true" />
            新規ひな形を作成
          </Button>
        </CreateTemplateButton>
      </header>

      <TemplatesFilters
        defaultValues={{
          q: params.q,
          contractType: params.contractType,
          status: params.status,
        }}
      />

      <Card>
        <CardHeader>
          <CardTitle>ひな形一覧</CardTitle>
        </CardHeader>
        <CardContent>
          <TemplatesGrid
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
