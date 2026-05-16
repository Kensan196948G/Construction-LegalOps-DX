import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowUpRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { RiskBadge } from "@/components/risks/risk-badge";
import { AiDisclaimerInline } from "@/components/legal/ai-disclaimer-inline";
import { ReviewIssuesPanel } from "@/components/reviews/review-issues-panel";
import { ReviewRisksPanel } from "@/components/reviews/review-risks-panel";
import { ReviewSuggestionsPanel } from "@/components/reviews/review-suggestions-panel";
import { ReviewAuditTrail } from "@/components/reviews/review-audit-trail";
import { LawyerConfirmationCheckbox } from "@/components/reviews/lawyer-confirmation-checkbox";

export const metadata: Metadata = {
  title: "レビュー詳細",
};

interface ReviewDetail {
  id: string;
  contractId: string;
  contractTitle: string;
  aiModel: string;
  aiPromptVersion: string;
  riskLevel: "low" | "medium" | "high" | "critical";
  status: string;
  reviewerConfirmed: boolean;
  reviewerConfirmedBy: string | null;
  reviewerConfirmedAt: string | null;
  startedAt: string;
  completedAt: string | null;
  summary: string;
}

async function getReview(id: string): Promise<ReviewDetail | null> {
  if (!id) return null;
  return null;
}

interface ReviewDetailPageProps {
  params: Promise<{ id: string }>;
}

export default async function ReviewDetailPage({ params }: ReviewDetailPageProps) {
  const { id } = await params;
  const review = await getReview(id);

  if (!review) {
    notFound();
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs text-muted-foreground">レビュー ID: {review.id}</p>
          <h1 className="mt-1 text-2xl font-bold text-foreground">
            {review.contractTitle}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            モデル: {review.aiModel} (prompt v{review.aiPromptVersion})
          </p>
        </div>
        <div className="flex items-center gap-3">
          <RiskBadge level={review.riskLevel} />
          <Button asChild variant="outline">
            <Link href={`/contracts/${review.contractId}`}>
              契約を開く
              <ArrowUpRight className="ml-2 h-4 w-4" aria-hidden="true" />
            </Link>
          </Button>
        </div>
      </header>

      <AiDisclaimerInline>
        本ページの AI 評価・修正候補は法的判断ではありません。
        最終判断は法務担当者・顧問弁護士が行います。AI 出力に依拠した不利益に
        ついて、システム提供者は責任を負いません。
      </AiDisclaimerInline>

      <Card>
        <CardHeader>
          <CardTitle>レビューサマリー</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm leading-relaxed text-foreground">{review.summary}</p>
        </CardContent>
      </Card>

      <Tabs defaultValue="issues">
        <TabsList>
          <TabsTrigger value="issues">論点</TabsTrigger>
          <TabsTrigger value="risks">リスク</TabsTrigger>
          <TabsTrigger value="suggestions">修正候補</TabsTrigger>
          <TabsTrigger value="audit">監査証跡</TabsTrigger>
        </TabsList>

        <TabsContent value="issues">
          <ReviewIssuesPanel reviewId={review.id} />
        </TabsContent>
        <TabsContent value="risks">
          <ReviewRisksPanel reviewId={review.id} />
        </TabsContent>
        <TabsContent value="suggestions">
          <ReviewSuggestionsPanel reviewId={review.id} />
        </TabsContent>
        <TabsContent value="audit">
          <ReviewAuditTrail reviewId={review.id} />
        </TabsContent>
      </Tabs>

      <Card>
        <CardHeader>
          <CardTitle>法務担当者・顧問弁護士による確認</CardTitle>
        </CardHeader>
        <CardContent>
          <LawyerConfirmationCheckbox
            reviewId={review.id}
            confirmed={review.reviewerConfirmed}
            confirmedBy={review.reviewerConfirmedBy}
            confirmedAt={review.reviewerConfirmedAt}
          />
        </CardContent>
      </Card>
    </div>
  );
}
