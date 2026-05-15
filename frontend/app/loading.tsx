import { Loader2 } from "lucide-react";

export default function RootLoading() {
  return (
    <div
      className="flex min-h-screen items-center justify-center bg-background"
      role="status"
      aria-live="polite"
      aria-label="読み込み中"
    >
      <div className="flex flex-col items-center gap-3 text-muted-foreground">
        <Loader2 className="h-8 w-8 animate-spin" aria-hidden="true" />
        <p className="text-sm">読み込んでいます…</p>
      </div>
    </div>
  );
}
