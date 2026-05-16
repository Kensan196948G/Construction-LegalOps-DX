import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { CONTRACT_STATUS_LABELS } from "@/lib/mock-data";

interface ContractDetail {
  id: string; title: string; counterparty: string; contractType: string;
  amount: number | null; currency: string; startDate: string | null;
  endDate: string | null; status: string; riskLevel: string; summary: string;
}

interface Props { contract: ContractDetail; }

const STATUS_V: Record<string, "default" | "secondary" | "outline" | "destructive"> = {
  draft: "secondary", in_review: "secondary", approved: "default",
  pending_approval: "outline", expired: "destructive", archived: "outline",
};

export function ContractSummary({ contract }: Props) {
  const label = CONTRACT_STATUS_LABELS[contract.status as keyof typeof CONTRACT_STATUS_LABELS] ?? contract.status;
  const fmt = (n: number | null) => n == null ? "—" : `¥${n.toLocaleString()}`;

  return (
    <Card>
      <CardContent className="pt-6">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          <Row label="状態"><Badge variant={STATUS_V[contract.status] ?? "outline"}>{label}</Badge></Row>
          <Row label="契約種別">{contract.contractType}</Row>
          <Row label="相手方">{contract.counterparty}</Row>
          <Row label="契約金額">{fmt(contract.amount)}</Row>
          <Row label="開始日">{contract.startDate ?? "—"}</Row>
          <Row label="終了日">{contract.endDate ?? "—"}</Row>
        </div>
        {contract.summary && (
          <div className="mt-4 rounded-md bg-muted/50 p-3 text-sm leading-relaxed text-foreground">
            {contract.summary}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <div className="mt-0.5 text-sm font-medium">{children}</div>
    </div>
  );
}

export default ContractSummary;
