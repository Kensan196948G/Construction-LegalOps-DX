import type { ReactNode } from "react";
import { AlertTriangle } from "lucide-react";

interface Props { children?: ReactNode; }

export function AiDisclaimerInline({ children }: Props) {
  return (
    <p role="note" className="flex items-start gap-1.5 text-xs text-muted-foreground">
      <AlertTriangle className="mt-[2px] h-3.5 w-3.5 shrink-0 text-amber-500" aria-hidden />
      <span>{children ?? "AI は法的判断を確定しません。最終判断は法務担当者・顧問弁護士が行います。"}</span>
    </p>
  );
}
export default AiDisclaimerInline;
