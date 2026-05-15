import Link from "next/link";
import { FileQuestion } from "lucide-react";

import { Button } from "@/components/ui/button";

export const metadata = {
  title: "ページが見つかりません",
};

export default function NotFound() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-6">
      <div className="w-full max-w-md rounded-lg border bg-card p-8 text-center shadow-sm">
        <FileQuestion
          className="mx-auto h-10 w-10 text-muted-foreground"
          aria-hidden="true"
        />
        <h1 className="mt-4 text-2xl font-semibold text-foreground">
          404 — ページが見つかりません
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          お探しのページは存在しないか、移動された可能性があります。
        </p>
        <Button asChild className="mt-6">
          <Link href="/dashboard">ダッシュボードへ戻る</Link>
        </Button>
      </div>
    </div>
  );
}
