"use client";

import { ArrowRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";

export interface ReviewSuggestedAction {
  action: string;
  target_clause_seq: number | null;
  description: string;
  replacement_text: string | null;
}

interface Props {
  reviewId: string;
  suggestions?: ReviewSuggestedAction[];
}

export function ReviewSuggestionsPanel({ reviewId: _, suggestions = [] }: Props) {
  if (suggestions.length === 0) {
    return (
      <p className="py-6 text-center text-sm text-muted-foreground">
        修正候補はまだありません。
      </p>
    );
  }

  return (
    <div className="space-y-4 py-2">
      {suggestions.map((s, index) => (
        <Card key={`${s.action}-${s.target_clause_seq ?? index}`}>
          <CardContent className="space-y-3 pt-4">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="secondary">アクション: {s.action}</Badge>
              {s.target_clause_seq ? (
                <span className="text-xs font-mono text-muted-foreground">
                  対象: 第{s.target_clause_seq}条
                </span>
              ) : null}
            </div>
            <p className="text-sm font-semibold">{s.description}</p>

            {s.replacement_text ? (
              <>
                <div className="flex justify-center">
                  <ArrowRight className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                </div>
                <div className="rounded-md bg-emerald-50 p-3 text-xs leading-relaxed text-emerald-800 dark:bg-emerald-950/20 dark:text-emerald-200">
                  <p className="mb-1 font-semibold">修正候補文言</p>
                  <p className="font-mono">{s.replacement_text}</p>
                </div>
              </>
            ) : null}

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
