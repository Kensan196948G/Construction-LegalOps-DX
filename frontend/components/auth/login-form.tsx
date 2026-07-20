"use client";

import { signIn } from "next-auth/react";
import { useEffect, useRef, useState } from "react";

export interface LoginFormProps {
  callbackUrl?: string;
  error?: string;
  /** True when Cloudflare Access has authenticated the request at the edge. */
  behindAccess?: boolean;
}

/**
 * Cloudflare Access ログインフォーム。
 *
 * このデプロイの認証境界は Cloudflare Access（メール OTP + ルールグループ）。
 * エッジで認証済み（`behindAccess`）の場合、`cloudflare-access` provider へ
 * 自動サインインしてアプリのセッションを確立する。認証済みでない（＝Access を
 * 経由していない）場合は、そもそも origin へ到達できないため案内のみ表示する。
 */
export function LoginForm({ callbackUrl = "/", error, behindAccess = false }: LoginFormProps) {
  const [failed, setFailed] = useState<string | null>(error ?? null);
  const started = useRef(false);

  useEffect(() => {
    // Auto sign-in once on mount. Suppressed when a prior attempt errored
    // (shown via the retry action) so we never loop on failure.
    if (!behindAccess || started.current || error) return;
    started.current = true;
    // The browser request to the credentials callback carries the
    // Cf-Access-* headers (injected by Cloudflare); the server-side authorize()
    // reads and verifies them via the backend.
    void signIn("cloudflare-access", { callbackUrl }).catch(() => {
      setFailed("AccessSignInFailed");
    });
  }, [behindAccess, callbackUrl, error]);

  if (behindAccess && !failed) {
    return (
      <div
        className="flex items-center justify-center gap-2 text-sm text-muted-foreground"
        role="status"
        aria-live="polite"
      >
        <span
          className="h-4 w-4 animate-spin rounded-full border-2 border-muted-foreground border-t-transparent"
          aria-hidden="true"
        />
        サインインしています…
      </div>
    );
  }

  if (failed) {
    return (
      <div className="space-y-3 text-sm" role="alert">
        <p className="text-destructive">
          サインインに失敗しました。ページを再読み込みしてください。
        </p>
        {behindAccess ? (
          <button
            type="button"
            onClick={() => {
              setFailed(null);
              started.current = false;
              void signIn("cloudflare-access", { callbackUrl }).catch(() =>
                setFailed("AccessSignInFailed"),
              );
            }}
            className="w-full rounded-md bg-primary px-4 py-2 font-medium text-primary-foreground hover:bg-primary/90"
          >
            再試行
          </button>
        ) : null}
      </div>
    );
  }

  // Not behind Access (should not happen in production, since the origin is
  // only reachable through the Cloudflare Access tunnel).
  return (
    <p className="text-sm text-muted-foreground">
      アクセスするには、システム管理者から付与された Cloudflare Access の
      リンク経由でサインインしてください。
    </p>
  );
}

export default LoginForm;
