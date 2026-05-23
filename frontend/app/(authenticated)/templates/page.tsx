import type { Metadata } from "next";
import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TemplatesGrid } from "@/components/templates/templates-grid";
import { TemplatesFilters } from "@/components/templates/templates-filters";
import { CreateTemplateButton } from "@/components/templates/create-template-button";
import { bindServerSession } from "@/lib/auth/session-bridge.server";
import { templatesApi } from "@/lib/api/endpoints";

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

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("ja-JP", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
  } catch {
    return iso;
  }
}

async function getTemplates(params: SearchParams): Promise<TemplateListResult> {
  const page = Number(params.page ?? 1);
  const perPage = 24;

  const cleanup = await bindServerSession();
  try {
    const result = await templatesApi.list({
      q: params.q || undefined,
      page,
      page_size: perPage,
    });

    const allItems = result.items.map((t) => ({
      id: String(t.id),
      title: t.name,
      contractType: t.contract_type ?? "—",
      version: "1.0",
      status: (t.is_active ? "published" : "archived") as "draft" | "published" | "archived",
      updatedBy: "—",
      updatedAt: formatDate(t.updated_at),
    }));

    // contractType and status filters are client-side (not in backend API)
    const filtered = allItems.filter((t) => {
      if (params.contractType && params.contractType !== "all" && t.contractType !== params.contractType) return false;
      if (params.status && params.status !== "all" && t.status !== params.status) return false;
      return true;
    });

    return { items: filtered, total: result.total, page, perPage };
  } catch {
    return { items: [], total: 0, page, perPage };
  } finally {
    cleanup();
  }
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
