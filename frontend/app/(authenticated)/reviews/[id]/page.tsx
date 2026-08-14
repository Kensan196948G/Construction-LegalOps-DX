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
import { bindServerSession } from "@/lib/auth/session-bridge.server";
import { ApiError } from "@/lib/api/client";
import { auditLogsApi, reviewsApi, risksApi } from "@/lib/api/endpoints";
import type { AuditLog, ReviewFinding, RiskItem } from "@/lib/api/schemas";
import type { ReviewSuggestedAction } from "@/components/reviews/review-suggestions-panel";

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
  startedAt: string | null;
  completedAt: string | null;
  summary: string;
  findings: ReviewFinding[];
  suggestedActions: ReviewSuggestedAction[];
  risks: RiskItem[];
  auditLogs: AuditLog[];
  auditForbidden: boolean;
}

type RiskLevel = "low" | "medium" | "high" | "critical";

function toRiskLevel(raw: string | null | undefined): RiskLevel {
  if (raw === "medium" || raw === "high" || raw === "critical") return raw;
  return "low";
}

function formatDate(iso: string | null | undefined): string | null {
  if (!iso) return null;
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

async function getReview(id: string): Promise<ReviewDetail | null> {
  const cleanup = await bindServerSession();
  try {
    const [rResult, risksResult, auditResult] = await Promise.allSettled([
      reviewsApi.get(id),
      reviewsApi.get(id).then((r) =>
        risksApi.list({ contract_id: r.contract_id, page: 1, page_size: 50 }),
      ),
      auditLogsApi.list({
        target_type: "reviews",
        target_id: id,
        page: 1,
        size: 20,
      }),
    ]);
    if (rResult.status === "rejected") {
      return null;
    }
    const r = rResult.value;
    const confirmed = r.status === "accepted" || r.status === "rejected";
    const risks = risksResult.status === "fulfilled" ? risksResult.value.items : [];
    let auditLogs: AuditLog[] = [];
    let auditForbidden = false;
    if (auditResult.status === "fulfilled") {
      auditLogs = auditResult.value.items;
    } else {
      auditForbidden = auditResult.reason instanceof ApiError && auditResult.reason.status === 403;
    }
    const suggestedActions: ReviewSuggestedAction[] = (r.suggested_actions ?? []).map((a) => ({
      action: a.action,
      target_clause_seq: a.target_clause_seq ?? null,
      description: a.description,
      replacement_text: a.replacement_text ?? null,
    }));
    return {
      id: String(r.id),
      contractId: String(r.contract_id),
      contractTitle: `レビュー #${r.contract_id}`,
      aiModel: r.ai_model ?? "—",
      aiPromptVersion: "—",
      riskLevel: toRiskLevel(r.overall_risk),
      status: r.status,
      reviewerConfirmed: confirmed,
      reviewerConfirmedBy: null,
      reviewerConfirmedAt: null,
      startedAt: formatDate(r.started_at),
      completedAt: formatDate(r.finished_at),
      summary: r.summary ?? `AI レビュー (リスク: ${r.overall_risk ?? "未評価"})。詳細は各タブでご確認ください。\n\n※ この要約は AI による参考情報です。法的判断は必ず法務担当者・顧問弁護士が行ってください。`,
      findings: r.findings ?? [],
      suggestedActions,
      risks,
      auditLogs,
      auditForbidden,
    };
  } catch {
    return null;
  } finally {
    cleanup();
  }
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
          <ReviewIssuesPanel reviewId={review.id} findings={review.findings} />
        </TabsContent>
        <TabsContent value="risks">
          <ReviewRisksPanel reviewId={review.id} risks={review.risks} />
        </TabsContent>
        <TabsContent value="suggestions">
          <ReviewSuggestionsPanel reviewId={review.id} suggestions={review.suggestedActions} />
        </TabsContent>
        <TabsContent value="audit">
          <ReviewAuditTrail
            reviewId={review.id}
            logs={review.auditLogs}
            forbidden={review.auditForbidden}
          />
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
