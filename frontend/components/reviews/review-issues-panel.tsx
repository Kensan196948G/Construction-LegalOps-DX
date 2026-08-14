"use client";

import { AlertTriangle, XCircle, AlertCircle, Info } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import type { ReviewFinding } from "@/lib/api/schemas";

type Severity = "critical" | "high" | "medium" | "low";

const SEV_LABEL: Record<string, string> = {
  critical: "重大",
  high: "高",
  medium: "中",
  low: "低",
};
const SEV_V: Record<string, "destructive" | "default" | "secondary" | "outline"> = {
  critical: "destructive",
  high: "default",
  medium: "secondary",
  low: "outline",
};
const SEV_ICON = ({ s }: { s: string }) => {
  if (s === "critical") return <XCircle className="h-4 w-4 text-destructive" aria-hidden="true" />;
  if (s === "high") return <AlertTriangle className="h-4 w-4 text-orange-500" aria-hidden="true" />;
  if (s === "medium") return <AlertCircle className="h-4 w-4 text-amber-500" aria-hidden="true" />;
  return <Info className="h-4 w-4 text-blue-400" aria-hidden="true" />;
};

interface Props {
  reviewId: string;
  findings?: ReviewFinding[];
}

export function ReviewIssuesPanel({ reviewId: _, findings = [] }: Props) {
  if (findings.length === 0) {
    return (
      <p className="py-6 text-center text-sm text-muted-foreground">
        AI レビューの指摘はまだありません。
      </p>
    );
  }

  return (
    <div className="space-y-3 py-2">
      {findings.map((issue, index) => {
        const severity = (issue.risk_level ?? "low") as Severity;
        return (
          <Card key={`${issue.clause_seq ?? "f"}-${index}`}>
            <CardContent className="pt-4">
              <div className="flex items-start gap-3">
                <SEV_ICON s={severity} />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-mono text-muted-foreground">
                      {issue.title ?? `第${issue.clause_seq ?? "?"}条`}
                    </span>
                    <Badge variant={SEV_V[severity]}>{SEV_LABEL[severity] ?? severity}</Badge>
                    {issue.verdict ? (
                      <span className="text-xs text-muted-foreground">判定: {issue.verdict}</span>
                    ) : null}
                  </div>
                  <p className="mt-1 text-sm">{issue.comment}</p>
                  {issue.suggestion ? (
                    <p className="mt-1 text-xs text-muted-foreground">
                      推奨対応: {issue.suggestion}
                    </p>
                  ) : null}
                </div>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
export default ReviewIssuesPanel;
