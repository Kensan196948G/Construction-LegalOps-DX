import { AlertTriangle, XCircle, AlertCircle, Info } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { MOCK_REVIEW_ISSUES } from "@/lib/mock-data";

type Severity = "critical" | "high" | "medium" | "low";

const SEV_LABEL: Record<Severity, string> = {
  critical: "重大", high: "高", medium: "中", low: "低",
};
const SEV_V: Record<Severity, "destructive" | "default" | "secondary" | "outline"> = {
  critical: "destructive", high: "default", medium: "secondary", low: "outline",
};
const SEV_ICON = ({ s }: { s: Severity }) => {
  if (s === "critical") return <XCircle className="h-4 w-4 text-destructive" />;
  if (s === "high") return <AlertTriangle className="h-4 w-4 text-orange-500" />;
  if (s === "medium") return <AlertCircle className="h-4 w-4 text-amber-500" />;
  return <Info className="h-4 w-4 text-blue-400" />;
};

interface Props { reviewId: string; }

export function ReviewIssuesPanel({ reviewId: _ }: Props) {
  return (
    <div className="space-y-3 py-2">
      {MOCK_REVIEW_ISSUES.map(issue => (
        <Card key={issue.id}>
          <CardContent className="pt-4">
            <div className="flex items-start gap-3">
              <SEV_ICON s={issue.severity as Severity} />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs font-mono text-muted-foreground">{issue.target}</span>
                  <Badge variant={SEV_V[issue.severity as Severity]}>{SEV_LABEL[issue.severity as Severity]}</Badge>
                </div>
                <p className="mt-1 text-sm font-semibold">{issue.summary}</p>
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{issue.detail}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
export default ReviewIssuesPanel;
