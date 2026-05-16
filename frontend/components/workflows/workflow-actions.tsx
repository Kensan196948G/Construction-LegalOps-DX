"use client";
import { useState } from "react";
import { CheckCircle2, XCircle, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

interface Props { workflowId: string; }

export function WorkflowActions({ workflowId: _ }: Props) {
  const [comment, setComment] = useState("");
  const [done, setDone] = useState<"approved" | "rejected" | "returned" | null>(null);

  const act = (type: "approved" | "rejected" | "returned") => {
    setDone(type);
  };

  if (done) {
    const labels = { approved: "承認しました", rejected: "却下しました", returned: "差戻しました" };
    const colors = { approved: "text-emerald-700", rejected: "text-destructive", returned: "text-amber-700" };
    return (
      <div className={`flex items-center gap-2 rounded-md bg-muted p-4 text-sm ${colors[done]}`}>
        {done === "approved" && <CheckCircle2 className="h-5 w-5" />}
        {done === "rejected" && <XCircle className="h-5 w-5" />}
        {done === "returned" && <RotateCcw className="h-5 w-5" />}
        <span className="font-semibold">{labels[done]}</span>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <Textarea
        placeholder="コメントを入力（任意）"
        value={comment}
        onChange={e => setComment(e.target.value)}
        rows={3}
        className="text-sm"
      />
      <div className="flex flex-wrap gap-3">
        <Button onClick={() => act("approved")} className="gap-2">
          <CheckCircle2 className="h-4 w-4" /> 承認
        </Button>
        <Button onClick={() => act("returned")} variant="outline" className="gap-2 text-amber-700 border-amber-300">
          <RotateCcw className="h-4 w-4" /> 差戻し
        </Button>
        <Button onClick={() => act("rejected")} variant="outline" className="gap-2 text-destructive border-destructive/30">
          <XCircle className="h-4 w-4" /> 却下
        </Button>
      </div>
    </div>
  );
}
export default WorkflowActions;
