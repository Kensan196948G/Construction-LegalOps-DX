import { MOCK_RISKS, MOCK_REVIEWS } from "@/lib/mock-data";
import { RiskBadge } from "@/components/risks/risk-badge";
import { Badge } from "@/components/ui/badge";

const STATUS_LABEL: Record<string, string> = {
  open: "未対応", mitigated: "軽減済み", accepted: "受容", closed: "解消",
};
const STATUS_V: Record<string, "destructive" | "default" | "secondary" | "outline"> = {
  open: "destructive", mitigated: "default", accepted: "secondary", closed: "outline",
};

interface Props { reviewId: string; }

export function ReviewRisksPanel({ reviewId }: Props) {
  const review = MOCK_REVIEWS.find(r => r.id === reviewId);
  const risks = review
    ? MOCK_RISKS.filter(r => r.contractId === review.contractId)
    : MOCK_RISKS.slice(0, 3);

  if (risks.length === 0) {
    return <p className="py-8 text-center text-sm text-muted-foreground">リスクは検出されませんでした</p>;
  }

  return (
    <div className="space-y-3 py-2">
      {risks.map(risk => (
        <div key={risk.id} className="rounded-md border p-4">
          <div className="flex flex-wrap items-center gap-2">
            <RiskBadge level={risk.level} />
            <Badge variant={STATUS_V[risk.status] ?? "outline"}>{STATUS_LABEL[risk.status] ?? risk.status}</Badge>
            <span className="ml-auto text-xs text-muted-foreground">スコア {risk.score}/100</span>
          </div>
          <p className="mt-2 text-sm font-semibold">{risk.category}</p>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{risk.description}</p>
          {risk.owner && (
            <p className="mt-2 text-xs text-muted-foreground">担当: {risk.owner}</p>
          )}
        </div>
      ))}
    </div>
  );
}
export default ReviewRisksPanel;
