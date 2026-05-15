import type { Metadata } from "next";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { KnowledgeSearchBar } from "@/components/knowledge/knowledge-search-bar";
import { KnowledgeResults } from "@/components/knowledge/knowledge-results";
import { KnowledgeCategoryNav } from "@/components/knowledge/knowledge-category-nav";
import { AiDisclaimerInline } from "@/components/legal/ai-disclaimer-inline";

export const metadata: Metadata = {
  title: "ナレッジベース",
  description: "判例・社内文書・FAQ の検索",
};

interface SearchParams {
  q?: string;
  category?: string;
  source?: string;
  page?: string;
}

interface KnowledgePageProps {
  searchParams?: Promise<SearchParams>;
}

interface KnowledgeSearchResult {
  items: Array<{
    id: string;
    title: string;
    excerpt: string;
    source: "internal_doc" | "precedent" | "faq" | "playbook";
    category: string;
    tags: string[];
    updatedAt: string;
    score: number;
  }>;
  total: number;
  page: number;
  perPage: number;
}

async function searchKnowledge(_params: SearchParams): Promise<KnowledgeSearchResult> {
  return { items: [], total: 0, page: 1, perPage: 20 };
}

export default async function KnowledgePage({ searchParams }: KnowledgePageProps) {
  const params = (await searchParams) ?? {};
  const result = await searchKnowledge(params);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-foreground">ナレッジベース</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          判例、社内文書、FAQ、レビュープレイブックを横断検索できます。
        </p>
      </header>

      <AiDisclaimerInline>
        検索結果に含まれる AI 要約は参考情報です。判例の引用・適用判断は
        法務担当者・顧問弁護士が行ってください。
      </AiDisclaimerInline>

      <KnowledgeSearchBar defaultQuery={params.q ?? ""} />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[16rem_1fr]">
        <aside aria-label="カテゴリ">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">カテゴリ</CardTitle>
            </CardHeader>
            <CardContent>
              <KnowledgeCategoryNav
                selectedCategory={params.category}
                selectedSource={params.source}
              />
            </CardContent>
          </Card>
        </aside>

        <section aria-label="検索結果">
          <KnowledgeResults
            items={result.items}
            total={result.total}
            page={result.page}
            perPage={result.perPage}
          />
        </section>
      </div>
    </div>
  );
}
