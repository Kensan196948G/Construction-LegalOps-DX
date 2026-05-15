"use client";

import * as React from "react";
import { CheckCircle2, XCircle, MessageSquare } from "lucide-react";

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
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";

export type ApprovalDecision = "approve" | "reject" | "comment";

export interface ApprovalSubmitPayload {
  decision: ApprovalDecision;
  comment: string;
}

export interface ApprovalPanelProps extends React.HTMLAttributes<HTMLDivElement> {
  title?: string;
  description?: string;
  /** コメント必須にする場合 */
  requireCommentOnReject?: boolean;
  disabled?: boolean;
  onSubmit?: (payload: ApprovalSubmitPayload) => void | Promise<void>;
}

export function ApprovalPanel({
  title = "承認操作",
  description = "本契約レビューに対する判断を入力してください。",
  requireCommentOnReject = true,
  disabled = false,
  onSubmit,
  className,
  ...props
}: ApprovalPanelProps) {
  const [comment, setComment] = React.useState("");
  const [submitting, setSubmitting] = React.useState<ApprovalDecision | null>(
    null
  );
  const [error, setError] = React.useState<string | null>(null);

  const handle = async (decision: ApprovalDecision) => {
    setError(null);
    if (decision === "reject" && requireCommentOnReject && !comment.trim()) {
      setError("差戻しにはコメントが必要です。");
      return;
    }
    try {
      setSubmitting(decision);
      await onSubmit?.({ decision, comment: comment.trim() });
      setComment("");
    } finally {
      setSubmitting(null);
    }
  };

  return (
    <Card className={cn(className)} {...props}>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-2">
          <Label htmlFor="approval-comment">コメント</Label>
          <Textarea
            id="approval-comment"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="承認理由・差戻し理由・追記事項を入力"
            rows={4}
            disabled={disabled}
          />
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
        </div>
      </CardContent>
      <CardFooter className="flex flex-wrap justify-end gap-2">
        <Button
          variant="ghost"
          onClick={() => handle("comment")}
          disabled={disabled || submitting !== null || !comment.trim()}
        >
          <MessageSquare className="h-4 w-4" />
          コメントのみ
        </Button>
        <Button
          variant="destructive"
          onClick={() => handle("reject")}
          disabled={disabled || submitting !== null}
        >
          <XCircle className="h-4 w-4" />
          {submitting === "reject" ? "送信中…" : "差戻し"}
        </Button>
        <Button
          onClick={() => handle("approve")}
          disabled={disabled || submitting !== null}
        >
          <CheckCircle2 className="h-4 w-4" />
          {submitting === "approve" ? "送信中…" : "承認"}
        </Button>
      </CardFooter>
    </Card>
  );
}

export default ApprovalPanel;
