import type { Metadata } from "next";

import { ReviewsTable } from "@/components/reviews/reviews-table";
import { ReviewsFilters } from "@/components/reviews/reviews-filters";
import { AiDisclaimerInline } from "@/components/legal/ai-disclaimer-inline";
import { bindServerSession } from "@/lib/auth/session-bridge.server";
import { reviewsApi } from "@/lib/api/endpoints";

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

function formatDate(iso: string | null | undefined): string {
  if (!iso) return null as unknown as string;
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

async function getReviews(params: SearchParams): Promise<ReviewListResult> {
  const page = Number(params.page ?? 1);
  const perPage = 20;

  const cleanup = await bindServerSession();
  try {
    const result = await reviewsApi.list({
      status: params.status && params.status !== "all" ? params.status : undefined,
      page,
      page_size: perPage,
    });

    const items = result.items.map((r) => ({
      id: String(r.id),
      contractId: String(r.contract_id),
      contractTitle: r.summary ?? `レビュー #${r.id}`,
      aiModel: r.ai_model ?? "—",
      riskLevel: (r.overall_risk ?? "low") as "low" | "medium" | "high" | "critical",
      issuesCount: r.findings?.length ?? 0,
      status: r.status,
      // Human-confirmed = a final decision (approved or rejected) has been made
      reviewerConfirmed: r.status === "accepted" || r.status === "rejected",
      completedAt: r.finished_at ? formatDate(r.finished_at) : null,
    }));

    // Client-side risk level filter (no backend support)
    const filtered =
      params.riskLevel && params.riskLevel !== "all"
        ? items.filter((r) => r.riskLevel === params.riskLevel)
        : items;

    // Client-side reviewerConfirmed filter
    const finalItems =
      params.reviewerConfirmed === "true"
        ? filtered.filter((r) => r.reviewerConfirmed)
        : params.reviewerConfirmed === "false"
          ? filtered.filter((r) => !r.reviewerConfirmed)
          : filtered;

    return { items: finalItems, total: result.total, page: result.page, perPage };
  } catch {
    return { items: [], total: 0, page, perPage };
  } finally {
    cleanup();
  }
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
