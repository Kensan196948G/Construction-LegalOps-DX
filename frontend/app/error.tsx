"use client";

import { useEffect } from "react";
import { AlertTriangle, RotateCcw } from "lucide-react";

import { Button } from "@/components/ui/button";

interface RootErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function RootError({ error, reset }: RootErrorProps) {
  useEffect(() => {
    // Sentry などへの連携は API Client / Observability チームが追加。
    // 本コンポーネントでは console に digest のみを残す。
    // eslint-disable-next-line no-console
    console.error("[RootError]", { message: error.message, digest: error.digest });
  }, [error]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-6">
      <div className="w-full max-w-md rounded-lg border bg-card p-8 text-center shadow-sm">
        <AlertTriangle
          className="mx-auto h-10 w-10 text-destructive"
          aria-hidden="true"
        />
        <h1 className="mt-4 text-xl font-semibold text-foreground">
          予期せぬエラーが発生しました
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          画面の再読み込みをお試しください。問題が続く場合はシステム管理者に
          下記エラー ID とともにご連絡ください。
        </p>
        {error.digest ? (
          <p className="mt-3 text-xs font-mono text-muted-foreground">
            エラー ID: {error.digest}
          </p>
        ) : null}
        <Button onClick={reset} className="mt-6" aria-label="再試行">
          <RotateCcw className="mr-2 h-4 w-4" aria-hidden="true" />
          再試行する
        </Button>
      </div>
    </div>
  );
}
