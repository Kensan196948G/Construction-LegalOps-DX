import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, Tag, Calendar, FileText } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { AiDisclaimerInline } from "@/components/legal/ai-disclaimer-inline";
import { bindServerSession } from "@/lib/auth/session-bridge.server";
import { knowledgeApi } from "@/lib/api/endpoints";
import type { KnowledgeArticle } from "@/lib/api/schemas";

export const metadata: Metadata = {
  title: "ナレッジ詳細",
  description: "ナレッジベース記事の詳細表示",
};

interface Props {
  params: Promise<{ id: string }>;
}

async function fetchArticle(id: string): Promise<KnowledgeArticle | null> {
  const cleanup = await bindServerSession();
  try {
    const result = await knowledgeApi.get(Number(id));
    return result ?? null;
  } catch {
    return null;
  } finally {
    cleanup();
  }
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

export default async function KnowledgeDetailPage({ params }: Props) {
  const { id } = await params;
  const article = await fetchArticle(id);

  if (article === null) {
    // Article not found or API unavailable — show 404 only for non-numeric ids
    if (!/^\d+$/.test(id)) {
      notFound();
    }
    // For numeric ids where API is unreachable (dev/E2E without backend), show a placeholder
    return (
      <div className="space-y-6" data-testid="knowledge-detail-page">
        <nav aria-label="パンくず">
          <Link
            href="/knowledge"
            className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
            data-testid="back-link"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden />
            ナレッジベースに戻る
          </Link>
        </nav>
        <AiDisclaimerInline>
          AI 要約は参考情報です。法的判断は法務担当者・顧問弁護士が行ってください。
        </AiDisclaimerInline>
        <Card>
          <CardContent className="py-16 text-center text-sm text-muted-foreground">
            記事が見つかりませんでした。
          </CardContent>
        </Card>
      </div>
    );
  }

  const tags = article.tags ?? [];

  return (
    <div className="space-y-6" data-testid="knowledge-detail-page">
      <nav aria-label="パンくず">
        <Link
          href="/knowledge"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
          data-testid="back-link"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden />
          ナレッジベースに戻る
        </Link>
      </nav>

      <header>
        <h1 className="text-2xl font-bold text-foreground" data-testid="article-title">
          {article.title}
        </h1>
        <div
          className="mt-2 flex flex-wrap items-center gap-3 text-xs text-muted-foreground"
          data-testid="article-metadata"
        >
          <span className="flex items-center gap-1">
            <Calendar className="h-3.5 w-3.5" aria-hidden />
            作成: {formatDate(article.created_at)}
          </span>
          {article.updated_at && (
            <span className="flex items-center gap-1">
              <FileText className="h-3.5 w-3.5" aria-hidden />
              更新: {formatDate(article.updated_at)}
            </span>
          )}
        </div>
      </header>

      <AiDisclaimerInline>
        この記事に含まれる AI 要約は参考情報です。判例の引用・適用判断は
        法務担当者・顧問弁護士が行ってください。
      </AiDisclaimerInline>

      {tags.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5" data-testid="article-tags">
          <Tag className="h-3.5 w-3.5 text-muted-foreground" aria-hidden />
          {tags.map((t) => (
            <Badge key={t} variant="outline" className="text-xs">
              {t}
            </Badge>
          ))}
        </div>
      )}

      <Card>
        <CardContent className="pt-6">
          <div
            className="prose prose-sm max-w-none whitespace-pre-wrap text-sm text-foreground"
            data-testid="article-body"
          >
            {article.body}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
