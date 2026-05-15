import * as React from "react";
import { Sparkles, ArrowRight, ScaleIcon } from "lucide-react";

import { cn } from "@/components/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export interface ReviewSuggestion {
  id: string;
  /** 何に対する提案か (例: 第7条 解除条項) */
  target: string;
  /** 提案の要約 */
  summary: string;
  /** 修正前テキスト */
  original?: string;
  /** AI が提案する修正後テキスト */
  proposed: string;
  /** 提案理由 / 根拠 */
  rationale?: string;
  /** AI 信頼度 (0-100) */
  confidence?: number;
}

export interface ReviewSuggestionCardProps
  extends React.HTMLAttributes<HTMLDivElement> {
  suggestion: ReviewSuggestion;
  onAccept?: (suggestion: ReviewSuggestion) => void;
  onReject?: (suggestion: ReviewSuggestion) => void;
}

export function ReviewSuggestionCard({
  suggestion,
  onAccept,
  onReject,
  className,
  ...props
}: ReviewSuggestionCardProps) {
  return (
    <Card className={cn("border-l-4 border-l-violet-500", className)} {...props}>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div className="flex flex-col gap-1">
            <CardTitle className="flex items-center gap-2 text-base">
              <Sparkles className="h-4 w-4 text-violet-500" aria-hidden="true" />
              {suggestion.target}
            </CardTitle>
            <CardDescription>{suggestion.summary}</CardDescription>
          </div>
          {typeof suggestion.confidence === "number" && (
            <Badge variant="outline" className="font-mono">
              信頼度 {suggestion.confidence}%
            </Badge>
          )}
        </div>
      </CardHeader>

      <CardContent className="flex flex-col gap-3">
        {suggestion.original && (
          <div className="rounded-md bg-muted/50 p-3">
            <p className="mb-1 text-xs font-medium text-muted-foreground">
              修正前
            </p>
            <p className="whitespace-pre-wrap text-sm">{suggestion.original}</p>
          </div>
        )}
        <div className="flex items-center justify-center text-muted-foreground">
          <ArrowRight className="h-4 w-4" aria-hidden="true" />
        </div>
        <div className="rounded-md border border-emerald-300/60 bg-emerald-50 p-3 dark:border-emerald-700/40 dark:bg-emerald-950/30">
          <p className="mb-1 text-xs font-medium text-emerald-800 dark:text-emerald-200">
            AI 修正案
          </p>
          <p className="whitespace-pre-wrap text-sm">{suggestion.proposed}</p>
        </div>
        {suggestion.rationale && (
          <p className="text-xs text-muted-foreground">
            <span className="font-medium">根拠:</span> {suggestion.rationale}
          </p>
        )}

        <p className="flex items-start gap-1.5 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-700/50 dark:bg-amber-950/40 dark:text-amber-100">
          <ScaleIcon
            className="mt-[2px] h-3.5 w-3.5 shrink-0"
            aria-hidden="true"
          />
          <span>
            <strong>AI 提案。弁護士確認推奨。</strong>{" "}
            適用前に必ず法務担当者・顧問弁護士の確認を行ってください。
          </span>
        </p>
      </CardContent>

      {(onAccept || onReject) && (
        <CardFooter className="justify-end gap-2">
          {onReject && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onReject(suggestion)}
            >
              却下
            </Button>
          )}
          {onAccept && (
            <Button size="sm" onClick={() => onAccept(suggestion)}>
              採用候補に追加
            </Button>
          )}
        </CardFooter>
      )}
    </Card>
  );
}

export default ReviewSuggestionCard;
