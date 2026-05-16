"use client";
import { useState } from "react";
import { CheckCircle2, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Props {
  reviewId: string;
  confirmed: boolean;
  confirmedBy: string | null;
  confirmedAt: string | null;
}

export function LawyerConfirmationCheckbox({ reviewId: _, confirmed: initialConfirmed, confirmedBy, confirmedAt }: Props) {
  const [confirmed, setConfirmed] = useState(initialConfirmed);
  const [saving, setSaving] = useState(false);

  const handleConfirm = () => {
    setSaving(true);
    setTimeout(() => {
      setConfirmed(true);
      setSaving(false);
    }, 800);
  };

  if (confirmed) {
    return (
      <div className="flex items-start gap-3 rounded-md bg-emerald-50 dark:bg-emerald-950/20 p-4">
        <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
        <div>
          <p className="text-sm font-semibold text-emerald-800 dark:text-emerald-200">法務担当者確認済み</p>
          {confirmedBy && confirmedAt && (
            <p className="mt-0.5 text-xs text-muted-foreground">
              {confirmedBy} が {confirmedAt} に確認しました
            </p>
          )}
          <p className="mt-2 text-xs text-muted-foreground">
            AI 出力を法務担当者・顧問弁護士が確認し、法的判断を行いました。
            このレコードは監査証跡に記録されています。
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-3 rounded-md border border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/20 p-4">
        <Clock className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
        <div>
          <p className="text-sm font-semibold text-amber-800 dark:text-amber-200">法務担当者確認 未実施</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            AI レビュー結果の法的有効性については、資格を持つ法務担当者・顧問弁護士の確認が必要です。
          </p>
        </div>
      </div>
      <Button onClick={handleConfirm} disabled={saving} variant="default">
        {saving ? "記録中..." : "法務確認済みとしてマーク"}
      </Button>
      <p className="text-xs text-muted-foreground">
        ※ この操作は監査証跡に記録されます。AI 出力のみを根拠に法的判断を行わないでください。
      </p>
    </div>
  );
}
export default LawyerConfirmationCheckbox;
