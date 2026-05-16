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

import { MOCK_REVIEWS } from "@/lib/mock-data";

async function getReviews(params: SearchParams): Promise<ReviewListResult> {
  let items = MOCK_REVIEWS.map(r => ({
    id: r.id, contractId: r.contractId, contractTitle: r.contractTitle,
    aiModel: r.aiModel, riskLevel: r.riskLevel, issuesCount: r.issuesCount,
    status: r.status, reviewerConfirmed: r.reviewerConfirmed, completedAt: r.completedAt,
  }));
  if (params.status) items = items.filter(r => r.status === params.status);
  if (params.riskLevel) items = items.filter(r => r.riskLevel === params.riskLevel);
  if (params.reviewerConfirmed === "true") items = items.filter(r => r.reviewerConfirmed);
  if (params.reviewerConfirmed === "false") items = items.filter(r => !r.reviewerConfirmed);
  const page = Number(params.page ?? 1);
  const perPage = 20;
  const total = items.length;
  items = items.slice((page - 1) * perPage, page * perPage);
  return { items, total, page, perPage };
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
