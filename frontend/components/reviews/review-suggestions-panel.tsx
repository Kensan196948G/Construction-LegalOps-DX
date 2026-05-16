import { ArrowRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { MOCK_REVIEW_SUGGESTIONS } from "@/lib/mock-data";

interface Props { reviewId: string; }

export function ReviewSuggestionsPanel({ reviewId: _ }: Props) {
  return (
    <div className="space-y-4 py-2">
      {MOCK_REVIEW_SUGGESTIONS.map(s => (
        <Card key={s.id}>
          <CardContent className="pt-4 space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-mono text-muted-foreground">{s.target}</span>
              <Badge variant="secondary">信頼度 {s.confidence}%</Badge>
            </div>
            <p className="text-sm font-semibold">{s.summary}</p>

            <div className="rounded-md bg-red-50 dark:bg-red-950/20 p-3 text-xs text-red-800 dark:text-red-200 leading-relaxed">
              <p className="mb-1 font-semibold">現行文言</p>
              <p className="font-mono">{s.original}</p>
            </div>

            <div className="flex justify-center">
              <ArrowRight className="h-4 w-4 text-muted-foreground" />
            </div>

            <div className="rounded-md bg-emerald-50 dark:bg-emerald-950/20 p-3 text-xs text-emerald-800 dark:text-emerald-200 leading-relaxed">
              <p className="mb-1 font-semibold">修正候補</p>
              <p className="font-mono">{s.proposed}</p>
            </div>

            <div className="rounded-md bg-muted/50 p-3 text-xs leading-relaxed text-muted-foreground">
              <p className="mb-1 font-semibold">根拠</p>
              <p>{s.rationale}</p>
            </div>

            <p className="text-xs text-muted-foreground italic">
              ※ AI 修正候補は参考情報です。採否の判断は法務担当者・顧問弁護士が行ってください。
            </p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
export default ReviewSuggestionsPanel;
