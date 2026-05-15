import type { Metadata } from "next";

import { ReviewsTable } from "@/components/reviews/reviews-table";
import { ReviewsFilters } from "@/components/reviews/reviews-filters";
import { AiDisclaimerInline } from "@/components/legal/ai-disclaimer-inline";

export const metadata: Metadata = {
  title: "AI 一次レビュー",
  description: "AI による契約書一次レビュー結果の一覧",
};

interface SearchParams {
  status?: string;
  riskLevel?: string;
  reviewerConfirmed?: string;
  page?: string;
}

interface ReviewsPageProps {
  searchParams?: Promise<SearchParams>;
}

interface ReviewListResult {
  items: Array<{
    id: string;
    contractId: string;
    contractTitle: string;
    aiModel: string;
    riskLevel: "low" | "medium" | "high" | "critical";
    issuesCount: number;
    status: string;
    reviewerConfirmed: boolean;
    completedAt: string | null;
  }>;
  total: number;
  page: number;
  perPage: number;
}

async function getReviews(_params: SearchParams): Promise<ReviewListResult> {
  return { items: [], total: 0, page: 1, perPage: 20 };
}

export default async function ReviewsPage({ searchParams }: ReviewsPageProps) {
  const params = (await searchParams) ?? {};
  const result = await getReviews(params);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-foreground">AI 一次レビュー</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          AI が生成した一次レビュー結果の一覧です。法務担当者の確認を経て確定します。
        </p>
      </header>

      <AiDisclaimerInline>
        ここに表示される評価・スコアは AI による参考情報です。最終的な
        法的判断は法務担当者・顧問弁護士が行います。
      </AiDisclaimerInline>

      <ReviewsFilters
        defaultValues={{
          status: params.status,
          riskLevel: params.riskLevel,
          reviewerConfirmed: params.reviewerConfirmed,
        }}
      />

      <ReviewsTable
        items={result.items}
        total={result.total}
        page={result.page}
        perPage={result.perPage}
      />
    </div>
  );
}
