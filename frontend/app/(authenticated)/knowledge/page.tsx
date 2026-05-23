import type { Metadata } from "next";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { KnowledgeSearchBar } from "@/components/knowledge/knowledge-search-bar";
import { KnowledgeResults } from "@/components/knowledge/knowledge-results";
import { KnowledgeCategoryNav } from "@/components/knowledge/knowledge-category-nav";
import { AiDisclaimerInline } from "@/components/legal/ai-disclaimer-inline";
import { bindServerSession } from "@/lib/auth/session-bridge.server";
import { knowledgeApi } from "@/lib/api/endpoints";

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

const KNOWN_SOURCES = ["internal_doc", "precedent", "faq", "playbook"] as const;
type KnowledgeSource = (typeof KNOWN_SOURCES)[number];

function deriveSource(tags: string[]): KnowledgeSource {
  for (const tag of tags) {
    if (KNOWN_SOURCES.includes(tag as KnowledgeSource)) return tag as KnowledgeSource;
  }
  return "internal_doc";
}

function deriveCategory(tags: string[]): string {
  return tags.find((t) => !KNOWN_SOURCES.includes(t as KnowledgeSource)) ?? "一般";
}

function makeExcerpt(body: string): string {
  const plain = body.replace(/\n+/g, " ").trim();
  return plain.length > 200 ? plain.slice(0, 200) + "…" : plain;
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

async function searchKnowledge(params: SearchParams): Promise<KnowledgeSearchResult> {
  const page = Number(params.page ?? 1);
  const perPage = 20;

  const cleanup = await bindServerSession();
  try {
    const result = await knowledgeApi.list({
      q: params.q || undefined,
      page,
      page_size: perPage,
    });

    const allItems = result.items.map((k) => {
      const tags = k.tags ?? [];
      return {
        id: String(k.id),
        title: k.title,
        excerpt: makeExcerpt(k.body),
        source: deriveSource(tags),
        category: deriveCategory(tags),
        tags,
        updatedAt: formatDate(k.updated_at),
        score: 0,
      };
    });

    // category and source filters are client-side (not in backend API)
    const filtered = allItems.filter((k) => {
      if (params.category && params.category !== "all" && k.category !== params.category) return false;
      if (params.source && params.source !== "all" && k.source !== params.source) return false;
      return true;
    });

    return { items: filtered, total: result.total, page, perPage };
  } catch {
    return { items: [], total: 0, page, perPage };
  } finally {
    cleanup();
  }
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
